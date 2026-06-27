"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Cable,
  DatabaseZap,
  Gauge,
  HardDrive,
  RadioTower,
  ServerCog,
  ShieldCheck,
  Waves,
  BrainCircuit,
  BarChart3,
  CircuitBoard,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { createObservabilityFallback, getObservability, getTelemetry } from "@/lib/api";
import { TopBar } from "@/components/top-bar";
import { SectionHeader } from "@/components/section-header";
import { HistorianDashboard } from "@/components/historian-views";
import { useTelemetryEvents } from "@/lib/useTelemetryEvents";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ObservabilityPanels } from "@/components/observability-panels";

const sourceHealth = [
  { protocol: "OPC UA", endpoint: "opc.tcp://opcua-sim:4840", status: "active", rate: "3 tags/s", latency: "410 ms" },
  { protocol: "MQTT", endpoint: "factory/+/+/+", status: "active", rate: "25 msg/s", latency: "74 ms" },
  { protocol: "Modbus TCP", endpoint: "modbus-sim:5020", status: "active", rate: "3 regs/s", latency: "190 ms" },
];

const events = [
  { asset: "Pump-01", tag: "Temperature", value: "51.2 °C", protocol: "OPC UA", quality: "good" },
  { asset: "Pump-04", tag: "Vibration", value: "8.8 mm/s", protocol: "MQTT", quality: "good" },
  { asset: "Pump-03", tag: "Pressure", value: "6.4 bar", protocol: "Modbus", quality: "good" },
  { asset: "Pump-07", tag: "Temperature", value: "72.1 °C", protocol: "MQTT", quality: "warning" },
];

const nav = [
  { label: "Overview", href: "#overview" },
  { label: "Pipeline", href: "#pipeline" },
  { label: "Sources", href: "#sources" },
  { label: "AI", href: "#ai" },
  { label: "Observability", href: "#observability" },
  { label: "Historian", href: "#historian" },
];

function statusTone(status: string) {
  if (status === "active") return "border-success/30 bg-success/10 text-success";
  if (status === "degraded" || status === "warning") return "border-warning/30 bg-warning/10 text-warning";
  return "border-error/30 bg-error/10 text-error";
}

