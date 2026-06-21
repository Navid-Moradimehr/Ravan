export type PipelineNode = {
  name: string;
  status: "active" | "starting" | "degraded" | "offline";
};

export type Telemetry = {
  pipeline: PipelineNode[];
  llm: {
    model: string;
    base_url: string;
    last_error: string | null;
  };
};

export type ObservabilityPoint = {
  timestamp: string;
  [key: string]: number | string;
};

export type ObservabilitySnapshot = {
  grafana: {
    online: boolean;
    status: string;
    login_url: string;
  };
  prometheus: {
    online: boolean;
    status: string;
  };
  throughput: ObservabilityPoint[];
  latency: ObservabilityPoint[];
  protocolMix: Array<{ protocol: string; total: number }>;
  severity: Array<{ label: string; total: number }>;
  summary: {
    total_throughput: number;
    ai_latency_p95: number;
    dlq_total: number;
    grafana_online: boolean;
  };
};

export function createObservabilityFallback(): ObservabilitySnapshot {
  const timestamps = Array.from({ length: 6 }, (_, index) => {
    const date = new Date(Date.now() - (5 - index) * 5 * 60 * 1000);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });

  return {
    grafana: {
      online: false,
      status: "offline",
      login_url: "http://localhost:13000/login",
    },
    prometheus: {
      online: false,
      status: "offline",
    },
    throughput: timestamps.map((timestamp, index) => ({
      timestamp,
      mqtt: 20 + index * 2,
      opcua: 4 + (index % 2),
      modbus: 3,
    })),
    latency: timestamps.map((timestamp, index) => ({
      timestamp,
      p95: 0.18 + index * 0.03,
      batch_size: 48 + index * 4,
    })),
    protocolMix: [
      { protocol: "mqtt", total: 1200 },
      { protocol: "opcua", total: 180 },
      { protocol: "modbus", total: 180 },
    ],
    severity: [
      { label: "normal", total: 240 },
      { label: "warning", total: 36 },
      { label: "critical", total: 4 },
    ],
    summary: {
      total_throughput: 26,
      ai_latency_p95: 0.31,
      dlq_total: 0,
      grafana_online: false,
    },
  };
}

export async function getTelemetry(): Promise<Telemetry> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
  const response = await fetch(`${baseUrl}/telemetry`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Telemetry request failed: ${response.status}`);
  }

  return response.json();
}

export async function getObservability(): Promise<ObservabilitySnapshot> {
  const response = await fetch("/api/observability", { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Observability request failed: ${response.status}`);
  }

  return response.json();
}
