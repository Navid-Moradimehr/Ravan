import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";
import { forwardedHeaders } from "@/lib/server-proxy";

export const dynamic = "force-dynamic";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/historian/query`, {
      method: "POST",
      headers: forwardedHeaders(request, true),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await readResponseError(response);
      return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    if (error instanceof HttpError) {
      return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    }
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const queryId = searchParams.get("query_id");
    if (!queryId) {
      return NextResponse.json({ error: "query_id is required" }, { status: 400 });
    }

    const response = await fetch(`${API_SERVICE_BASE}/api/v1/historian/query/${encodeURIComponent(queryId)}`, {
      method: "DELETE",
      headers: forwardedHeaders(request),
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
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 502 });
  }
}