export default function Home() {
  const telemetryEvents = useTelemetryEvents();

  const observability = useQuery({
    queryKey: ["observability"],
    queryFn: getObservability,
    refetchInterval: 30000,
  });

  const pipeline = telemetryEvents.data?.pipeline ?? [
    { name: "edge", status: "starting" as const },
    { name: "normalize", status: "starting" as const },
    { name: "process", status: "starting" as const },
    { name: "ai", status: "starting" as const },
  ];
  const observabilitySnapshot = observability.data ?? createObservabilityFallback();
  const systemOnline = !telemetryEvents.error;

  return (
    <div className="industrial-shell min-h-dvh bg-surface-0 text-text-primary">
      <TopBar systemStatus={systemOnline ? "online" : "degraded"} />

      <main className="mx-auto grid max-w-[1560px] gap-5 px-4 py-5 lg:grid-cols-[248px_minmax(0,1fr)_320px]">
        {/* Sidebar */}
        <aside className="panel-rail hidden flex-col rounded-xl p-4 lg:sticky lg:top-[4.5rem] lg:flex lg:h-[calc(100dvh-5.5rem)]">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg border border-accent/40 bg-accent-subtle text-accent">
              <CircuitBoard aria-hidden="true" className="size-5" />
            </span>
            <div className="leading-tight">
              <div className="label-overline">LSE</div>
              <div className="font-heading text-sm font-semibold">Industrial Stream</div>
            </div>
          </div>

          <Separator className="my-4 bg-border-subtle" />

          <nav aria-label="Dashboard sections" className="space-y-1">
            <p className="label-overline mb-2 px-2">Navigate</p>
            {nav.map((item, index) => (
              <a
                key={item.label}
                href={item.href}
                className={`flex h-9 items-center rounded-lg border border-transparent px-3 text-sm font-medium transition-colors ${index === 0 ? "nav-active" : "nav-muted"}`}
              >
                {item.label}
              </a>
            ))}
          </nav>

          <div className="mt-auto rounded-lg border border-border-subtle bg-surface-2 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <ShieldCheck aria-hidden="true" className="size-4 text-success" />
              Hardware-free mode
            </div>
            <p className="mt-2 text-pretty text-xs leading-5 text-text-secondary">
              OPC UA, MQTT, and Modbus are simulated locally so every industrial path is repeatable in test.
            </p>
          </div>
        </aside>

        {/* Main column */}
        <div className="min-w-0 space-y-8">
          {/* Hero */}
          <header className="app-card overflow-hidden">
            <div className="border-b border-border-subtle px-6 py-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-accent/40 bg-accent-subtle text-accent">
                  Edge simulation profile
                </Badge>
                <Badge variant="outline" className={statusTone(!!telemetryEvents.error ? "degraded" : "active")}>
                  {!!telemetryEvents.error ? "Telemetry fallback" : "Telemetry online"}
                </Badge>
              </div>
              <h1 className="mt-4 max-w-2xl text-balance font-heading text-3xl font-semibold leading-tight tracking-tight text-text-primary md:text-4xl">
                Validate plant data before it reaches the plant.
              </h1>
              <p className="mt-3 max-w-2xl text-pretty text-sm leading-6 text-text-secondary md:text-base">
                Validate protocol adapters, normalized events, stream processing, AI enrichment, and observability before
                physical plant integration.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2 bg-surface-0/40 px-6 py-3">
              <a
                href="http://localhost:18080"
                className="action-primary inline-flex h-9 items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors"
              >
                Open Redpanda Console
              </a>
            </div>
          </header>

          {/* Overview KPIs */}
          <section id="overview" aria-label="Key platform indicators" className="space-y-4">
            <SectionHeader
              title="Platform indicators"
              eyebrow="Overview"
              description="Core targets and lanes for the local validation stack."
            />
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Normalized stream" value="industrial.normalized" icon={RadioTower} tone="info" />
              <StatCard label="Burst target" value="1k" unit="msg/s" icon={Activity} tone="default" />
              <StatCard label="Latency budget" value="p95 <500" unit="ms" icon={Gauge} tone="warning" />
              <StatCard label="Exception lane" value="industrial.dlq" icon={AlertTriangle} tone="error" />
            </div>
          </section>

          <Tabs defaultValue="pipeline" className="shell-band rounded-2xl p-4">
            <TabsList className="w-full bg-surface-2">
              <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
              <TabsTrigger value="events">Events</TabsTrigger>
              <TabsTrigger value="tests">Test workflow</TabsTrigger>
            </TabsList>

            <TabsContent value="pipeline" className="mt-4">
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
            </TabsContent>

            <TabsContent value="events" className="mt-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Asset</TableHead>
                    <TableHead>Tag</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Protocol</TableHead>
                    <TableHead>Quality</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => (
                    <TableRow key={`${event.asset}-${event.tag}`}>
                      <TableCell className="font-mono">{event.asset}</TableCell>
                      <TableCell>{event.tag}</TableCell>
                      <TableCell>{event.value}</TableCell>
                      <TableCell>{event.protocol}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={statusTone(event.quality === "good" ? "active" : "warning")}>
                          {event.quality}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>

            <TabsContent value="tests" className="mt-4 grid gap-3 md:grid-cols-3">
              {[
                ["Start sim", "scripts/start-industrial-sim.ps1"],
                ["Soak test", "scripts/edge-soak.ps1 -Seconds 300"],
                ["Unit tests", ".venv\\Scripts\\python.exe -m pytest tests -q"],
              ].map(([label, command]) => (
                <Card key={label} className="border-border bg-surface-2">
                  <CardHeader>
                    <CardTitle>{label}</CardTitle>
                    <CardDescription className="font-mono">{command}</CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </TabsContent>
          </Tabs>

          {/* Sources */}
          <section id="sources" className="space-y-4">
            <SectionHeader
              title="Industrial sources"
              eyebrow="Edge ingest"
              description="Protocol adapters currently active in the simulation."
              icon={Cable}
            />
            <div className="grid gap-4 md:grid-cols-3">
              {sourceHealth.map((source) => (
                <Card key={source.protocol} className="app-card overflow-hidden">
                  <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
                    <CardTitle className="flex items-center justify-between gap-2 text-base font-semibold">
                      <span className="flex items-center gap-2">
                        <Cable aria-hidden="true" className="size-4 text-accent" />
                        {source.protocol}
                      </span>
                      <Badge variant="outline" className={statusTone(source.status)}>
                        <span className="capitalize">{source.status}</span>
                      </Badge>
                    </CardTitle>
                    <CardDescription className="font-mono text-xs text-text-muted">{source.endpoint}</CardDescription>
                  </CardHeader>
                  <CardContent className="grid grid-cols-2 gap-3 p-4 text-sm">
                    <div>
                      <div className="label-overline">Rate</div>
                      <div className="mt-1 font-mono text-xs text-text-primary">{source.rate}</div>
                    </div>
                    <div>
                      <div className="label-overline">Latency</div>
                      <div className="mt-1 font-mono text-xs text-text-primary">{source.latency}</div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          {/* Observability */}
         <ObservabilityPanels snapshot={observabilitySnapshot} />

         {/* Historian */}
         <section id="historian" className="scroll-mt-24">
           <SectionHeader title="Historian" icon={DatabaseZap}>
             <p className="max-w-[720px] text-pretty text-sm leading-6 text-text-secondary">
               Time-series storage, asset trends, and ground-truth scenario replay.
             </p>
           </SectionHeader>
           <HistorianDashboard />
         </section>
        </div>

        {/* Right rail */}
        <aside className="space-y-4">
          {/* AI Gateway removed — now event-driven via SSE in telemetry hook */}

          <Card className="app-card overflow-hidden">
            <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <HardDrive aria-hidden="true" className="size-4 text-accent" />
                Current Test Stack
              </CardTitle>
              <CardDescription className="text-text-secondary">Local, repeatable, hardware-free validation</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5 p-4 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">Protocols</span>
                <span className="font-mono text-xs text-text-primary">3 active</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">Broker</span>
                <span className="font-mono text-xs text-text-primary">Redpanda</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-secondary">AI endpoint</span>
                <span className="font-mono text-xs text-text-primary">LM Studio</span>
              </div>
            </CardContent>
          </Card>

          <Card id="operator-links" className="app-card overflow-hidden">
            <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <BarChart3 aria-hidden="true" className="size-4 text-accent" />
                Operator Links
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-1.5 p-3">
              {[
                ["Grafana", "http://localhost:13000/login", Waves],
                ["Prometheus", "http://localhost:19090", Activity],
                ["Edge Metrics", "http://localhost:8090", ServerCog],
                ["AI Health", "http://localhost:8080/health", BrainCircuit],
                ["Postgres CDC", "http://localhost:18083", DatabaseZap],
              ].map(([label, href, Icon]) => {
                const IconCmp = Icon as typeof Waves;
                return (
                  <a
                    key={href as string}
                    href={href as string}
                    className="action-secondary inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium transition-colors"
                  >
                    <IconCmp aria-hidden="true" className="mr-2 size-4 text-text-secondary" />
                    {label as string}
                  </a>
                );
              })}
            </CardContent>
          </Card>
        </aside>
      </main>
    </div>
  );
}
