import { NextResponse } from "next/server";
export const dynamic = "force-dynamic";
const API_SERVICE_BASE = process.env.API_SERVICE_BASE ?? "http://api-service:8020";
async function forward(request: Request) {
  try { const response = await fetch(new URL("/api/v1/datasets/builds", API_SERVICE_BASE), { method: request.method, headers: { "Content-Type": "application/json" }, body: request.method === "GET" ? undefined : await request.text(), cache: "no-store" }); return NextResponse.json(await response.json(), { status: response.status }); }
  catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Dataset build queue unavailable" }, { status: 502 }); }
}
export async function GET(request: Request) { return forward(request); }
export async function POST(request: Request) { return forward(request); }
