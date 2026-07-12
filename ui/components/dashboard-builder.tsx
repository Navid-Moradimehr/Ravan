"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Database,
  GripVertical,
  LayoutDashboard,
  Plus,
  Settings2,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ChartContainer, ChartTooltipContent } from "@/components/ui/chart";
import { HelpTip } from "@/components/help-tip";
import {
  getAlarms,
  getAssetTagCatalog,
  getHistorianEvents,
  getHistorianTrend,
  getObservability,
  type AlarmEvent,
  type HistorianEvent,
  type HistorianTrendPoint,
  type ObservabilitySnapshot,
} from "@/lib/api";
import { formatErrorMessage } from "@/lib/http";

export type PanelType = "trend" | "alarms" | "events" | "stats" | "observability";

export interface DashboardPanel {
  id: string;
  type: PanelType;
  title: string;
  config: {
    asset_id: string;
    tag: string;
    table: string;
    hours: number;
    refresh_seconds: number;
  };
}

const STORAGE_KEY = "lse.historian.custom-dashboard.v2";

const PANEL_TYPES: { type: PanelType; label: string; description: string }[] = [
  { type: "trend", label: "Historian trend", description: "Plot one asset tag over a selected time window." },
  { type: "stats", label: "Historian stats", description: "Show event count, latest value, and alarm count." },
  { type: "alarms", label: "Alarm table", description: "Show the latest historian alarms." },
  { type: "events", label: "Events table", description: "Show the latest rows from a historian table." },
  { type: "observability", label: "Runtime health", description: "Show live throughput and processing health." },
];

const defaultConfig = (): DashboardPanel["config"] => ({
  asset_id: "",
  tag: "",
  table: "industrial_events",
  hours: 1,
  refresh_seconds: 5,
});

const defaultPanels = (): DashboardPanel[] => [
  { id: "stats", type: "stats", title: "Historian overview", config: defaultConfig() },
  { id: "alarms", type: "alarms", title: "Latest alarms", config: defaultConfig() },
];

function sanitizePanels(value: unknown): DashboardPanel[] {
  if (!Array.isArray(value)) throw new Error("Dashboard file must contain a panel array.");
  const allowed = new Set<PanelType>(PANEL_TYPES.map((item) => item.type));
  const panels = value.map((item, index) => {
    if (!item || typeof item !== "object") throw new Error(`Panel ${index + 1} is invalid.`);
    const candidate = item as Partial<DashboardPanel>;
    if (!candidate.id || !candidate.title || !candidate.type || !allowed.has(candidate.type)) {
      throw new Error(`Panel ${index + 1} has an invalid id, title, or type.`);
    }
    return {
      id: String(candidate.id),
      type: candidate.type,
      title: String(candidate.title),
      config: { ...defaultConfig(), ...(candidate.config ?? {}) },
    } as DashboardPanel;
  });
  if (panels.length > 20) throw new Error("Dashboard files may contain at most 20 panels.");
  return panels;
}

function formatTime(value: unknown): string {
  if (!value) return "n/a";
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? "n/a" : date.toLocaleTimeString();
}

function formatValue(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "n/a";
}

function flattenTags(items: Awaited<ReturnType<typeof getAssetTagCatalog>>["items"]): Array<{ asset_id: string; tag: string; label: string }> {
  return items.map((item) => ({ asset_id: item.asset_id, tag: item.tag, label: `${item.site_id} / ${item.asset_name} / ${item.tag}` }));
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-8 text-center text-sm text-text-secondary">{children}</p>;
}

function QueryError({ error }: { error: unknown }) {
  return <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-3 text-sm text-text-primary">{formatErrorMessage(error, "This panel could not load its data.")}</p>;
}

