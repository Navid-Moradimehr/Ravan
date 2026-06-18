export type PipelineNode = {
  name: string;
  status: "active" | "starting" | "degraded" | "offline";
};

export type Telemetry = {
  pipeline: PipelineNode[];
  llm: {
    model: string;
    base_url: string;
    last_error: string | null;
  };
};

export async function getTelemetry(): Promise<Telemetry> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
  const response = await fetch(`${baseUrl}/telemetry`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Telemetry request failed: ${response.status}`);
  }

  return response.json();
}
