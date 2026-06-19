"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  Cable,
  DatabaseZap,
  Factory,
  Gauge,
  RadioTower,
  ServerCog,
  ShieldCheck,
  Waves,
} from "lucide-react";
import { getTelemetry } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const sourceHealth = [
  { protocol: "OPC UA", endpoint: "opc.tcp://opcua-sim:4840", status: "active", rate: "3 tags/s", latency: "410 ms" },
  { protocol: "MQTT", endpoint: "factory/+/+/+", status: "active", rate: "25 msg/s", latency: "74 ms" },
  { protocol: "Modbus TCP", endpoint: "modbus-sim:5020", status: "active", rate: "3 regs/s", latency: "190 ms" },
];

const events = [
  { asset: "Pump-01", tag: "Temperature", value: "51.2 c", protocol: "OPC UA", quality: "good" },
  { asset: "Pump-04", tag: "Vibration", value: "8.8 mm/s", protocol: "MQTT", quality: "good" },
  { asset: "Pump-03", tag: "Pressure", value: "6.4 bar", protocol: "Modbus", quality: "good" },
  { asset: "Pump-07", tag: "Temperature", value: "72.1 c", protocol: "MQTT", quality: "warning" },
];

const nav = ["Overview", "Sources", "Events", "AI", "Observability"];

function statusTone(status: string) {
  if (status === "active") return "border-success/30 bg-success/10 text-success";
  if (status === "degraded" || status === "warning") return "border-warning/30 bg-warning/10 text-warning";
  return "border-error/30 bg-error/10 text-error";
}

