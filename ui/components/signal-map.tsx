import type { PipelineNode } from "@/lib/api";
import { StatusPill } from "@/components/status-pill";

export function SignalMap({ nodes }: { nodes: PipelineNode[] }) {
  return (
    <section aria-labelledby="signal-map-title" className="surface-card rounded-2xl p-5">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 id="signal-map-title" className="text-balance text-lg font-semibold text-primary">
            Signal Map
          </h2>
          <p className="mt-1 max-w-2xl text-pretty text-sm text-secondary">
            Live path from raw events to AI-assisted operational insight.
          </p>
        </div>
      </div>
      <ol className="grid gap-3 md:grid-cols-4">
        {nodes.map((node, index) => (
          <li key={node.name} className="relative rounded-xl border border-border-subtle bg-surface-0 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-xs uppercase text-muted-foreground">0{index + 1}</span>
              <StatusPill status={node.status} />
            </div>
            <div className="mt-5 text-balance text-xl font-semibold capitalize text-primary">{node.name}</div>
            <div className="mt-3 h-1 rounded-full bg-surface-3">
              <div className="h-1 rounded-full bg-accent" style={{ width: node.status === "active" ? "100%" : "45%" }} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
