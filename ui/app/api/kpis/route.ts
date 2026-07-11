import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

async function forward(request: Request, method: "GET" | "POST") {
  try {
    const authorization = request.headers.get("authorization");
    const headers: Record<string, string> = {};
    if (authorization) headers.Authorization = authorization;
    if (method === "POST") headers["Content-Type"] = "application/json";
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/kpis`, {
      method,
      headers,
      body: method === "POST" ? JSON.stringify(await request.json()) : undefined,
      cache: "no-store",
    });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown" }, { status: 502 });
  }
}

export function GET(request: Request) { return forward(request, "GET"); }
export function POST(request: Request) { return forward(request, "POST"); }
