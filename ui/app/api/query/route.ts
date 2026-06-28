import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/historian/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json({ error }, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 502 }
    );
  }
}
