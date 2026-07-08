import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (!response.ok) {
    throw await readResponseError(response);
  }
  return response.json() as Promise<T>;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const action = searchParams.get("action") ?? "events";

  try {
    switch (action) {
      case "events": {
        const table = searchParams.get("table") ?? "industrial_events";
        const limit = Number(searchParams.get("limit") ?? 100);
        const data = await fetchJson<unknown[]>(
          `${API_SERVICE_BASE}/api/v1/historian/events?table=${encodeURIComponent(table)}&limit=${limit}`,
        );
        return NextResponse.json(data);
      }
      case "trend": {
        const assetId = searchParams.get("asset_id");
        const tag = searchParams.get("tag");
        const hours = Number(searchParams.get("hours") ?? 1);
        if (!assetId || !tag) {
          return NextResponse.json({ error: "asset_id and tag are required" }, { status: 400 });
        }
        const data = await fetchJson<unknown[]>(
          `${API_SERVICE_BASE}/api/v1/historian/trend?asset_id=${encodeURIComponent(assetId)}&tag=${encodeURIComponent(tag)}&hours=${hours}`,
        );
        return NextResponse.json(data);
      }
      case "assets": {
        const data = await fetchJson<unknown[]>(`${API_SERVICE_BASE}/api/v1/assets`);
        return NextResponse.json(data);
      }
      case "scenarios": {
        const data = await fetchJson<unknown[]>(`${API_SERVICE_BASE}/api/v1/scenarios`);
        return NextResponse.json(data);
      }
      case "alarms": {
        const limit = Number(searchParams.get("limit") ?? 50);
        const data = await fetchJson<unknown[]>(`${API_SERVICE_BASE}/api/v1/historian/alarms?limit=${limit}`);
        return NextResponse.json(data);
      }
      case "replay": {
        const data = await fetchJson<unknown>(`${API_SERVICE_BASE}/api/v1/historian/replay`);
        return NextResponse.json(data);
      }
      default:
        return NextResponse.json({ error: "Unknown action" }, { status: 400 });
    }
  } catch (error) {
    if (error instanceof HttpError) {
      return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    }
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
  }
}

export async function POST(request: Request) {
  const { searchParams } = new URL(request.url);
  const action = searchParams.get("action") ?? "replay";

  if (action === "replay") {
    try {
      const body = await request.json();
      const data = await fetchJson<unknown>(`${API_SERVICE_BASE}/api/v1/historian/replay`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return NextResponse.json(data);
    } catch (error) {
      if (error instanceof HttpError) {
        return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
      }
      return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
    }
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const action = searchParams.get("action") ?? "replay";

  if (action === "replay") {
    try {
      const data = await fetchJson<unknown>(`${API_SERVICE_BASE}/api/v1/historian/replay`, { method: "DELETE" });
      return NextResponse.json(data);
  } catch (error) {
      if (error instanceof HttpError) {
        return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
      }
      return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
    }
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
