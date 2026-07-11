import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

function forwardedHeaders(request: Request, contentType = false): HeadersInit {
  const headers: Record<string, string> = {};
  const authorization = request.headers.get("authorization");
  if (authorization) headers.Authorization = authorization;
  if (contentType) headers["Content-Type"] = "application/json";
  return headers;
}

async function forward(
  request: Request,
  context: { params: Promise<{ connectionId: string }> },
  method: "GET" | "PUT" | "DELETE",
) {
  try {
    const { connectionId } = await context.params;
    const body = method === "PUT" ? JSON.stringify(await request.json()) : undefined;
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/connections/${encodeURIComponent(connectionId)}`, {
      method,
      headers: forwardedHeaders(request, method === "PUT"),
      body,
      cache: "no-store",
    });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown" }, { status: 502 });
  }
}

export function GET(request: Request, context: { params: Promise<{ connectionId: string }> }) {
  return forward(request, context, "GET");
}

export function PUT(request: Request, context: { params: Promise<{ connectionId: string }> }) {
  return forward(request, context, "PUT");
}

export function DELETE(request: Request, context: { params: Promise<{ connectionId: string }> }) {
  return forward(request, context, "DELETE");
}
