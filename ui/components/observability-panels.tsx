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

export function ObservabilityPanels({ snapshot }: { snapshot: ObservabilitySnapshot }) {
  const grafanaTone = snapshot.grafana.online
    ? "border-success/30 bg-success/10 text-success"
    : "border-error/30 bg-error/10 text-error";
  const grafanaLabel = snapshot.grafana.online ? "Grafana online" : "Grafana offline";
  const grafanaButtonClass = snapshot.grafana.online
    ? "action-primary"
    : "action-secondary pointer-events-none cursor-not-allowed opacity-60";

  return (
    <section id="observability" className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card className="shell-band border-border bg-surface-1">
          <CardHeader className="space-y-2">
            <CardDescription>Live throughput</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{snapshot.summary.total_throughput.toFixed(2)} /s</CardTitle>
          </CardHeader>
        </Card>
        <Card className="shell-band border-border bg-surface-1">
          <CardHeader className="space-y-2">
            <CardDescription>LLM p95 latency</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{snapshot.summary.ai_latency_p95.toFixed(2)} s</CardTitle>
          </CardHeader>
        </Card>
        <Card className="shell-band border-border bg-surface-1">
          <CardHeader className="space-y-2">
            <CardDescription>DLQ total</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{snapshot.summary.dlq_total.toFixed(0)}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="shell-band border-border bg-surface-1">
          <CardHeader className="space-y-2">
            <CardDescription>Grafana</CardDescription>
            <CardTitle className="text-2xl">{grafanaLabel}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="shell-band border-border bg-surface-1 xl:col-span-2">
        <CardHeader>
          <CardTitle>Ingest throughput</CardTitle>
          <CardDescription>Live rate by protocol from the edge stream.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={throughputConfig} className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={snapshot.throughput}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="timestamp" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltipContent indicator="line" />} />
                <Line type="monotone" dataKey="mqtt" stroke="var(--chart-2)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="opcua" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="modbus" stroke="var(--chart-3)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card className="shell-band border-border bg-surface-1">
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-3">
            <span>Grafana</span>
            <Badge variant="outline" className={cn("font-medium", grafanaTone)}>
              {grafanaLabel}
            </Badge>
          </CardTitle>
          <CardDescription>Local observability target only.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2 text-sm text-text-secondary">
            <div className="flex items-center justify-between gap-3">
              <span>Endpoint</span>
              <span className="font-mono text-text-primary">localhost:13000</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Prometheus</span>
              <span className="font-mono text-text-primary">{snapshot.prometheus.status}</span>
            </div>
          </div>
          <a href={snapshot.grafana.login_url} target="_blank" rel="noreferrer" className={cn("inline-flex min-h-11 w-full items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors", grafanaButtonClass)}>
            Open local Grafana
          </a>
        </CardContent>
      </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="shell-band border-border bg-surface-1">
        <CardHeader>
          <CardTitle>AI latency</CardTitle>
          <CardDescription>Model response time and batch size.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={latencyConfig} className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={snapshot.latency}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="timestamp" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltipContent indicator="line" />} />
                <Area type="monotone" dataKey="p95" stroke="var(--chart-4)" fill="var(--chart-4)" fillOpacity={0.18} />
                <Area type="monotone" dataKey="batch_size" stroke="var(--chart-2)" fill="var(--chart-2)" fillOpacity={0.12} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartContainer>
        </CardContent>
      </Card>

        <Card className="shell-band border-border bg-surface-1">
        <CardHeader>
          <CardTitle>Protocol mix</CardTitle>
          <CardDescription>Current totals by source type.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={throughputConfig} className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={snapshot.protocolMix}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="protocol" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltipContent indicator="dot" />} />
                <Bar dataKey="total" radius={4} fill="var(--chart-1)" />
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        </CardContent>
      </Card>

        <Card className="shell-band border-border bg-surface-1">
        <CardHeader>
          <CardTitle>Severity mix</CardTitle>
          <CardDescription>Live processor output grouped by severity.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={severityConfig} className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={snapshot.severity}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltipContent indicator="dot" />} />
                <Bar dataKey="total" radius={4} fill="var(--chart-3)" />
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        </CardContent>
      </Card>
      </div>
    </section>
  );
}
