import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

function forwardedHeaders(request: Request, includeJson = false): HeadersInit {
  const headers: Record<string, string> = {};
  const authorization = request.headers.get("authorization");
  if (authorization) headers.Authorization = authorization;
  if (includeJson) headers["Content-Type"] = "application/json";
  return headers;
}

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/ai/reports${url.search}`, { cache: "no-store", headers: forwardedHeaders(request) });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
  }
}

export async function POST(request: Request) {
  try {
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/ai/reports/generate`, { method: "POST", headers: forwardedHeaders(request, true), body: JSON.stringify(await request.json()) });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
  }
}