function TrendPanel({ panel }: { panel: DashboardPanel }) {
  const query = useQuery<HistorianTrendPoint[]>({
    queryKey: ["custom-dashboard", panel.id, "trend", panel.config.asset_id, panel.config.tag, panel.config.hours],
    queryFn: () => getHistorianTrend(panel.config.asset_id, panel.config.tag, panel.config.hours),
    enabled: Boolean(panel.config.asset_id && panel.config.tag),
    refetchInterval: panel.config.refresh_seconds > 0 ? panel.config.refresh_seconds * 1000 : false,
  });
  if (!panel.config.asset_id || !panel.config.tag) return <EmptyState>Open Settings and choose an asset tag to configure this trend.</EmptyState>;
  if (query.isError) return <QueryError error={query.error} />;
  if (query.isLoading) return <EmptyState>Loading historian trend...</EmptyState>;
  if (!query.data?.length) return <EmptyState>No historian samples match this asset, tag, and time window.</EmptyState>;
  return (
    <ChartContainer config={{ value: { label: panel.config.tag, color: "var(--chart-1)" } }} className="h-[230px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={query.data}>
          <CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="time" tickFormatter={formatTime} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} width={42} />
          <Tooltip content={<ChartTooltipContent indicator="line" labelFormatter={(value) => formatTime(value)} />} />
          <Line type="monotone" dataKey="value" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}

function EventsPanel({ panel }: { panel: DashboardPanel }) {
  const query = useQuery<HistorianEvent[]>({
    queryKey: ["custom-dashboard", panel.id, "events", panel.config.table],
    queryFn: () => getHistorianEvents(panel.config.table, 25),
    refetchInterval: panel.config.refresh_seconds > 0 ? panel.config.refresh_seconds * 1000 : false,
  });
  if (query.isError) return <QueryError error={query.error} />;
  if (query.isLoading) return <EmptyState>Loading historian events...</EmptyState>;
  if (!query.data?.length) return <EmptyState>No events are available in this historian table.</EmptyState>;
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-border-subtle">
      <Table>
        <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Asset</TableHead><TableHead>Tag</TableHead><TableHead>Value</TableHead><TableHead>Quality</TableHead></TableRow></TableHeader>
        <TableBody>{query.data.map((event) => <TableRow key={`${event.event_id}-${event.time}`}><TableCell className="whitespace-nowrap text-xs">{formatTime(event.time)}</TableCell><TableCell>{event.asset_id}</TableCell><TableCell>{event.tag}</TableCell><TableCell>{formatValue(event.value)}</TableCell><TableCell><Badge variant="outline">{event.quality || "unknown"}</Badge></TableCell></TableRow>)}</TableBody>
      </Table>
    </div>
  );
}

function AlarmsPanel({ panel }: { panel: DashboardPanel }) {
  const query = useQuery<AlarmEvent[]>({
    queryKey: ["custom-dashboard", panel.id, "alarms"],
    queryFn: () => getAlarms(25),
    refetchInterval: panel.config.refresh_seconds > 0 ? panel.config.refresh_seconds * 1000 : false,
  });
  if (query.isError) return <QueryError error={query.error} />;
  if (query.isLoading) return <EmptyState>Loading alarms...</EmptyState>;
  if (!query.data?.length) return <EmptyState>No alarms are currently recorded.</EmptyState>;
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-border-subtle">
      <Table>
        <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Asset</TableHead><TableHead>Tag</TableHead><TableHead>Value</TableHead><TableHead>Severity</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
        <TableBody>{query.data.map((alarm, index) => <TableRow key={`${alarm.time}-${alarm.asset_id}-${alarm.tag}-${index}`}><TableCell className="whitespace-nowrap text-xs">{formatTime(alarm.time)}</TableCell><TableCell>{alarm.asset_id}</TableCell><TableCell>{alarm.tag}</TableCell><TableCell>{alarm.value == null ? "n/a" : `${formatValue(alarm.value)} ${alarm.unit ?? ""}`}</TableCell><TableCell><Badge variant="outline">{alarm.severity}</Badge></TableCell><TableCell>{alarm.acknowledged ? "Acknowledged" : "Open"}</TableCell></TableRow>)}</TableBody>
      </Table>
    </div>
  );
}

