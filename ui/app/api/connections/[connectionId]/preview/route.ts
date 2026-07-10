import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

export async function POST(request: Request, context: { params: Promise<{ connectionId: string }> }) {
  try {
    const { connectionId } = await context.params;
    const authorization = request.headers.get("authorization");
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/connections/${encodeURIComponent(connectionId)}/preview`, {
      method: "POST",
      headers: authorization ? { Authorization: authorization } : {},
    });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message, details: error.details }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown" }, { status: 502 });
  }
}
