"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge, RadioTower } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { ObservabilityPanels } from "@/components/observability-panels";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createObservabilityFallback, getObservability } from "@/lib/api";
import { AlertTriangle } from "lucide-react";
import { LatestAIBriefing } from "@/components/latest-ai-briefing";

export default function ObservabilityPage() {
  const observability = useQuery({
    queryKey: ["observability"],
    queryFn: getObservability,
    refetchInterval: 30000,
  });
  const snapshot = observability.data ?? createObservabilityFallback();
  const isDegraded = observability.isError || Boolean(snapshot.degraded);

  return (
    <DashboardFrame systemStatus={isDegraded ? "degraded" : "online"} rightRail={<ObservabilityRail />}>
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <p className="label-overline">Observability</p>
            <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Health, latency, and throughput</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This route keeps the dense operational signals together instead of scattering them across the landing page.
            </p>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Ingest throughput" value={String(snapshot.summary.total_throughput ?? 0)} unit="events/s" icon={Gauge} tone="default" />
          <StatCard label="AI latency" value={String(snapshot.summary.ai_latency_p95 ?? 0)} unit="s" icon={RadioTower} tone="warning" />
          <StatCard label="DLQ total" value={String(snapshot.summary.dlq_total ?? 0)} icon={Gauge} tone="error" />
          <StatCard label="Prometheus" value={String(snapshot.prometheus?.status ?? "unknown")} icon={Gauge} tone="info" />
        </section>

        {isDegraded ? (
          <Card className="app-card overflow-hidden border-warning/30 bg-warning/5">
            <CardContent className="flex items-start gap-3 p-4">
              <AlertTriangle className="mt-0.5 size-4 text-warning" />
              <div className="space-y-1">
                <p className="text-sm font-semibold text-text-primary">Live observability is degraded</p>
                <p className="text-sm leading-6 text-text-secondary">
                  {observability.isError
                    ? "The page is rendering a fallback snapshot because the observability gateway is unavailable."
                    : "One or more observability dependencies are unavailable; affected panels are shown empty rather than as live-looking data."}
                </p>
                {snapshot.degraded_reasons?.length ? (
                  <ul className="list-disc space-y-1 pl-5 text-xs text-text-secondary">
                    {snapshot.degraded_reasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : null}

        <LatestAIBriefing reportType="anomaly" title="Latest anomaly briefing" />

        <SectionHeader
          title="Observability panels"
          eyebrow="Signals"
          description="Throughput, protocol mix, severity mix, and service health."
          icon={Gauge}
        />
        <ObservabilityPanels snapshot={snapshot} />
      </div>
    </DashboardFrame>
  );
}

function ObservabilityRail() {
  return (
    <Card className="app-card overflow-hidden">
      <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
        <CardTitle className="text-base font-semibold">Signal sources</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
        <p>Prometheus, AI gateway telemetry, edge metrics, and historian state feed this page.</p>
        <p>The page is intentionally broader than a single service dashboard.</p>
      </CardContent>
    </Card>
  );
}
