import { NextResponse } from "next/server";
import { createObservabilityFallback, type ObservabilityPoint, type ObservabilitySnapshot } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type PrometheusInstantSeries = {
  metric?: Record<string, string>;
  value?: [number, string];
};

type PrometheusRangeSeries = {
  metric?: Record<string, string>;
  values?: Array<[number, string]>;
};

type PrometheusPayload<T> = {
  status?: string;
  data?: {
    result?: T[];
  };
};

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function fetchPrometheus<T>(url: string): Promise<PrometheusPayload<T>> {
  const payload = await fetchJson<PrometheusPayload<T>>(url);
  if (payload.status && payload.status !== "success") {
    throw new Error("Prometheus query returned an error");
  }
  return payload;
}

function queryUrl(baseUrl: string, path: string, query: string, params?: Record<string, string | number>) {
  const url = new URL(path, baseUrl);
  url.searchParams.set("query", query);
  for (const [key, value] of Object.entries(params ?? {})) {
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

function toTimeLabel(unixSeconds: number) {
  return new Date(unixSeconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function mergeRangeSeries(series: PrometheusRangeSeries[], keyForSeries: (metric: Record<string, string>) => string) {
  const rows = new Map<string, { point: ObservabilityPoint; ts: number }>();

  for (const item of series) {
    const key = keyForSeries(item.metric ?? {});
    for (const [timestamp, rawValue] of item.values ?? []) {
      const label = toTimeLabel(timestamp);
      const existing = rows.get(label);
      const row = existing?.point ?? { timestamp: label };
      row[key] = Number.parseFloat(rawValue);
      rows.set(label, { point: row, ts: timestamp });
    }
  }

  return Array.from(rows.values())
    .sort((left, right) => left.ts - right.ts)
    .map((item) => item.point);
}

function latestValue(series: PrometheusInstantSeries[] | undefined) {
  const entry = series?.[0]?.value;
  return entry ? Number.parseFloat(entry[1]) : 0;
}

function latestRangeValue(series: PrometheusRangeSeries[] | undefined) {
  const values = series?.flatMap((item) => item.values ?? []) ?? [];
  const latest = values[values.length - 1];
  return latest ? Number.parseFloat(latest[1]) : 0;
}

function latestThroughput(rows: ObservabilityPoint[]) {
  if (!rows.length) {
    return 0;
  }

  const row = rows[rows.length - 1];
  return Object.values(row).reduce((sum: number, value) => (typeof value === "number" ? sum + value : sum), 0);
}

async function fetchPrometheusSnapshot(baseUrl: string): Promise<ObservabilitySnapshot> {
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - 3600;

  const [throughputResult, latencyResult, protocolMixResult, severityResult, dlqResult, batchSizeResult] =
    await Promise.allSettled([
      fetchPrometheus<PrometheusRangeSeries>(
        queryUrl(
          baseUrl,
          "/api/v1/query_range",
          "sum by (protocol) (rate(edge_ingest_events_total[5m]))",
          { start: windowStart, end: now, step: 300 },
        ),
      ),
      fetchPrometheus<PrometheusRangeSeries>(
        queryUrl(
          baseUrl,
          "/api/v1/query_range",
          "histogram_quantile(0.95, sum by (le) (rate(ai_gateway_llm_request_seconds_bucket[5m])))",
          { start: windowStart, end: now, step: 300 },
        ),
      ),
      fetchPrometheus<PrometheusInstantSeries>(
        queryUrl(baseUrl, "/api/v1/query", "sum by (protocol) (edge_ingest_events_total)"),
      ),
      fetchPrometheus<PrometheusInstantSeries>(
        queryUrl(baseUrl, "/api/v1/query", "sum by (severity) (ai_gateway_batch_severity_total)"),
      ),
      fetchPrometheus<PrometheusInstantSeries>(
        queryUrl(baseUrl, "/api/v1/query", "sum(edge_ingest_dlq_total)"),
      ),
      fetchPrometheus<PrometheusInstantSeries>(
        queryUrl(baseUrl, "/api/v1/query", "ai_gateway_batch_size"),
      ),
    ]);
  const batchSize =
    batchSizeResult.status === "fulfilled"
      ? latestValue(batchSizeResult.value.data?.result)
      : 0;

  const throughput =
    throughputResult.status === "fulfilled"
      ? mergeRangeSeries(throughputResult.value.data?.result ?? [], (metric) => metric.protocol ?? "unknown")
      : [];

  const latency =
    latencyResult.status === "fulfilled"
      ? mergeRangeSeries(latencyResult.value.data?.result ?? [], () => "p95").map((row) => ({
          timestamp: row.timestamp,
          p95: Number(row.p95 ?? 0),
          batch_size: batchSize,
        }))
      : [];

  const protocolMix =
    protocolMixResult.status === "fulfilled"
      ? (protocolMixResult.value.data?.result ?? []).map((series) => ({
          protocol: series.metric?.protocol ?? "unknown",
          total: series.value ? Number.parseFloat(series.value[1]) : 0,
        }))
      : [];

  const severity =
    severityResult.status === "fulfilled"
      ? (severityResult.value.data?.result ?? []).map((series) => ({
          label: series.metric?.severity ?? "unknown",
          total: series.value ? Number.parseFloat(series.value[1]) : 0,
        }))
      : [];

  const degradedReasons = [
    throughputResult.status === "rejected" ? "Prometheus throughput query failed." : null,
    latencyResult.status === "rejected" ? "Prometheus latency query failed." : null,
    protocolMixResult.status === "rejected" ? "Prometheus protocol mix query failed." : null,
    severityResult.status === "rejected" ? "Prometheus severity query failed." : null,
    dlqResult.status === "rejected" ? "Prometheus DLQ query failed." : null,
    batchSizeResult.status === "rejected" ? "Prometheus batch-size query failed." : null,
  ].filter((reason): reason is string => reason !== null);

  const summary = {
    total_throughput: latestThroughput(throughput),
    ai_latency_p95:
      latencyResult.status === "fulfilled" ? latestRangeValue(latencyResult.value.data?.result) : 0,
    dlq_total: dlqResult.status === "fulfilled" ? latestValue(dlqResult.value.data?.result) : 0,
    grafana_online: true,
  };
  const prometheusOnline = degradedReasons.length < 6;

  return {
    grafana: {
      online: true,
      status: "online",
      login_url: baseUrl.replace(/\/$/, ""),
    },
    prometheus: {
      online: prometheusOnline,
      status: prometheusOnline && degradedReasons.length === 0 ? "online" : "degraded",
    },
    throughput,
    latency,
    protocolMix,
    severity,
    summary,
    degraded: degradedReasons.length > 0,
    degraded_reasons: degradedReasons,
  };
}

function publicUrl(value: string) {
  return value.replace(/\/$/, "");
}

async function fetchGrafanaStatus(internalBaseUrl: string, publicBaseUrl: string) {
  try {
    const health = await fetchJson<Record<string, string>>(new URL("/api/health", internalBaseUrl).toString());
    return {
      online: true,
      status: health.database === "ok" ? "online" : "degraded",
      login_url: publicUrl(publicBaseUrl),
    };
  } catch {
    return {
      online: false,
      status: "offline",
      login_url: publicUrl(publicBaseUrl),
    };
  }
}

export async function GET() {
  const prometheusBaseUrl = process.env.PROMETHEUS_BASE_URL ?? "http://localhost:19090";
  const grafanaBaseUrl = process.env.GRAFANA_BASE_URL ?? "http://localhost:13000";
  const grafanaPublicUrl = process.env.GRAFANA_PUBLIC_URL ?? "http://localhost:13000";
  const fallback = createObservabilityFallback();

  const [prometheus, grafana] = await Promise.allSettled([
    fetchPrometheusSnapshot(prometheusBaseUrl),
    fetchGrafanaStatus(grafanaBaseUrl, grafanaPublicUrl),
  ]);

  if (prometheus.status === "fulfilled") {
    const grafanaSnapshot = grafana.status === "fulfilled"
      ? grafana.value
      : { ...fallback.grafana, login_url: publicUrl(grafanaPublicUrl) };
    const degradedReasons = [
      ...(prometheus.value.degraded_reasons ?? []),
      ...(!grafanaSnapshot.online ? ["Grafana is unavailable."] : []),
    ];
    return NextResponse.json({
      ...prometheus.value,
      grafana: grafanaSnapshot,
      summary: {
        ...prometheus.value.summary,
        grafana_online: grafanaSnapshot.online,
      },
      degraded: degradedReasons.length > 0,
      degraded_reasons: degradedReasons,
    });
  }

  const grafanaSnapshot = grafana.status === "fulfilled"
    ? grafana.value
    : { ...fallback.grafana, login_url: publicUrl(grafanaPublicUrl) };
  return NextResponse.json({
    ...fallback,
    grafana: grafanaSnapshot,
    summary: {
      ...fallback.summary,
      grafana_online: grafanaSnapshot.online,
    },
    degraded: true,
    degraded_reasons: [
      "Prometheus is unavailable.",
      ...(!grafanaSnapshot.online ? ["Grafana is unavailable."] : []),
    ],
  });
}
