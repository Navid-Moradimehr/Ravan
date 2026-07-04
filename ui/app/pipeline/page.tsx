import { Activity, AlertTriangle, Cable, RadioTower } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
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
  if (status === "active") return "border-success/30 bg-success/10 text-success";
  if (status === "degraded" || status === "warning") return "border-warning/30 bg-warning/10 text-warning";
  return "border-error/30 bg-error/10 text-error";
}

export default function PipelinePage() {
  return (
    <DashboardFrame rightRail={<PipelineRail />}>
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <p className="label-overline">Pipeline</p>
            <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Extraction, normalization, and DLQ boundaries</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This route isolates the pre-storage flow: PLC and sensor extraction, validation, normalized Kafka topics, and the
              exception lane for bad records.
            </p>
          </div>
        </header>

        <section className="space-y-4">
          <SectionHeader
            title="Ingress lanes"
            eyebrow="Edge ingest"
            description="Protocol adapters and their current simulated endpoints."
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

        <section className="space-y-4">
          <SectionHeader
            title="Pipeline stages"
            eyebrow="Flow"
            description="The path from extraction to normalized Kafka topics."
            icon={Activity}
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
      </div>
    </DashboardFrame>
  );
}

function PipelineRail() {
  return (
    <Card className="app-card overflow-hidden">
      <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <AlertTriangle aria-hidden="true" className="size-4 text-accent" />
          Boundary notes
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
        <p>Everything here happens before durable storage or analytics views.</p>
        <p>Use this page to test source isolation, normalization, and DLQ behavior.</p>
      </CardContent>
    </Card>
  );
}
