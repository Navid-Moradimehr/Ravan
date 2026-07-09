"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, BarChart3, Cable, DatabaseZap, Gauge, HardDrive, HelpCircle, Workflow } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createObservabilityFallback, getObservability } from "@/lib/api";
import { useTelemetryEvents } from "@/lib/useTelemetryEvents";

const quickRoutes = [
  {
    href: "/pipeline",
    title: "Pipeline",
    description: "Ingress, normalization, DLQ, and event preview.",
    icon: Cable,
  },
  {
    href: "/processing",
    title: "Processing",
    description: "Python fallback, Flink runtime, and benchmark paths.",
    icon: Workflow,
  },
  {
    href: "/historian",
    title: "Historian",
    description: "SQL, backup, replay, webhooks, and dashboards.",
    icon: DatabaseZap,
  },
  {
    href: "/observability",
    title: "Observability",
    description: "Throughput, latency, reconnects, and health.",
    icon: Gauge,
  },
];

function statusTone(status: string) {
  if (status === "active" || status === "online") return "border-success/30 bg-success/10 text-success";
  if (status === "degraded" || status === "warning") return "border-warning/30 bg-warning/10 text-warning";
  return "border-error/30 bg-error/10 text-error";
}

export default function Home() {
  const telemetryEvents = useTelemetryEvents();
  const observability = useQuery({
    queryKey: ["observability"],
    queryFn: getObservability,
    refetchInterval: 60000,
  });

  const telemetrySourceLabel = telemetryEvents.data
    ? "Live telemetry stream"
    : telemetryEvents.isConnected
      ? "Telemetry connected, awaiting payload"
      : "Demo fallback telemetry";
  const observabilitySourceLabel =
    observability.data && (observability.data.prometheus.online || observability.data.grafana.online)
      ? "Live observability snapshot"
      : "Demo fallback snapshot";

  const pipeline = telemetryEvents.data?.pipeline ?? [
    { name: "edge", status: "starting" as const },
    { name: "normalize", status: "starting" as const },
    { name: "process", status: "starting" as const },
    { name: "ai", status: "starting" as const },
  ];
  const observabilitySnapshot = observability.data ?? createObservabilityFallback();
  const systemOnline = !telemetryEvents.error;
  const aiStatus = telemetryEvents.data?.llm?.last_error ? "degraded" : systemOnline ? "online" : "offline";

  return (
    <DashboardFrame
      systemStatus={systemOnline ? "online" : "degraded"}
      rightRail={
        <>
          <Card className="app-card overflow-hidden">
            <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <HardDrive aria-hidden="true" className="size-4 text-accent" />
                Current Stack
              </CardTitle>
              <CardDescription className="text-text-secondary">Kafka-native, simulator-first, single-tenant safe</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5 p-4 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">Broker</span>
                <span className="font-mono text-xs text-text-primary">Kafka</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">Processor</span>
                <span className="font-mono text-xs text-text-primary">Python + Flink</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">AI endpoint</span>
                <span className="font-mono text-xs text-text-primary">LM Studio</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">Storage</span>
                <span className="font-mono text-xs text-text-primary">TimescaleDB</span>
              </div>
            </CardContent>
          </Card>

          <Card className="app-card overflow-hidden">
            <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <BarChart3 aria-hidden="true" className="size-4 text-accent" />
                Operator Links
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-1.5 p-3">
              {[ 
                ["Kafka UI", "http://localhost:18080"],
                ["Grafana", "http://localhost:13000"],
                ["Prometheus", "http://localhost:19090"],
                ["Edge Metrics", "http://localhost:8090"],
                ["AI Health", "http://localhost:8080/health"],
              ].map(([label, href]) => (
                <Link
                  key={href}
                  href={href}
                  className="action-secondary inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium transition-colors"
                >
                  <ArrowRight aria-hidden="true" className="mr-2 size-4 text-text-secondary" />
                  {label}
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card className="app-card overflow-hidden">
            <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <HelpCircle aria-hidden="true" className="size-4 text-accent" />
                Kafka UI
              </CardTitle>
              <CardDescription className="text-text-secondary">What the broker console is for and how to read it.</CardDescription>
            </CardHeader>
            <CardContent className="p-4">
              <Tabs defaultValue="about" className="gap-3">
                <TabsList variant="line" className="w-full justify-start border-b border-border-subtle pb-1">
                  <TabsTrigger value="about">About</TabsTrigger>
                  <TabsTrigger value="use">How to use</TabsTrigger>
                </TabsList>
                <TabsContent value="about" className="space-y-2 pt-3 text-sm leading-6 text-text-secondary">
                  <p>
                    Kafka UI is the broker inspection console. It shows the topics, messages, partitions, and consumer groups that sit
                    behind the platform's event stream.
                  </p>
                  <p>
                    In this stack it is not a design surface and not a data-entry form. It is the place where operators verify that
                    events are moving through Kafka correctly.
                  </p>
                </TabsContent>
                <TabsContent value="use" className="space-y-2 pt-3 text-sm leading-6 text-text-secondary">
                  <p>
                    Open a topic to inspect the messages it contains, check whether the topic is filling up, and confirm that the
                    processor or historian consumers are keeping up.
                  </p>
                  <p>
                    Start with the canonical streams: <span className="font-mono text-text-primary">industrial.raw</span>,
                    <span className="font-mono text-text-primary"> industrial.normalized</span>, and{" "}
                    <span className="font-mono text-text-primary">iot.processed</span>. If a topic stays empty, the ingestion path or
                    simulator is not producing data yet.
                  </p>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </>
      }
    >
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="border-accent/40 bg-accent-subtle text-accent">
                Kafka control plane
              </Badge>
              <Badge variant="outline" className={statusTone(aiStatus)}>
                {aiStatus === "online" ? "Telemetry online" : aiStatus === "degraded" ? "Telemetry degraded" : "Telemetry offline"}
              </Badge>
            </div>
            <h1 className="mt-4 max-w-2xl text-balance font-heading text-3xl font-semibold leading-tight tracking-tight text-text-primary md:text-4xl">
              Industrial streaming command center
            </h1>
            <p className="mt-3 max-w-2xl text-pretty text-sm leading-6 text-text-secondary md:text-base">
              The landing page keeps a concise operational overview while detailed pipeline, historian, and integration views live on
              their own routes.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 bg-surface-0/40 px-6 py-3">
            <Link
              href="/pipeline"
              className="action-primary inline-flex h-9 items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors"
            >
              Open pipeline view
            </Link>
            <Link
              href="/historian"
              className="action-secondary inline-flex h-9 items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors"
            >
              Open historian tools
            </Link>
          </div>
        </header>

        <section className="space-y-4">
          <SectionHeader
            title="Execution lanes"
            eyebrow="Navigation"
            description="Each major operational area now has a dedicated route."
          />
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {quickRoutes.map((route) => {
              const Icon = route.icon;
              return (
                <Link key={route.href} href={route.href} className="group">
                  <Card className="h-full border-border bg-surface-2 transition-colors hover:border-accent/40">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <span className="flex size-8 items-center justify-center rounded-lg border border-border-subtle bg-surface-0 text-accent">
                          <Icon aria-hidden="true" className="size-4" />
                        </span>
                        {route.title}
                      </CardTitle>
                      <CardDescription>{route.description}</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-text-secondary">
                      <span className="inline-flex items-center gap-2 font-medium text-text-primary">
                        Open route
                        <ArrowRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1" />
                      </span>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="space-y-4">
          <SectionHeader
            title="Live pipeline summary"
            eyebrow="Telemetry"
            description="The home page keeps a concise readout of the active pipeline without absorbing the detailed screens."
          />
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-accent/40 bg-accent-subtle text-accent">
              {telemetrySourceLabel}
            </Badge>
            <Badge variant="outline" className={statusTone(aiStatus)}>
              {aiStatus === "online" ? "Telemetry online" : aiStatus === "degraded" ? "Telemetry degraded" : "Telemetry offline"}
            </Badge>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            {pipeline.map((node, index) => (
              <Card key={node.name} className="border-border bg-surface-2">
                <CardHeader>
                  <CardDescription>Stage {index + 1}</CardDescription>
                  <CardTitle className="capitalize text-base md:text-lg">{node.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge variant="outline" className={statusTone(node.status)}>
                    {node.status}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <SectionHeader
            title="Current health snapshot"
            eyebrow="Observability"
            description="This mirrors the active service state without turning the home page into a metrics wall."
          />
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-accent/40 bg-accent-subtle text-accent">
              {observabilitySourceLabel}
            </Badge>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Grafana" value={String(observabilitySnapshot.grafana?.status ?? "unknown")} icon={BarChart3} tone="default" />
            <StatCard label="Prometheus" value={String(observabilitySnapshot.prometheus?.status ?? "unknown")} icon={Gauge} tone="default" />
            <StatCard
              label="Throughput"
              value={String(Math.round(observabilitySnapshot.summary?.total_throughput ?? 0))}
              unit="/s"
              icon={Activity}
              tone="info"
            />
            <StatCard
              label="AI p95"
              value={String(observabilitySnapshot.summary?.ai_latency_p95 ?? 0)}
              unit="s"
              icon={Workflow}
              tone="warning"
            />
          </div>
        </section>
      </div>
    </DashboardFrame>
  );
}
