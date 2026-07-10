"use client";

import { Activity, AlertTriangle, BrainCircuit, Cable, Gauge, RadioTower, Workflow } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { HelpTip } from "@/components/help-tip";
import { SectionHeader } from "@/components/section-header";
import { StatCard } from "@/components/stat-card";
import { useTelemetryEvents } from "@/lib/useTelemetryEvents";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const sourceHealth = [
  { protocol: "OPC UA", endpoint: "opc.tcp://opcua-sim:4840", status: "active", rate: "3 tags/s", latency: "410 ms" },
  { protocol: "MQTT", endpoint: "factory/+/+/+", status: "active", rate: "25 msg/s", latency: "74 ms" },
  { protocol: "Modbus TCP", endpoint: "modbus-sim:5020", status: "active", rate: "3 regs/s", latency: "190 ms" },
];

const events = [
  { asset: "Pump-01", tag: "Temperature", value: "51.2 C", protocol: "OPC UA", quality: "good" },
  { asset: "Pump-04", tag: "Vibration", value: "8.8 mm/s", protocol: "MQTT", quality: "good" },
  { asset: "Pump-03", tag: "Pressure", value: "6.4 bar", protocol: "Modbus", quality: "good" },
  { asset: "Pump-07", tag: "Temperature", value: "72.1 C", protocol: "MQTT", quality: "warning" },
];

function statusTone(status: string) {
  if (status === "active" || status === "online") return "border-success/30 bg-success/10 text-success";
  if (status === "degraded" || status === "warning") return "border-warning/30 bg-warning/10 text-warning";
  return "border-error/30 bg-error/10 text-error";
}

export default function PipelinePage() {
  const telemetry = useTelemetryEvents();
  const runtimeMode = telemetry.data?.pipeline?.[2]?.status ?? "starting";
  const systemStatus = telemetry.error ? "degraded" : "online";

  return (
    <DashboardFrame systemStatus={systemStatus} rightRail={<PipelineRail runtimeMode={runtimeMode} />}>
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <p className="label-overline">Pipeline</p>
            <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Extraction, normalization, processing, and DLQ boundaries</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This route shows the pre-storage flow from PLC and sensor extraction through validation, normalization, runtime
              processing, and the exception lane for bad records.
            </p>
          </div>
        </header>

        <section className="space-y-4">
          <SectionHeader
            title="Ingress lanes"
            eyebrow="Edge ingest"
            description="Protocol adapters and their current simulated endpoints."
            icon={Cable}
            actions={
              <HelpTip
                label="Ingress lanes help"
                side="left"
                content="This panel shows the protocol adapters at the edge. Use it to understand which industrial source types the platform can ingest, how they are mapped, and whether a protocol lane is active or degraded."
              />
            }
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

        <section className="space-y-4">
          <SectionHeader
            title="Pipeline stages"
            eyebrow="Flow"
            description="The path from extraction to normalized Kafka topics."
            icon={Activity}
            actions={
              <HelpTip
                label="Pipeline stages help"
                side="left"
                content="This panel explains the transformation path after source data enters the platform. Use it to see where the record is extracted, validated, normalized, and routed to either the canonical stream or the DLQ."
              />
            }
          />
          <div className="grid gap-3 md:grid-cols-4">
            {[
              ["Extract", "OPC UA, MQTT, Modbus"],
              ["Validate", "Schema and quality checks"],
              ["Normalize", "industrial.raw -> industrial.normalized"],
              ["Route", "DLQ and compatibility lanes"],
            ].map(([title, desc], index) => (
              <Card key={title} className="border-border bg-surface-2">
                <CardHeader>
                  <CardDescription>Stage {index + 1}</CardDescription>
                  <CardTitle className="text-base">{title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-text-secondary">{desc}</CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <SectionHeader
            title="Event preview"
            eyebrow="Preview"
            description="Representative records after extraction and normalization."
            icon={RadioTower}
            actions={
              <HelpTip
                label="Event preview help"
                side="left"
                content="This panel shows example records in the shape the platform expects after normalization. Use it to understand the asset, tag, value, protocol, and quality fields before data is written to durable storage."
              />
            }
          />
          <Card className="border-border bg-surface-2">
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
          </Card>
        </section>

        <section className="space-y-4">
          <SectionHeader
            title="Processing runtime"
            eyebrow="Runtime"
            description="The live contract for the scoring and enrichment layer that consumes normalized events."
            icon={Workflow}
            actions={
              <HelpTip
                label="Processing runtime help"
                side="left"
                content="This panel shows how the platform processes normalized records after ingestion. Use it to understand whether the runtime is on Python fallback or a Flink path, and how events are handed off to downstream consumers."
              />
            }
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Runtime mode" value={runtimeMode} icon={Workflow} tone="info" />
            <StatCard label="Batch path" value="iot.raw -> iot.processed" icon={Gauge} tone="default" />
            <StatCard label="AI handoff" value="iot.processed -> ai" icon={BrainCircuit} tone="warning" />
            <StatCard label="State model" value="keyed windows" icon={Workflow} tone="default" />
          </div>
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
      </div>
    </DashboardFrame>
  );
}

function PipelineRail({ runtimeMode }: { runtimeMode: string }) {
  return (
    <div className="space-y-4">
      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <AlertTriangle aria-hidden="true" className="size-4 text-accent" />
            Boundary notes
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
          <p>Everything here happens before durable storage or analytics views.</p>
          <p>Use this page to test source isolation, normalization, DLQ behavior, and processing runtime behavior.</p>
        </CardContent>
      </Card>

      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <CardTitle className="text-base font-semibold">Runtime notes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
          <p>Use Python fallback to debug logic and Flink to validate distributed behavior.</p>
          <p className="font-mono text-xs text-text-primary">active: {runtimeMode}</p>
        </CardContent>
      </Card>
    </div>
  );
}
