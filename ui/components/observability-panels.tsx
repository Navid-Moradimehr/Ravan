"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartContainer, ChartTooltipContent } from "@/components/ui/chart";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/stat-card";
import { SectionHeader } from "@/components/section-header";
import { Activity, AlertOctagon, Gauge, ShieldCheck } from "lucide-react";
import type { ObservabilitySnapshot } from "@/lib/api";
import { cn } from "@/lib/utils";

const throughputConfig = {
  mqtt: { label: "MQTT", color: "var(--chart-2)" },
  opcua: { label: "OPC UA", color: "var(--chart-1)" },
  modbus: { label: "Modbus", color: "var(--chart-3)" },
};

const latencyConfig = {
  p95: { label: "LLM p95", color: "var(--chart-4)" },
  batch_size: { label: "Batch size", color: "var(--chart-2)" },
};

const severityConfig = {
  normal: { label: "Normal", color: "var(--chart-3)" },
  warning: { label: "Warning", color: "var(--chart-4)" },
  critical: { label: "Critical", color: "var(--chart-5)" },
};

const chartGrid = <CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" vertical={false} />;
const axisProps = { tickLine: false, axisLine: false, tick: { fontSize: 11, fill: "var(--color-text-muted)" } };

function formatMetric(value: unknown, digits: number, fallback = "0") {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(digits) : fallback;
}

export function ObservabilityPanels({ snapshot }: { snapshot: ObservabilitySnapshot }) {
  const grafanaTone = snapshot.grafana.online
    ? "border-success/30 bg-success/10 text-success"
    : "border-error/30 bg-error/10 text-error";
  const grafanaLabel = snapshot.grafana.online ? "Grafana online" : "Grafana offline";
  const grafanaButtonClass = snapshot.grafana.online
    ? "action-primary"
    : "action-secondary pointer-events-none cursor-not-allowed opacity-60";

  return (
    <section id="observability" className="space-y-5">
      <SectionHeader
        title="Observability"
        eyebrow="Telemetry"
        description="Live throughput, AI latency, protocol mix, and severity across the local stack."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Live throughput"
          value={formatMetric(snapshot.summary.total_throughput, 2)}
          unit="/s"
          icon={Activity}
          tone="info"
        />
        <StatCard
          label="LLM p95 latency"
          value={formatMetric(snapshot.summary.ai_latency_p95, 2)}
          unit="s"
          icon={Gauge}
          tone="warning"
        />
        <StatCard
          label="DLQ total"
          value={formatMetric(snapshot.summary.dlq_total, 0)}
          icon={AlertOctagon}
          tone={snapshot.summary.dlq_total > 0 ? "error" : "success"}
        />
        <StatCard
          label="Grafana"
          value={snapshot.grafana.online ? "Online" : "Offline"}
          icon={ShieldCheck}
          tone={snapshot.grafana.online ? "success" : "error"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="app-card overflow-hidden xl:col-span-2">
          <CardHeader className="app-card-header rounded-none border-b px-5 py-4">
            <CardTitle className="text-base font-semibold">Ingest throughput</CardTitle>
            <CardDescription className="text-text-secondary">Live rate by protocol from the edge stream.</CardDescription>
          </CardHeader>
          <CardContent className="p-5">
            <ChartContainer config={throughputConfig} className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={snapshot.throughput}>
                  {chartGrid}
                  <XAxis dataKey="timestamp" {...axisProps} />
                  <YAxis {...axisProps} width={32} />
                  <Tooltip content={<ChartTooltipContent indicator="line" />} />
                  <Line type="monotone" dataKey="mqtt" stroke="var(--chart-2)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="opcua" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="modbus" stroke="var(--chart-3)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-5 py-4">
            <CardTitle className="flex items-center justify-between gap-3 text-base font-semibold">
              <span>Grafana</span>
              <Badge variant="outline" className={cn("font-medium", grafanaTone)}>
                {grafanaLabel}
              </Badge>
            </CardTitle>
            <CardDescription className="text-text-secondary">Local observability target only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-5">
            <div className="space-y-2.5 text-sm text-text-secondary">
              <div className="flex items-center justify-between gap-3">
                <span>Endpoint</span>
                <span className="font-mono text-xs text-text-primary">localhost:13000</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Prometheus</span>
                <span className="font-mono text-xs capitalize text-text-primary">{snapshot.prometheus.status}</span>
              </div>
            </div>
            <a
              href={snapshot.grafana.login_url}
              target="_blank"
              rel="noreferrer"
              className={cn(
                "inline-flex h-9 w-full items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors",
                grafanaButtonClass,
              )}
            >
              Open local Grafana
            </a>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-5 py-4">
            <CardTitle className="text-base font-semibold">AI latency</CardTitle>
            <CardDescription className="text-text-secondary">Model response time and batch size.</CardDescription>
          </CardHeader>
          <CardContent className="p-5">
            <ChartContainer config={latencyConfig} className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={snapshot.latency}>
                  {chartGrid}
                  <XAxis dataKey="timestamp" {...axisProps} />
                  <YAxis {...axisProps} width={32} />
                  <Tooltip content={<ChartTooltipContent indicator="line" />} />
                  <Area type="monotone" dataKey="p95" stroke="var(--chart-4)" strokeWidth={2} fill="var(--chart-4)" fillOpacity={0.18} />
                  <Area type="monotone" dataKey="batch_size" stroke="var(--chart-2)" strokeWidth={2} fill="var(--chart-2)" fillOpacity={0.12} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-5 py-4">
            <CardTitle className="text-base font-semibold">Protocol mix</CardTitle>
            <CardDescription className="text-text-secondary">Current totals by source type.</CardDescription>
          </CardHeader>
          <CardContent className="p-5">
            <ChartContainer config={throughputConfig} className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={snapshot.protocolMix}>
                  {chartGrid}
                  <XAxis dataKey="protocol" {...axisProps} />
                  <YAxis {...axisProps} width={32} />
                  <Tooltip content={<ChartTooltipContent indicator="dot" />} />
                  <Bar dataKey="total" radius={[4, 4, 0, 0]} fill="var(--chart-1)" />
                </BarChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="app-card overflow-hidden xl:col-span-2">
          <CardHeader className="app-card-header rounded-none border-b px-5 py-4">
            <CardTitle className="text-base font-semibold">Severity mix</CardTitle>
            <CardDescription className="text-text-secondary">Live processor output grouped by severity.</CardDescription>
          </CardHeader>
          <CardContent className="p-5">
            <ChartContainer config={severityConfig} className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={snapshot.severity}>
                  {chartGrid}
                  <XAxis dataKey="label" {...axisProps} />
                  <YAxis {...axisProps} width={32} />
                  <Tooltip content={<ChartTooltipContent indicator="dot" />} />
                  <Bar dataKey="total" radius={[4, 4, 0, 0]} fill="var(--chart-3)" />
                </BarChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
