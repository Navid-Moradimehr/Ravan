import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";
import { forwardedHeaders } from "@/lib/server-proxy";

export const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (!response.ok) throw await readResponseError(response);
  return response.json() as Promise<T>;
}

export function normalizeAction(action: string | null | undefined): string {
  return (action ?? "").trim().toLowerCase();
}

export async function handleRead(action: string, request: Request) {
  const { searchParams } = new URL(request.url);
  const headers = forwardedHeaders(request);
  switch (action) {
    case "events": {
      const table = searchParams.get("table") ?? "industrial_events";
      const limit = Number(searchParams.get("limit") ?? 100);
      return NextResponse.json(await fetchJson<unknown[]>(
        `${API_SERVICE_BASE}/api/v1/historian/events?table=${encodeURIComponent(table)}&limit=${limit}`,
        { headers },
      ));
    }
    case "trend": {
      const assetId = searchParams.get("asset_id");
      const tag = searchParams.get("tag");
      const siteId = searchParams.get("site_id");
      const hours = Number(searchParams.get("hours") ?? 1);
      if (!assetId || !tag) return NextResponse.json({ error: "asset_id and tag are required" }, { status: 400 });
      return NextResponse.json(await fetchJson<unknown[]>(
        `${API_SERVICE_BASE}/api/v1/historian/trend?asset_id=${encodeURIComponent(assetId)}&tag=${encodeURIComponent(tag)}&hours=${hours}${siteId ? `&site_id=${encodeURIComponent(siteId)}` : ""}`,
        { headers },
      ));
    }
    case "assets":
      return NextResponse.json(await fetchJson<unknown[]>(`${API_SERVICE_BASE}/api/v1/assets`, { headers }));
    case "scenarios":
      return NextResponse.json(await fetchJson<unknown[]>(`${API_SERVICE_BASE}/api/v1/scenarios`, { headers }));
    case "alarms": {
      const limit = Number(searchParams.get("limit") ?? 50);
      return NextResponse.json(await fetchJson<unknown[]>(`${API_SERVICE_BASE}/api/v1/historian/alarms?limit=${limit}`, { headers }));
    }
    case "replay":
      return NextResponse.json(await fetchJson<unknown>(`${API_SERVICE_BASE}/api/v1/historian/replay`, { headers }));
    default:
      return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  }
}

export async function handleReplayMutation(method: "POST" | "DELETE", request: Request) {
  const init: RequestInit = { method, headers: forwardedHeaders(request, method === "POST") };
  if (method === "POST") init.body = JSON.stringify(await request.json());
  return NextResponse.json(await fetchJson<unknown>(`${API_SERVICE_BASE}/api/v1/historian/replay`, init));
}

export function proxyError(error: unknown) {
  if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
  return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
}