function StatsPanel({ panel }: { panel: DashboardPanel }) {
  const events = useQuery<HistorianEvent[]>({ queryKey: ["custom-dashboard", panel.id, "stats-events"], queryFn: () => getHistorianEvents(panel.config.table, 100), refetchInterval: panel.config.refresh_seconds > 0 ? panel.config.refresh_seconds * 1000 : false });
  const alarms = useQuery<AlarmEvent[]>({ queryKey: ["custom-dashboard", panel.id, "stats-alarms"], queryFn: () => getAlarms(100), refetchInterval: panel.config.refresh_seconds > 0 ? panel.config.refresh_seconds * 1000 : false });
  if (events.isError || alarms.isError) return <QueryError error={events.error ?? alarms.error} />;
  const latest = events.data?.[0];
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="text-xs text-text-secondary">Rows sampled</div><div className="mt-1 text-2xl font-semibold">{events.data?.length ?? "..."}</div></div>
      <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="text-xs text-text-secondary">Latest value</div><div className="mt-1 text-2xl font-semibold">{latest ? formatValue(latest.value) : "..."}</div><div className="text-xs text-text-secondary">{latest?.tag ?? "waiting for data"}</div></div>
      <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="text-xs text-text-secondary">Alarms sampled</div><div className="mt-1 text-2xl font-semibold">{alarms.data?.length ?? "..."}</div></div>
    </div>
  );
}

function ObservabilityPanel({ panel }: { panel: DashboardPanel }) {
  const query = useQuery<ObservabilitySnapshot>({ queryKey: ["custom-dashboard", panel.id, "observability"], queryFn: getObservability, refetchInterval: panel.config.refresh_seconds > 0 ? panel.config.refresh_seconds * 1000 : false });
  if (query.isError) return <QueryError error={query.error} />;
  if (!query.data) return <EmptyState>Loading runtime health...</EmptyState>;
  const points = query.data.throughput ?? [];
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="text-xs text-text-secondary">Throughput</div><div className="mt-1 text-xl font-semibold">{formatValue(query.data.summary.total_throughput)} /s</div></div><div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="text-xs text-text-secondary">DLQ</div><div className="mt-1 text-xl font-semibold">{query.data.summary.dlq_total}</div></div><div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="text-xs text-text-secondary">Prometheus</div><div className="mt-1 text-xl font-semibold">{query.data.prometheus.status}</div></div></div>
      {points.length ? <ChartContainer config={{ mqtt: { label: "MQTT", color: "var(--chart-2)" }, opcua: { label: "OPC UA", color: "var(--chart-1)" }, modbus: { label: "Modbus", color: "var(--chart-3)" } }} className="h-[190px] w-full"><ResponsiveContainer width="100%" height="100%"><AreaChart data={points}><CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="timestamp" tickLine={false} axisLine={false} /><YAxis tickLine={false} axisLine={false} width={35} /><Tooltip content={<ChartTooltipContent indicator="line" />} /><Area type="monotone" dataKey="mqtt" stroke="var(--chart-2)" fill="var(--chart-2)" fillOpacity={0.12} /><Area type="monotone" dataKey="opcua" stroke="var(--chart-1)" fill="var(--chart-1)" fillOpacity={0.12} /><Area type="monotone" dataKey="modbus" stroke="var(--chart-3)" fill="var(--chart-3)" fillOpacity={0.12} /></AreaChart></ResponsiveContainer></ChartContainer> : <EmptyState>No runtime samples are available yet.</EmptyState>}
    </div>
  );
}

function PanelBody({ panel }: { panel: DashboardPanel }) {
  if (panel.type === "trend") return <TrendPanel panel={panel} />;
  if (panel.type === "events") return <EventsPanel panel={panel} />;
  if (panel.type === "alarms") return <AlarmsPanel panel={panel} />;
  if (panel.type === "observability") return <ObservabilityPanel panel={panel} />;
  return <StatsPanel panel={panel} />;
}

