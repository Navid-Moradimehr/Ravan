import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

function headers(request: Request): HeadersInit {
  const authorization = request.headers.get("authorization");
  return authorization ? { Authorization: authorization } : {};
}

async function forward(request: Request, method: string) {
  const url = new URL(request.url);
  const response = await fetch(`${API_SERVICE_BASE}/api/v1/ai/reporting-policy${url.search}`, {
    method,
    cache: "no-store",
    headers: method === "PUT" ? { "Content-Type": "application/json", ...headers(request) } : headers(request),
    body: method === "PUT" ? JSON.stringify(await request.json()) : undefined,
  });
  if (!response.ok) throw await readResponseError(response);
  return NextResponse.json(await response.json());
}

export async function GET(request: Request) {
  try { return await forward(request, "GET"); }
  catch (error) { return errorResponse(error); }
}

export async function PUT(request: Request) {
  try { return await forward(request, "PUT"); }
  catch (error) { return errorResponse(error); }
}

function errorResponse(error: unknown) {
  if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
  return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
}
