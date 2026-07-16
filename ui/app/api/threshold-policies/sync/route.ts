import { NextResponse } from "next/server";
import { forwardedHeaders } from "@/lib/server-proxy";

export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

export async function GET(request: Request) {
  try {
    const target = new URL("/api/v1/metadata/threshold-policies/sync", API_SERVICE_BASE);
    const response = await fetch(target, { headers: forwardedHeaders(request), cache: "no-store" });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Threshold policy sync unavailable" },
      { status: 502 },
    );
  }
}
