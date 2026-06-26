"use client";

import { useEffect, useRef, useState, useCallback } from "react";

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

export function useTelemetryEvents(baseUrl: string = "http://localhost:8080") {
  const [data, setData] = useState<Telemetry | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`${baseUrl}/events`);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onmessage = (event) => {
      if (!event.data || event.data.startsWith(":")) {
        return; // heartbeat or empty
      }
      try {
        const payload = JSON.parse(event.data) as Telemetry;
        setData((prev) => {
          // Only update if data actually changed
          if (
            prev &&
            prev.llm.model === payload.llm.model &&
            prev.llm.base_url === payload.llm.base_url &&
            prev.llm.last_error === payload.llm.last_error &&
            JSON.stringify(prev.pipeline) === JSON.stringify(payload.pipeline)
          ) {
            return prev;
          }
          return payload;
        });
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setIsConnected(false);
      setError(new Error("EventSource connection failed"));
      es.close();
      // Auto-reconnect after 3s
      setTimeout(() => connect(), 3000);
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [baseUrl]);

  useEffect(() => {
    const cleanup = connect();
    return () => {
      cleanup?.();
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [connect]);

  return { data, isConnected, error };
}
