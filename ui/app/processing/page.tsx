"use client";

import { BrainCircuit, Gauge, Workflow } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTelemetryEvents } from "@/lib/useTelemetryEvents";

export default function ProcessingPage() {
  const telemetry = useTelemetryEvents();
  const runtimeMode = telemetry.data?.pipeline?.[2]?.status ?? "starting";

  return (
    <DashboardFrame systemStatus={telemetry.error ? "degraded" : "online"} rightRail={<ProcessingRail runtimeMode={runtimeMode} />}>
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <p className="label-overline">Processing</p>
            <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Runtime processing and enrichment</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This route separates the host Python fallback from the distributed Flink path and shows the observable runtime
              contract behind both.
            </p>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Runtime mode" value={runtimeMode} icon={Workflow} tone="info" />
          <StatCard label="Batch path" value="iot.raw -> iot.processed" icon={Gauge} tone="default" />
          <StatCard label="AI handoff" value="iot.processed -> ai" icon={BrainCircuit} tone="warning" />
          <StatCard label="State model" value="keyed windows" icon={Workflow} tone="default" />
        </section>

        <section className="space-y-4">
          <SectionHeader
            title="Processing runtime"
            eyebrow="Execution"
            description="The current runtime contract stays aligned across Python and Flink."
            icon={Workflow}
          />
          <div className="grid gap-3 md:grid-cols-3">
            {[
              ["Python fallback", "Single-node development and benchmark harness"],
              ["Flink local", "Distributed stateful runtime for plant-local deployments"],
              ["Flink production", "Multi-site mode with checkpointed keyed processing"],
            ].map(([title, desc]) => (
              <Card key={title} className="border-border bg-surface-2">
                <CardHeader>
                  <CardTitle className="text-base">{title}</CardTitle>
                  <CardDescription>{desc}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-text-secondary">
                  Same normalization and scoring contract, different runtime envelope.
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <SectionHeader
            title="Processing outputs"
            eyebrow="Downstream"
            description="What this runtime hands off to the rest of the platform."
            icon={BrainCircuit}
          />
          <div className="grid gap-3 md:grid-cols-3">
            {[
              ["Processed events", "iot.processed", "Events that passed runtime scoring and are ready for historian and AI consumers."],
              ["AI enrichment", "iot.ai_enriched", "Versioned summaries and explanations that downstream consumers can replay."],
              ["Alerts", "Rule and anomaly outputs", "Severity signals that can be turned into alarms or operational notifications."],
            ].map(([title, value, desc]) => (
              <Card key={title} className="border-border bg-surface-2">
                <CardHeader>
                  <CardTitle className="text-base">{title}</CardTitle>
                  <CardDescription>{value}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-text-secondary">{desc}</CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </DashboardFrame>
  );
}

function ProcessingRail({ runtimeMode }: { runtimeMode: string }) {
  return (
    <Card className="app-card overflow-hidden">
      <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
        <CardTitle className="text-base font-semibold">Runtime notes</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
        <p>Use Python fallback to debug logic and Flink to validate distributed behavior.</p>
        <p className="font-mono text-xs text-text-primary">active: {runtimeMode}</p>
      </CardContent>
    </Card>
  );
}
