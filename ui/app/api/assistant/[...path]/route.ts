import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

function headersFor(request: Request, json = false): HeadersInit {
  const headers: Record<string, string> = {};
  const authorization = request.headers.get("authorization");
  if (authorization) headers.Authorization = authorization;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function forward(request: Request, path: string) {
  try {
    const isVoice = path === "voice/transcribe";
    const body = request.method === "GET" || request.method === "HEAD"
      ? undefined
      : isVoice
        ? await request.arrayBuffer()
        : await request.text();
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/assistant/${path}${new URL(request.url).search}`, {
      method: request.method,
      cache: "no-store",
      headers: isVoice ? { ...headersFor(request), "Content-Type": request.headers.get("content-type") ?? "audio/webm" } : headersFor(request, Boolean(body)),
      body: body || undefined,
    });
    if (!response.ok) throw await readResponseError(response);
    if (path.endsWith("/stream") || path.endsWith("/events")) {
      return new Response(response.body, {
        status: response.status,
        headers: {
          "Content-Type": response.headers.get("content-type") ?? "text/event-stream",
          "Cache-Control": "no-cache",
        },
      });
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.startsWith("audio/") || contentType === "application/octet-stream") {
      return new Response(response.body, {
        status: response.status,
        headers: { "Content-Type": contentType },
      });
    }
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Assistant service unavailable" }, { status: 502 });
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, context: RouteContext) {
  return forward(request, (await context.params).path.join("/"));
}

export async function POST(request: Request, context: RouteContext) {
  return forward(request, (await context.params).path.join("/"));
}

export async function DELETE(request: Request, context: RouteContext) {
  return forward(request, (await context.params).path.join("/"));
}

export async function PATCH(request: Request, context: RouteContext) {
  return forward(request, (await context.params).path.join("/"));
}
