import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

export async function GET() {
  try {
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/notifications`, { cache: "no-store" });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) {
      return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    }
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown" }, { status: 502 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/notifications`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(request.headers.get("authorization") ? { Authorization: request.headers.get("authorization")! } : {}) },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await readResponseError(response);
      return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) {
      return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    }
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown" }, { status: 502 });
  }
}
