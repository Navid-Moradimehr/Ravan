import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";

async function forward(request: Request) {
  try {
    const incoming = new URL(request.url);
    const target = new URL("/api/v1/metadata/threshold-policies", API_SERVICE_BASE);
    incoming.searchParams.forEach((value, key) => target.searchParams.set(key, value));
    const response = await fetch(target, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Threshold policy service unavailable" }, { status: 502 });
  }
}

export async function GET(request: Request) { return forward(request); }
export async function PUT(request: Request) { return forward(request); }