export default function Home() {
  const telemetry = useQuery({
    queryKey: ["telemetry"],
    queryFn: getTelemetry,
    refetchInterval: 5000,
  });

  const pipeline = telemetry.data?.pipeline ?? [
    { name: "edge", status: "starting" as const },
    { name: "normalize", status: "starting" as const },
    { name: "process", status: "starting" as const },
    { name: "ai", status: "starting" as const },
  ];

  return (
    <main className="industrial-grid min-h-dvh bg-surface-0 text-primary">
      <div className="mx-auto grid max-w-[1560px] gap-4 px-4 py-4 lg:grid-cols-[248px_minmax(0,1fr)_320px]">
        <aside className="surface-card hidden rounded-2xl p-4 lg:sticky lg:top-4 lg:block lg:h-[calc(100dvh-2rem)]">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl border border-accent/30 bg-accent-subtle">
              <Factory aria-hidden="true" className="size-5 text-accent" />
            </div>
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.24em] text-accent">LSE</div>
              <div className="text-sm font-semibold">Industrial Stream</div>
            </div>
          </div>
          <Separator className="my-5 bg-border" />
          <nav aria-label="Dashboard sections" className="space-y-1">
            {nav.map((item, index) => (
              <a
                key={item}
                href={`#${item.toLowerCase()}`}
                className={`flex min-h-11 items-center rounded-xl px-3 text-sm transition-colors hover:bg-surface-2 ${
                  index === 0 ? "bg-surface-2 text-primary" : "text-secondary"
                }`}
              >
                {item}
              </a>
            ))}
          </nav>
          <div className="mt-6 rounded-xl border border-border-subtle bg-surface-2 p-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <ShieldCheck aria-hidden="true" className="size-4 text-success" />
              Hardware-free mode
            </div>
            <p className="mt-2 text-xs leading-5 text-secondary">
              OPC UA, MQTT, and Modbus are simulated locally so every industrial path is repeatable in tests.
            </p>
          </div>
        </aside>

        <section className="space-y-4">
          <header className="surface-card rounded-2xl p-5">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="border-accent/40 bg-accent-subtle text-accent">
                    Edge simulation profile
                  </Badge>
                  <Badge variant="outline" className={statusTone(telemetry.isError ? "degraded" : "active")}>
                    {telemetry.isError ? "Telemetry fallback" : "Telemetry online"}
                  </Badge>
                </div>
                <h1 className="mt-4 max-w-4xl text-balance text-4xl font-semibold tracking-[-0.04em] md:text-6xl">
                  Industrial data command center.
                </h1>
                <p className="mt-4 max-w-3xl text-pretty text-base leading-7 text-secondary">
                  Validate protocol adapters, normalized events, stream processing, AI enrichment, and observability before
                  any physical plant integration.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <ThemeToggle />
                <a href="http://localhost:18080" className={cn(buttonVariants({ size: "lg" }), "min-h-11 cursor-pointer")}>
                  Open Redpanda Console
                </a>
              </div>
            </div>
          </header>

          <section id="overview" aria-label="Key platform indicators" className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "Normalized topic", value: "industrial.normalized", icon: RadioTower },
              { label: "Burst target", value: "1k msg/s", icon: Activity },
              { label: "Latency budget", value: "p95 <500 ms", icon: Gauge },
              { label: "DLQ capture", value: "100%", icon: AlertTriangle },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <Card key={item.label} className="surface-card border-border bg-surface-1">
                  <CardHeader>
                    <Icon aria-hidden="true" className="size-5 text-accent" />
                    <CardDescription>{item.label}</CardDescription>
                    <CardTitle className="font-mono text-xl">{item.value}</CardTitle>
                  </CardHeader>
                </Card>
              );
            })}
          </section>

          <Tabs defaultValue="pipeline" className="surface-card rounded-2xl p-4">
            <TabsList className="bg-surface-2">
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
                      <CardTitle className="capitalize">{node.name}</CardTitle>
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

          <section id="sources" className="grid gap-4 xl:grid-cols-3">
            {sourceHealth.map((source) => (
              <Card key={source.protocol} className="surface-card border-border bg-surface-1">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Cable aria-hidden="true" className="size-4 text-accent" />
                    {source.protocol}
                  </CardTitle>
                  <CardDescription className="font-mono">{source.endpoint}</CardDescription>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-muted-foreground">Rate</div>
                    <div className="mt-1 font-mono">{source.rate}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Latency</div>
                    <div className="mt-1 font-mono">{source.latency}</div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </section>
        </section>

        <aside className="space-y-4">
          <Card id="ai" className="surface-card border-border bg-surface-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BrainCircuit aria-hidden="true" className="size-5 text-accent" />
                AI Gateway
              </CardTitle>
              <CardDescription>LM Studio compatible enrichment path</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {telemetry.isLoading ? (
                <>
                  <Skeleton className="h-5 w-full bg-surface-2" />
                  <Skeleton className="h-5 w-3/4 bg-surface-2" />
                </>
              ) : (
                <>
                  <div>
                    <div className="text-muted-foreground">Model</div>
                    <div className="mt-1 break-words font-mono">{telemetry.data?.llm.model ?? "openai/gpt-oss-20B"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Base URL</div>
                    <div className="mt-1 break-words font-mono">
                      {telemetry.data?.llm.base_url ?? "http://172.17.0.1:1234/v1"}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Last error</div>
                    <div className="mt-1">{telemetry.data?.llm.last_error ?? "None reported"}</div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card id="observability" className="surface-card border-border bg-surface-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 aria-hidden="true" className="size-5 text-accent" />
                Operator Links
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              {[
                ["Grafana", "http://localhost:13000", Waves],
                ["Prometheus", "http://localhost:19090", Activity],
                ["Edge Metrics", "http://localhost:8090", ServerCog],
                ["AI Health", "http://localhost:8080/health", BrainCircuit],
                ["Postgres CDC", "http://localhost:18083", DatabaseZap],
              ].map(([label, href, Icon]) => (
                <a
                  key={href as string}
                  href={href as string}
                  className={cn(buttonVariants({ variant: "outline" }), "min-h-11 cursor-pointer justify-start")}
                >
                  <Icon aria-hidden="true" className="mr-2 size-4" />
                  {label as string}
                </a>
              ))}
            </CardContent>
          </Card>
        </aside>
      </div>
    </main>
  );
}
