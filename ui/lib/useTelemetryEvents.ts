"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { subscribeTelemetryWebSocket, type Telemetry } from "@/lib/api";

export type { PipelineNode, Telemetry } from "@/lib/api";

export function useTelemetryEvents(wsBaseUrl: string = "ws://localhost:8020") {
  const [data, setData] = useState<Telemetry | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const handlePayload = useCallback((payload: Telemetry) => {
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
  }, []);

  useEffect(() => {
    const cleanup = subscribeTelemetryWebSocket(
      {
        onPayload: handlePayload,
        onConnect: () => {
          setIsConnected(true);
          setError(null);
        },
        onDisconnect: () => setIsConnected(false),
        onError: () => {
          setIsConnected(false);
          setError(new Error("WebSocket connection failed"));
        },
      },
      wsBaseUrl
    );
    return () => cleanup();
  }, [handlePayload, wsBaseUrl]);

  return { data, isConnected, error };
}
