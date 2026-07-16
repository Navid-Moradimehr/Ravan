import { NextResponse } from "next/server";
import { forwardedHeaders } from "@/lib/server-proxy";
export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";
export async function POST(request: Request) {
  try { const response = await fetch(new URL("/api/v1/datasets/manifests/validate", API_SERVICE_BASE), { method: "POST", headers: forwardedHeaders(request, true), body: await request.text(), cache: "no-store" }); return NextResponse.json(await response.json(), { status: response.status }); }
  catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Dataset validation unavailable" }, { status: 502 }); }
}
