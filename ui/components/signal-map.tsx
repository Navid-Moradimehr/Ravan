import type { PipelineNode } from "@/lib/api";
import { SectionHeader } from "@/components/section-header";
import { StatusPill } from "@/components/status-pill";

const nodeDescriptions: Record<string, string> = {
  edge: "Industrial protocols ingested at the edge.",
  normalize: "Raw payloads validated into typed envelopes.",
  process: "Stateful processing and enrichment.",
  ai: "AI-assisted operational insight.",
};

export function SignalMap({ nodes }: { nodes: PipelineNode[] }) {
  return (
    <section aria-labelledby="signal-map-title" className="surface-card rounded-xl p-5">
      <SectionHeader
        title="Signal Map"
        eyebrow="Pipeline"
        description="Live path from raw events to AI-assisted operational insight."
      />
      <ol className="mt-5 grid gap-3 md:grid-cols-4">
        {nodes.map((node, index) => (
          <li
            key={node.name}
            className="relative flex flex-col gap-3 rounded-lg border border-border-subtle bg-surface-0 p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="label-overline">Stage {String(index + 1).padStart(2, "0")}</span>
              <StatusPill status={node.status} />
            </div>
            <div className="mt-1">
              <h3 className="font-heading text-base font-semibold capitalize text-text-primary">{node.name}</h3>
              <p className="mt-1 text-xs leading-5 text-text-secondary">
                {nodeDescriptions[node.name] ?? "Pipeline stage."}
              </p>
            </div>
            <div className="mt-auto h-1 overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full bg-accent transition-all duration-300"
                style={{ width: node.status === "active" ? "100%" : node.status === "starting" ? "45%" : "12%" }}
              />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