function PanelSettings({ panel, assets, onConfigChange, onTitleChange }: { panel: DashboardPanel; assets: Array<{ asset_id: string; tag: string; label: string }>; onConfigChange: (config: DashboardPanel["config"]) => void; onTitleChange: (title: string) => void }) {
  const update = (patch: Partial<DashboardPanel["config"]>) => onConfigChange({ ...panel.config, ...patch });
  return <div className="grid gap-3 rounded-lg border border-border-subtle bg-surface-2 p-3 sm:grid-cols-2">
    <label className="space-y-1 text-xs text-text-secondary"><span>Panel title</span><Input value={panel.title} onChange={(event) => onTitleChange(event.target.value)} /></label>
    {panel.type === "trend" ? <div className="space-y-2"><label className="space-y-1 text-xs text-text-secondary"><span>Asset tag</span><select value={`${panel.config.asset_id}::${panel.config.tag}`} onChange={(event) => { const [asset_id, tag] = event.target.value.split("::"); update({ asset_id, tag }); }} className="app-select"><option value="::">Select a configured asset tag</option>{assets.map((item) => <option key={`${item.asset_id}::${item.tag}`} value={`${item.asset_id}::${item.tag}`}>{item.label}</option>)}</select></label><div className="grid gap-2 sm:grid-cols-2"><Input aria-label="Manual asset id" placeholder="Asset ID" value={panel.config.asset_id} onChange={(event) => update({ asset_id: event.target.value })} /><Input aria-label="Manual tag" placeholder="Tag" value={panel.config.tag} onChange={(event) => update({ tag: event.target.value })} /></div><p className="text-[11px] leading-4 text-text-secondary">Use manual values when the observed catalog is not populated yet. They must match historian rows.</p></div> : null}
    {panel.type === "events" || panel.type === "stats" ? <label className="space-y-1 text-xs text-text-secondary"><span>Historian table</span><Input value={panel.config.table} onChange={(event) => update({ table: event.target.value })} /></label> : null}
    {panel.type === "trend" ? <label className="space-y-1 text-xs text-text-secondary"><span>Hours</span><Input type="number" min={1} max={168} value={panel.config.hours} onChange={(event) => update({ hours: Math.max(1, Number(event.target.value) || 1) })} /></label> : null}
    <label className="space-y-1 text-xs text-text-secondary"><span>Refresh seconds, 0 pauses</span><Input type="number" min={0} max={3600} value={panel.config.refresh_seconds} onChange={(event) => update({ refresh_seconds: Math.max(0, Number(event.target.value) || 0) })} /></label>
  </div>;
}

