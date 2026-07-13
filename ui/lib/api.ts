import { requestJson } from "@/lib/http";

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

export type AssetTagCatalogItem = {
  site_id: string;
  asset_id: string;
  asset_name: string;
  tag: string;
  tag_id: string;
  unit: string;
  warning_low?: number | null;
  warning_high?: number | null;
  critical_low?: number | null;
  critical_high?: number | null;
  source: "registry" | "observed";
  active: boolean;
};

export type ThresholdPolicy = {
  site_id: string;
  asset_id: string;
  tag: string;
  unit: string;
  mode: "above" | "below" | "outside_range" | "between_range" | "bad_quality";
  warning_low: number | null;
  warning_high: number | null;
  critical_low: number | null;
  critical_high: number | null;
  deadband: number;
  on_delay_seconds: number;
  off_delay_seconds: number;
  enabled: boolean;
  source: string;
  version?: number;
  configured?: boolean;
};

export type ThresholdPolicySyncState = {
  topic: string;
  status: string;
  version: number;
  published: number;
  consumed: number;
  pending_outbox: number;
  last_error: string;
  last_published_at: string | null;
  last_consumed_at: string | null;
  policy_count: number;
};

const DEFAULT_API_WS_BASE_URL = process.env.NEXT_PUBLIC_API_WS_BASE_URL ?? "ws://localhost:8020";

export async function getAssetTagCatalog(): Promise<{ items: AssetTagCatalogItem[] }> {
  return requestJson("/api/metadata/asset-tags");
}

export async function getThresholdPolicies(siteId?: string): Promise<{ policies: ThresholdPolicy[] }> {
  const query = siteId ? `?site_id=${encodeURIComponent(siteId)}` : "";
  return requestJson(`/api/threshold-policies${query}`);
}

export async function saveThresholdPolicy(policy: ThresholdPolicy): Promise<{ ok: boolean; policy: ThresholdPolicy }> {
  return requestJson("/api/threshold-policies", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
}

export async function getThresholdPolicySync(): Promise<ThresholdPolicySyncState> {
  return requestJson("/api/threshold-policies/sync");
}

export type ScenarioInfo = {
  id: string;
  name: string;
  description: string;
};

export type AlarmEvent = {
  time: string;
  asset_id: string;
  tag: string;
  value?: number | null;
  unit?: string | null;
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
  return requestJson(`/api/historian?action=events&table=${encodeURIComponent(table)}&limit=${limit}`);
}

export async function getHistorianTrend(
  assetId: string,
  tag: string,
  hours: number = 1,
): Promise<HistorianTrendPoint[]> {
  return requestJson(
    `/api/historian?action=trend&asset_id=${encodeURIComponent(assetId)}&tag=${encodeURIComponent(tag)}&hours=${hours}`,
  );
}

export async function getAssetHierarchy(): Promise<AssetHierarchyNode[]> {
  return requestJson("/api/historian?action=assets");
}

export async function getScenarios(): Promise<ScenarioInfo[]> {
  return requestJson("/api/historian?action=scenarios");
}

export async function getAlarms(limit: number = 50): Promise<AlarmEvent[]> {
  return requestJson(`/api/historian?action=alarms&limit=${limit}`);
}

export async function getReplayStatus(): Promise<ReplayStatus> {
  return requestJson("/api/historian?action=replay");
}

export async function startReplay(dataset: string, scenario: string): Promise<{ ok: boolean }> {
  return requestJson("/api/historian?action=replay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset, scenario }),
  });
}

export async function stopReplay(): Promise<{ ok: boolean }> {
  return requestJson("/api/historian?action=replay", { method: "DELETE" });
}

export type HistorianStreamPayload = {
  type: "init" | "update" | "heartbeat";
  alarms?: HistorianEvent[];
  events?: HistorianEvent[];
  table?: string;
  timestamp?: string;
};

// WebSocket client for alarms
export function subscribeHistorianStream(
  handlers: {
    onPayload: (payload: HistorianStreamPayload) => void;
    onError?: () => void;
    onConnect?: () => void;
    onDisconnect?: () => void;
  },
  baseUrl: string = DEFAULT_API_WS_BASE_URL,
): () => void {
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const connect = () => {
    if (closed) return;
    try {
      ws = new WebSocket(`${baseUrl}/ws/alarms`);
      ws.onopen = () => {
        handlers.onConnect?.();
      };
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as HistorianStreamPayload;
          handlers.onPayload(payload);
        } catch {
          // ignore malformed
        }
      };
      ws.onerror = () => {
        handlers.onError?.();
      };
      ws.onclose = () => {
        handlers.onDisconnect?.();
        if (!closed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    } catch {
      if (!closed) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    }
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}

// WebSocket client for events
export function subscribeEventsWebSocket(
  handlers: {
    onPayload: (payload: HistorianStreamPayload) => void;
    onError?: () => void;
    onConnect?: () => void;
    onDisconnect?: () => void;
  },
  baseUrl: string = DEFAULT_API_WS_BASE_URL,
): () => void {
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const connect = () => {
    if (closed) return;
    try {
      ws = new WebSocket(`${baseUrl}/ws/events`);
      ws.onopen = () => {
        handlers.onConnect?.();
      };
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as HistorianStreamPayload;
          handlers.onPayload(payload);
        } catch {
          // ignore malformed
        }
      };
      ws.onerror = () => {
        handlers.onError?.();
      };
      ws.onclose = () => {
        handlers.onDisconnect?.();
        if (!closed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    } catch {
      if (!closed) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    }
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}

// WebSocket client for telemetry
export function subscribeTelemetryWebSocket(
  handlers: {
    onPayload: (payload: Telemetry) => void;
    onError?: () => void;
    onConnect?: () => void;
    onDisconnect?: () => void;
  },
  baseUrl: string = DEFAULT_API_WS_BASE_URL,
): () => void {
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const connect = () => {
    if (closed) return;
    try {
      ws = new WebSocket(`${baseUrl}/ws/telemetry`);
      ws.onopen = () => {
        handlers.onConnect?.();
      };
      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === "init" || parsed.type === "update") {
            handlers.onPayload(parsed.telemetry as Telemetry);
          }
        } catch {
          // ignore malformed
        }
      };
      ws.onerror = () => {
        handlers.onError?.();
      };
      ws.onclose = () => {
        handlers.onDisconnect?.();
        if (!closed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    } catch {
      if (!closed) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    }
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
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
      login_url: "http://localhost:13000",
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
  return requestJson(`${baseUrl}/telemetry`);
}

export async function getObservability(): Promise<ObservabilitySnapshot> {
  return requestJson("/api/observability");
}
