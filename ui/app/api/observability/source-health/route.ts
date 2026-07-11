import { NextResponse } from "next/server";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function GET() {
  const data = await fetchJson(`${API_SERVICE_BASE}/api/v1/observability/source-health`);
  return NextResponse.json(data);
}
