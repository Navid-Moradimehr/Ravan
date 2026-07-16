import { NextResponse } from "next/server";
import { forwardedHeaders } from "@/lib/server-proxy";

export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const target = new URL("/api/v1/metadata/asset-tags", API_SERVICE_BASE);
  incoming.searchParams.forEach((value, key) => target.searchParams.set(key, value));
  try {
    const response = await fetch(target, { headers: forwardedHeaders(request), cache: "no-store" });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Asset catalog unavailable" }, { status: 502 });
  }
}
