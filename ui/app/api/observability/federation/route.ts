import { NextResponse } from "next/server";
import { forwardedHeaders } from "@/lib/server-proxy";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  const response = await fetch(`${API_SERVICE_BASE}/api/v1/observability/federation`, { headers: forwardedHeaders(request), cache: "no-store" });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}
