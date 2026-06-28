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

export type HistorianEvent = {
  time: string;
  event_id: string;
  source_protocol: string;
  asset_id: string;
  tag: string;
  value: number;
  quality: string;
  unit: string;
  site: string;
  line: string;
  fault_type: string;
  scenario_id: string;
  ground_truth_severity: string;
};

export type HistorianTrendPoint = {
  time: string;
  value: number;
  quality: string;
  fault_type: string;
  ground_truth_severity: string;
};

export type AssetHierarchyNode = {
  id: string;
  name: string;
  type?: string;
  children?: AssetHierarchyNode[];
  tags?: Array<{
    id: string;
    name: string;
    unit: string;
    min: number;
    max: number;
    warning_low: number;
    warning_high: number;
    critical_low: number;
    critical_high: number;
    sampling_rate_hz: number;
  }>;
};

export type ScenarioInfo = {
  id: string;
  name: string;
  description: string;
};

export type AlarmEvent = {
  time: string;
  asset_id: string;
  tag: string;
  severity: string;
  message: string;
  triggered_rules: string[];
  acknowledged: boolean;
};

export type ReplayStatus = {
  running: boolean;
  dataset: string;
  scenario: string;
  progress_percent: number;
  events_emitted: number;
};

export async function getHistorianEvents(table: string, limit: number = 100): Promise<HistorianEvent[]> {
  const response = await fetch(`/api/historian/events?table=${encodeURIComponent(table)}&limit=${limit}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Historian events request failed: ${response.status}`);
  return response.json();
}

export async function getHistorianTrend(
  assetId: string,
  tag: string,
  hours: number = 1,
): Promise<HistorianTrendPoint[]> {
  const response = await fetch(
    `/api/historian/trend?asset_id=${encodeURIComponent(assetId)}&tag=${encodeURIComponent(tag)}&hours=${hours}`,
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error(`Historian trend request failed: ${response.status}`);
  return response.json();
}

export async function getAssetHierarchy(): Promise<AssetHierarchyNode[]> {
  const response = await fetch("/api/historian/assets", { cache: "no-store" });
  if (!response.ok) throw new Error(`Asset hierarchy request failed: ${response.status}`);
  return response.json();
}

export async function getScenarios(): Promise<ScenarioInfo[]> {
  const response = await fetch("/api/historian/scenarios", { cache: "no-store" });
  if (!response.ok) throw new Error(`Scenarios request failed: ${response.status}`);
  return response.json();
}

export async function getAlarms(limit: number = 50): Promise<AlarmEvent[]> {
  const response = await fetch(`/api/historian/alarms?limit=${limit}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Alarms request failed: ${response.status}`);
  return response.json();
}

export async function getReplayStatus(): Promise<ReplayStatus> {
  const response = await fetch("/api/historian/replay", { cache: "no-store" });
  if (!response.ok) throw new Error(`Replay status request failed: ${response.status}`);
  return response.json();
}

export async function startReplay(dataset: string, scenario: string): Promise<{ ok: boolean }> {
  const response = await fetch("/api/historian/replay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset, scenario }),
  });
  if (!response.ok) throw new Error(`Start replay request failed: ${response.status}`);
  return response.json();
}

export async function stopReplay(): Promise<{ ok: boolean }> {
  const response = await fetch("/api/historian/replay", { method: "DELETE" });
  if (!response.ok) throw new Error(`Stop replay request failed: ${response.status}`);
  return response.json();
}

export type HistorianStreamPayload = {
  type: "init" | "update";
  alarms?: HistorianEvent[];
  events?: HistorianEvent[];
  timestamp?: string;
};

export function subscribeHistorianStreamSSE(
  handlers: {
    onPayload: (payload: HistorianStreamPayload) => void;
    onError?: () => void;
  },
  baseUrl: string = "http://localhost:8080",
): () => void {
  const source = new EventSource(`${baseUrl}/historian/stream`);
  source.onmessage = (message) => {
    if (!message.data || message.data.startsWith(":")) return;
    try {
      const payload = JSON.parse(message.data) as HistorianStreamPayload;
      handlers.onPayload(payload);
    } catch {
      // ignore malformed events
    }
  };
  source.onerror = () => {
    handlers.onError?.();
  };
  return () => source.close();
}

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
