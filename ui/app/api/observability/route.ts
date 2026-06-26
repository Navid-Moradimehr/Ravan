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
  const fallback = createObservabilityFallback();

  const [throughputResult, latencyResult, protocolMixResult, severityResult, dlqResult, batchSizeResult] =
    await Promise.allSettled([
      fetchJson<PrometheusPayload<PrometheusRangeSeries>>(
        queryUrl(
          baseUrl,
          "/api/v1/query_range",
          "sum by (protocol) (rate(edge_ingest_events_total[5m]))",
          { start: windowStart, end: now, step: 300 },
        ),
      ),
      fetchJson<PrometheusPayload<PrometheusRangeSeries>>(
        queryUrl(
          baseUrl,
          "/api/v1/query_range",
          "histogram_quantile(0.95, sum by (le) (rate(ai_gateway_llm_request_seconds_bucket[5m])))",
          { start: windowStart, end: now, step: 300 },
        ),
      ),
      fetchJson<PrometheusPayload<PrometheusInstantSeries>>(
        queryUrl(baseUrl, "/api/v1/query", "sum by (protocol) (edge_ingest_events_total)"),
      ),
      fetchJson<PrometheusPayload<PrometheusInstantSeries>>(
        queryUrl(baseUrl, "/api/v1/query", "sum by (severity) (ai_gateway_batch_severity_total)"),
      ),
      fetchJson<PrometheusPayload<PrometheusInstantSeries>>(
        queryUrl(baseUrl, "/api/v1/query", "sum(edge_ingest_dlq_total)"),
      ),
      fetchJson<PrometheusPayload<PrometheusInstantSeries>>(
        queryUrl(baseUrl, "/api/v1/query", "ai_gateway_batch_size"),
      ),
    ]);
  const batchSize =
    batchSizeResult.status === "fulfilled"
      ? latestValue(batchSizeResult.value.data?.result)
      : Number(fallback.latency[fallback.latency.length - 1]?.batch_size ?? 0);

  const throughput =
    throughputResult.status === "fulfilled"
      ? mergeRangeSeries(throughputResult.value.data?.result ?? [], (metric) => metric.protocol ?? "unknown")
      : fallback.throughput;

  const latency =
    latencyResult.status === "fulfilled"
      ? mergeRangeSeries(latencyResult.value.data?.result ?? [], () => "p95").map((row) => ({
          timestamp: row.timestamp,
          p95: Number(row.p95 ?? 0),
          batch_size: batchSize,
        }))
      : fallback.latency;

  const protocolMix =
    protocolMixResult.status === "fulfilled"
      ? (protocolMixResult.value.data?.result ?? []).map((series) => ({
          protocol: series.metric?.protocol ?? "unknown",
          total: series.value ? Number.parseFloat(series.value[1]) : 0,
        }))
      : fallback.protocolMix;

  const severity =
    severityResult.status === "fulfilled"
      ? (severityResult.value.data?.result ?? []).map((series) => ({
          label: series.metric?.severity ?? "unknown",
          total: series.value ? Number.parseFloat(series.value[1]) : 0,
        }))
      : fallback.severity;

  const summary = {
    total_throughput: latestThroughput(throughput),
    ai_latency_p95:
      latencyResult.status === "fulfilled" ? latestRangeValue(latencyResult.value.data?.result) : fallback.summary.ai_latency_p95,
    dlq_total: dlqResult.status === "fulfilled" ? latestValue(dlqResult.value.data?.result) : fallback.summary.dlq_total,
    grafana_online: true,
  };

  return {
    grafana: {
      online: true,
      status: "online",
      login_url: `${baseUrl.replace(/\/$/, "")}/login`,
    },
    prometheus: {
      online: true,
      status: "online",
    },
    throughput,
    latency,
    protocolMix,
    severity,
    summary,
  };
}

async function fetchGrafanaStatus(baseUrl: string) {
  try {
    const health = await fetchJson<Record<string, string>>(new URL("/api/health", baseUrl).toString());
    return {
      online: true,
      status: health.database === "ok" ? "online" : "degraded",
      login_url: `${baseUrl.replace(/\/$/, "")}/login`,
    };
  } catch {
    return createObservabilityFallback().grafana;
  }
}

export async function GET() {
  const prometheusBaseUrl = process.env.PROMETHEUS_BASE_URL ?? "http://localhost:19090";
  const grafanaBaseUrl = process.env.GRAFANA_BASE_URL ?? "http://localhost:13000";
  const fallback = createObservabilityFallback();

  const [prometheus, grafana] = await Promise.allSettled([
    fetchPrometheusSnapshot(prometheusBaseUrl),
    fetchGrafanaStatus(grafanaBaseUrl),
  ]);

  if (prometheus.status === "fulfilled") {
    return NextResponse.json({
      ...prometheus.value,
      grafana: grafana.status === "fulfilled" ? grafana.value : fallback.grafana,
      summary: {
        ...prometheus.value.summary,
        grafana_online: grafana.status === "fulfilled",
      },
    });
  }

  return NextResponse.json({
    ...fallback,
    grafana: grafana.status === "fulfilled" ? grafana.value : fallback.grafana,
  });
}
