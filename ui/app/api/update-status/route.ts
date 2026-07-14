import { NextResponse } from "next/server";
import { HttpError, readResponseError } from "@/lib/http";

export const dynamic = "force-dynamic";

const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://localhost:8020";

export async function GET(request: Request) {
  try {
    const authorization = request.headers.get("authorization");
    const headers = authorization ? { Authorization: authorization } : undefined;
    const response = await fetch(`${API_SERVICE_BASE}/api/v1/system/update-status`, { cache: "no-store", headers });
    if (!response.ok) throw await readResponseError(response);
    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: error.message }, { status: error.status });
    return NextResponse.json({ error: error instanceof Error ? error.message : "Update check unavailable" }, { status: 502 });
  }
}
