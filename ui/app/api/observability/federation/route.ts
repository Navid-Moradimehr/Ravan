import { NextResponse } from "next/server";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  const response = await fetch(`${API_SERVICE_BASE}/api/v1/observability/federation`, { cache: "no-store" });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}