export function DashboardBuilder() {
  const [panels, setPanels] = useState<DashboardPanel[]>(defaultPanels);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const assetsQuery = useQuery({ queryKey: ["custom-dashboard", "asset-tag-catalog"], queryFn: getAssetTagCatalog });
  const assets = flattenTags(assetsQuery.data?.items ?? []);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setPanels(sanitizePanels(JSON.parse(saved)));
      }
    } catch {
      setStorageWarning("The saved dashboard could not be loaded. The default layout is being used.");
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(panels));
      setStorageWarning(null);
    } catch {
      setStorageWarning("Dashboard changes could not be saved in this browser.");
    }
  }, [hydrated, panels]);

  const savePanels = useCallback((next: DashboardPanel[]) => setPanels(next), []);
  const updatePanel = (id: string, patch: Partial<DashboardPanel>) => savePanels(panels.map((panel) => panel.id === id ? { ...panel, ...patch } : panel));
  const movePanel = (id: string, direction: -1 | 1) => {
    const index = panels.findIndex((panel) => panel.id === id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= panels.length) return;
    const next = [...panels];
    [next[index], next[target]] = [next[target], next[index]];
    savePanels(next);
  };
  const addPanel = (type: PanelType) => {
    const definition = PANEL_TYPES.find((item) => item.type === type);
    const id = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${type}-${Date.now()}`;
    savePanels([...panels, { id, type, title: definition?.label ?? type, config: defaultConfig() }]);
    setShowAdd(false);
    setEditing(id);
  };
  const exportDashboard = () => {
    const blob = new Blob([JSON.stringify({ version: 2, panels }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "industrial-dashboard.json";
    link.click();
    URL.revokeObjectURL(url);
  };
  const importDashboard = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result));
        setPanels(sanitizePanels(parsed.panels ?? parsed));
        setStorageWarning(null);
      } catch (error) {
        setStorageWarning(error instanceof Error ? error.message : "Dashboard file could not be imported.");
      }
    };
    reader.readAsText(file);
  };

  return <Card className="app-card">
    <CardHeader className="app-card-header">
      <CardTitle className="flex items-center gap-2 text-base font-semibold"><LayoutDashboard className="size-4 text-accent" />Custom Dashboard <HelpTip label="Custom dashboard help" content="Build a small operator view from historian and runtime APIs. Layouts are saved in this browser and can be moved with Export JSON and Import JSON. Use Grafana for shared, advanced, or cross-site dashboards." /></CardTitle>
      <CardDescription className="text-text-secondary">Compose a focused operator view from live historian and observability data. Grafana remains the advanced dashboard surface.</CardDescription>
    </CardHeader>
    <CardContent className="space-y-4 p-4">
      {storageWarning ? <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-text-primary">{storageWarning}</p> : null}
      {assetsQuery.isError ? <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-text-primary">Asset tags could not be loaded. Trend panels can be added, but they need an asset registry entry before they can display samples.</p> : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {panels.map((panel, index) => <div key={panel.id} className="rounded-xl border border-border-subtle bg-surface-2/60 p-4">
          <div className="mb-3 flex items-start justify-between gap-3"><div className="flex min-w-0 items-center gap-2"><GripVertical className="size-4 shrink-0 text-text-muted" /><div className="min-w-0"><div className="truncate text-sm font-semibold">{panel.title}</div><div className="text-xs text-text-secondary">{PANEL_TYPES.find((item) => item.type === panel.type)?.description}</div></div></div><div className="flex shrink-0 items-center gap-1"><Button variant="ghost" size="icon-xs" aria-label="Move panel up" disabled={index === 0} onClick={() => movePanel(panel.id, -1)}><ChevronUp className="size-4" /></Button><Button variant="ghost" size="icon-xs" aria-label="Move panel down" disabled={index === panels.length - 1} onClick={() => movePanel(panel.id, 1)}><ChevronDown className="size-4" /></Button><Button variant="ghost" size="icon-xs" aria-label="Configure panel" onClick={() => setEditing(editing === panel.id ? null : panel.id)}><Settings2 className="size-4" /></Button><Button variant="ghost" size="icon-xs" aria-label="Remove panel" onClick={() => savePanels(panels.filter((item) => item.id !== panel.id))}><X className="size-4 text-error" /></Button></div></div>
          {editing === panel.id ? <PanelSettings panel={panel} assets={assets} onConfigChange={(config) => updatePanel(panel.id, { config })} onTitleChange={(title) => updatePanel(panel.id, { title })} /> : null}
          <div className="mt-3"><PanelBody panel={panel} /></div>
        </div>)}
      </div>
      {showAdd ? <div className="grid gap-2 rounded-lg border border-border-subtle bg-surface-2 p-3 sm:grid-cols-2 lg:grid-cols-3">{PANEL_TYPES.map((item) => <Button key={item.type} variant="outline" className="h-auto justify-start whitespace-normal p-3 text-left" onClick={() => addPanel(item.type)}><span><span className="block font-medium">{item.label}</span><span className="mt-1 block text-xs font-normal text-text-secondary">{item.description}</span></span></Button>)}</div> : null}
      <div className="flex flex-wrap items-center gap-2"><Button variant="outline" onClick={() => setShowAdd(!showAdd)}><Plus className="mr-1 size-4" />{showAdd ? "Close panel library" : "Add panel"}</Button><Button variant="ghost" onClick={() => savePanels(defaultPanels())}>Reset layout</Button><Button variant="ghost" onClick={exportDashboard}>Export JSON</Button><Button variant="ghost" onClick={() => importInputRef.current?.click()}>Import JSON</Button><input ref={importInputRef} type="file" accept="application/json" className="hidden" onChange={(event) => { importDashboard(event.target.files?.[0]); event.currentTarget.value = ""; }} /><span className="text-xs text-text-secondary">Export/import shares a layout without adding server-side identity or permissions.</span></div>
    </CardContent>
  </Card>;
}
