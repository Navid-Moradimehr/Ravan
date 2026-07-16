import { handleRead, handleReplayMutation, normalizeAction, proxyError } from "../_handlers";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ action?: string }> }) {
  try {
    const { action } = await context.params;
    return await handleRead(normalizeAction(action), request);
  } catch (error) {
    return proxyError(error);
  }
}

export async function POST(request: Request, context: { params: Promise<{ action?: string }> }) {
  const { action } = await context.params;
  if (normalizeAction(action) !== "replay") return new Response(JSON.stringify({ error: "Unknown action" }), { status: 400, headers: { "content-type": "application/json" } });
  try {
    return await handleReplayMutation("POST", request);
  } catch (error) {
    return proxyError(error);
  }
}

export async function DELETE(request: Request, context: { params: Promise<{ action?: string }> }) {
  const { action } = await context.params;
  if (normalizeAction(action) !== "replay") return new Response(JSON.stringify({ error: "Unknown action" }), { status: 400, headers: { "content-type": "application/json" } });
  try {
    return await handleReplayMutation("DELETE", request);
  } catch (error) {
    return proxyError(error);
  }
}
