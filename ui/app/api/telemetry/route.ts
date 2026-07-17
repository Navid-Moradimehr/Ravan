import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";
const AI_GATEWAY_BASE = process.env.AI_GATEWAY_BASE ?? "http://ai-gateway:8080";

export async function GET() {
  try {
    const response = await fetch(`${AI_GATEWAY_BASE}/telemetry`, { cache: "no-store" });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "AI telemetry is unavailable" }, { status: 502 });
  }
}
