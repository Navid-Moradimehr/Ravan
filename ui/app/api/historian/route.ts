import { handleRead, handleReplayMutation, normalizeAction, proxyError } from "./_handlers";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return await handleRead(normalizeAction(new URL(request.url).searchParams.get("action") ?? "events"), request);
  } catch (error) {
    return proxyError(error);
  }
}

export async function POST(request: Request) {
  if (normalizeAction(new URL(request.url).searchParams.get("action") ?? "replay") !== "replay") {
    return new Response(JSON.stringify({ error: "Unknown action" }), { status: 400, headers: { "content-type": "application/json" } });
  }
  try {
    return await handleReplayMutation("POST", request);
  } catch (error) {
    return proxyError(error);
  }
}

export async function DELETE(request: Request) {
  if (normalizeAction(new URL(request.url).searchParams.get("action") ?? "replay") !== "replay") {
    return new Response(JSON.stringify({ error: "Unknown action" }), { status: 400, headers: { "content-type": "application/json" } });
  }
  try {
    return await handleReplayMutation("DELETE", request);
  } catch (error) {
    return proxyError(error);
  }
}
