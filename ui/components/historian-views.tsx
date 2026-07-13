"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, ChevronDown, ChevronUp, Clock3, Database, FolderTree, Play, RefreshCcw, Square, TrendingUp } from "lucide-react";
import { CartesianGrid, Label, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { getHistorianTrend, getAssetHierarchy, getAssetTagCatalog, getScenarios, getReplayStatus, getHistorianEvents, getAlarms, startReplay, stopReplay } from "@/lib/api";
import { requestJson } from "@/lib/http";
import { formatErrorMessage } from "@/lib/http";
import { showToast } from "@/components/toaster";
import { HelpTip } from "@/components/help-tip";
import { ChartContainer, ChartTooltipContent } from "@/components/ui/chart";
import { SearchableSelect } from "@/components/searchable-select";

type RefreshOption = {
  label: string;
  value: number | null;
  description: string;
};

type SourceHealth = {
  connection_id: string;
  protocol: string;
  site: string;
  state?: string;
  error?: string;
  mapping_seen?: number;
  mapping_matched?: number;
  mapping_missed?: number;
};

const HISTORIAN_REFRESH_OPTIONS: RefreshOption[] = [
  { label: "Live (2s)", value: 2000, description: "Matches the current backend polling cadence." },
  { label: "5s", value: 5000, description: "Reduce redraws while keeping near-real-time updates." },
  { label: "15s", value: 15000, description: "Best for slower review sessions." },
  { label: "Paused", value: null, description: "Freeze the table until you resume live sync." },
];

const HISTORIAN_REFRESH_STORAGE_KEY = "lse.historian.refresh";
const HISTORIAN_EVENTS_REFRESH_STORAGE_KEY = "lse.historian.events-refresh";
const HISTORIAN_TREND_RANGE_STORAGE_KEY = "lse.historian.trend-range-hours";

const HISTORIAN_TREND_RANGE_OPTIONS = [
  { label: "Last hour", hours: 1 },
  { label: "Last 6 hours", hours: 6 },
  { label: "Last 24 hours", hours: 24 },
  { label: "Last 7 days", hours: 168 },
];

async function getSourceHealth(): Promise<{ current: SourceHealth[] }> {
  return requestJson("/api/observability/source-health");
}

function readStoredRefresh(key: string): number | null | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return undefined;
    if (raw === "null") return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function writeStoredRefresh(key: string, value: number | null): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value === null ? "null" : String(value));
  } catch {
    // Ignore storage failures and fall back to in-memory state.
  }
}

function formatRefreshLabel(value: number | null): string {
  if (value === null) return "Paused";
  if (value === 2000) return "Live (2s)";
  if (value % 1000 === 0) return `${value / 1000}s`;
  return `${value}ms`;
}

function formatEventValue(value: unknown): string {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : "n/a";
}

function formatEventTime(value: unknown): string {
  if (!value) return "n/a";
  const time = new Date(String(value));
  return Number.isNaN(time.getTime()) ? "n/a" : time.toLocaleTimeString();
}

function RefreshMenu({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (next: number | null) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex h-8 items-center gap-2 rounded-full border border-border-subtle bg-surface-2 px-3 text-xs font-medium text-text-secondary transition-colors hover:bg-accent-subtle hover:text-accent"
        >
          <Clock3 className="size-3.5" />
          {label}: {formatRefreshLabel(value)}
          <RefreshCcw className="size-3.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[12rem] max-w-[calc(100vw-2rem)]">
        {HISTORIAN_REFRESH_OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.label}
            onClick={() => onChange(option.value)}
            className="flex flex-col items-start gap-0.5"
          >
            <span className="font-medium text-text-primary">{option.label}</span>
            <span className="block text-xs text-text-secondary">{option.description}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function TrendChart({ data, tag, unit }: { data: { time: string; value: number }[]; tag: string; unit?: string }) {
  if (!data.length) return <p className="text-sm text-text-secondary">No data</p>;
  return (
    <ChartContainer config={{ value: { label: unit ? `${tag} (${unit})` : tag, color: "var(--chart-1)" } }} className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, left: 10, bottom: 26 }}>
          <CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="time" tickFormatter={formatEventTime} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}>
            <Label value="Time" position="insideBottom" offset={-18} fill="var(--color-text-secondary)" fontSize={11} />
          </XAxis>
          <YAxis tickLine={false} axisLine={false} width={52} tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}>
            <Label value={unit ? `${tag} (${unit})` : tag} angle={-90} position="insideLeft" offset={-2} fill="var(--color-text-secondary)" fontSize={11} />
          </YAxis>
          <Tooltip content={<ChartTooltipContent indicator="line" labelFormatter={(value) => formatEventTime(value)} />} />
          <Line type="monotone" dataKey="value" name={unit ? `${tag} (${unit})` : tag} stroke="var(--chart-1)" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}

function AssetTree({ nodes, onSelect, selected }: { nodes: any[]; onSelect: (assetId: string, tag: string) => void; selected: { assetId: string; tag: string } | null }) {
  return (
    <ul className="space-y-1 text-sm">
      {nodes.map((node) => (
        <li key={node.id}>
          <div className="flex items-center gap-2 py-1">
            <FolderTree className="size-3.5 text-text-secondary" />
            <span className="font-medium">{node.name}</span>
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">{node.type}</Badge>
        </div>
          {node.children?.length ? (
            <div className="ml-4 border-l border-border-subtle pl-2">
              {node.type === "asset" ? (
                <div className="grid gap-1">
                  {node.children.map((tag: any) => (
                    <button key={tag.id} onClick={() => onSelect(node.id, tag.name)} className={`flex items-center gap-2 rounded-md px-2 py-1 text-left transition-colors ${selected?.assetId === node.id && selected?.tag === tag.name ? "bg-accent-subtle text-accent" : "hover:bg-surface-2"}`}>
                      <Activity className="size-3 text-text-secondary" />
                      <span className="text-xs">{tag.name}</span>
                      <span className="ml-auto text-[10px] text-text-secondary">{tag.unit}</span>
                    </button>
                  ))}
            </div>
              ) : (
                <AssetTree nodes={node.children} onSelect={onSelect} selected={selected} />
              )}
        </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function HistorianDashboard() {
  const [selectedTable, setSelectedTable] = useState("industrial_events");
  const [selectedAsset, setSelectedAsset] = useState<{ assetId: string; tag: string } | null>(null);
  const [selectedScenario, setSelectedScenario] = useState("normal");
  const [selectedDataset, setSelectedDataset] = useState("ai4i");
  const [alarmsRefreshMs, setAlarmsRefreshMs] = useState<number | null>(2000);
  const [eventsRefreshMs, setEventsRefreshMs] = useState<number | null>(2000);
  const [trendHours, setTrendHours] = useState(1);
  const [alarmsExpanded, setAlarmsExpanded] = useState(false);
  const [eventsExpanded, setEventsExpanded] = useState(false);
  const [refreshPreferencesReady, setRefreshPreferencesReady] = useState(false);
  const queryClient = useQueryClient();

  const trendQuery = useQuery({ queryKey: ["historian", "trend", selectedAsset?.assetId, selectedAsset?.tag, trendHours], queryFn: () => selectedAsset ? getHistorianTrend(selectedAsset.assetId, selectedAsset.tag, trendHours) : Promise.resolve([]), enabled: !!selectedAsset });
  const assetsQuery = useQuery({ queryKey: ["historian", "assets"], queryFn: getAssetHierarchy });
  const catalogQuery = useQuery({ queryKey: ["historian", "asset-tag-catalog"], queryFn: getAssetTagCatalog });
  const scenariosQuery = useQuery({ queryKey: ["historian", "scenarios"], queryFn: getScenarios });
  const replayQuery = useQuery({ queryKey: ["historian", "replay"], queryFn: getReplayStatus, refetchInterval: 10000 });
  const sourceHealthQuery = useQuery({ queryKey: ["historian", "source-health"], queryFn: getSourceHealth, refetchInterval: 10000 });
  const alarmsQuery = useQuery({
    queryKey: ["historian", "alarms"],
    queryFn: () => getAlarms(50),
    refetchInterval: alarmsRefreshMs ?? false,
    refetchIntervalInBackground: true,
  });
  const eventsQuery = useQuery({
    queryKey: ["historian", "events", selectedTable],
    queryFn: () => getHistorianEvents(selectedTable, 100),
    refetchInterval: eventsRefreshMs ?? false,
    refetchIntervalInBackground: true,
  });

  useEffect(() => {
    const storedTrendHours = readStoredRefresh(HISTORIAN_TREND_RANGE_STORAGE_KEY);
    if (storedTrendHours !== undefined && storedTrendHours !== null && HISTORIAN_TREND_RANGE_OPTIONS.some((option) => option.hours === storedTrendHours)) {
      setTrendHours(storedTrendHours);
    }
    const storedAlarms = readStoredRefresh(HISTORIAN_REFRESH_STORAGE_KEY);
    const storedEvents = readStoredRefresh(HISTORIAN_EVENTS_REFRESH_STORAGE_KEY);
    if (storedAlarms !== undefined) {
      setAlarmsRefreshMs(storedAlarms);
    }
    if (storedEvents !== undefined) {
      setEventsRefreshMs(storedEvents);
    }
    setRefreshPreferencesReady(true);
  }, []);

  useEffect(() => {
    writeStoredRefresh(HISTORIAN_TREND_RANGE_STORAGE_KEY, trendHours);
  }, [trendHours]);

  useEffect(() => {
    if (!refreshPreferencesReady) return;
    writeStoredRefresh(HISTORIAN_REFRESH_STORAGE_KEY, alarmsRefreshMs);
  }, [alarmsRefreshMs, refreshPreferencesReady]);

  useEffect(() => {
    if (!refreshPreferencesReady) return;
    writeStoredRefresh(HISTORIAN_EVENTS_REFRESH_STORAGE_KEY, eventsRefreshMs);
  }, [eventsRefreshMs, refreshPreferencesReady]);

  const startReplayMutation = useMutation({
    mutationFn: () => startReplay(selectedDataset, selectedScenario),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["historian", "replay"] });
      showToast({
        title: "Replay started",
        description: `Dataset ${selectedDataset} is now replaying scenario ${selectedScenario}.`,
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Replay start failed",
        description: formatErrorMessage(error, "Replay could not be started."),
        variant: "error",
      });
    },
  });
  const stopReplayMutation = useMutation({
    mutationFn: stopReplay,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["historian", "replay"] });
      showToast({
        title: "Replay stopped",
        description: "The ground-truth playback has been halted.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Replay stop failed",
        description: formatErrorMessage(error, "Replay could not be stopped."),
        variant: "error",
      });
    },
  });

  const queryErrors = [
    trendQuery.isError ? `Trend: ${formatErrorMessage(trendQuery.error, "Unable to load trend data.")}` : null,
    assetsQuery.isError ? `Assets: ${formatErrorMessage(assetsQuery.error, "Unable to load the asset hierarchy.")}` : null,
    catalogQuery.isError ? `Asset catalog: ${formatErrorMessage(catalogQuery.error, "Unable to load selectable asset tags.")}` : null,
    scenariosQuery.isError ? `Scenarios: ${formatErrorMessage(scenariosQuery.error, "Unable to load scenarios.")}` : null,
    replayQuery.isError ? `Replay: ${formatErrorMessage(replayQuery.error, "Unable to load replay status.")}` : null,
    sourceHealthQuery.isError ? `Source health: ${formatErrorMessage(sourceHealthQuery.error, "Unable to load source health.")}` : null,
    alarmsQuery.isError ? `Alarms: ${formatErrorMessage(alarmsQuery.error, "Unable to load alarm history.")}` : null,
    eventsQuery.isError ? `Events: ${formatErrorMessage(eventsQuery.error, "Unable to load historian events.")}` : null,
  ].filter((item): item is string => Boolean(item));

  const alarmsData = alarmsQuery.data ?? [];
  const eventsData = eventsQuery.data ?? [];
  const visibleAlarms = alarmsExpanded ? alarmsData : alarmsData.slice(0, 5);
  const visibleEvents = eventsExpanded ? eventsData : eventsData.slice(0, 5);
  const isAlarmsLoading = alarmsQuery.isLoading;
  const isEventsLoading = eventsQuery.isLoading;
  const mappedSources = sourceHealthQuery.data?.current.filter((source) => (source.mapping_seen ?? 0) > 0) ?? [];
  const unmappedSources = mappedSources.filter((source) => (source.mapping_matched ?? 0) === 0);

  return (
      <div className="space-y-5">
      {queryErrors.length ? (
        <Card className="app-card overflow-hidden border-error/30 bg-error/5">
          <CardHeader className="app-card-header rounded-none border-b border-error/20 px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <AlertTriangle className="size-4 text-error" />
              Historian data unavailable
            </CardTitle>
            <CardDescription className="text-text-secondary">
              Some live historian views could not be loaded. The rest of the page remains available.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 p-4 text-sm text-text-primary">
            {queryErrors.map((message) => (
              <div key={message} className="rounded-lg border border-error/20 bg-background/80 px-3 py-2">
                {message}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {unmappedSources.length ? (
        <Card className="app-card overflow-hidden border-warning/30 bg-warning/5">
          <CardHeader className="app-card-header rounded-none border-b border-warning/20 px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <AlertTriangle className="size-4 text-warning" />
              No matched mappings yet
            </CardTitle>
            <CardDescription className="text-text-secondary">
              One or more sources have live traffic, but their configured mappings have not matched the incoming fields yet.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 p-4 text-sm text-text-primary">
            {unmappedSources.slice(0, 3).map((source) => (
              <div key={source.connection_id} className="rounded-lg border border-warning/20 bg-background/80 px-3 py-2">
                <div className="font-medium">{source.connection_id}</div>
                <div className="text-xs text-text-secondary">
                  {source.protocol} · {source.site} · {source.mapping_missed ?? 0} misses · check source_field, source_id, and tag alignment
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <Play className="size-4 text-accent" />
            Scenario & Replay
            <HelpTip
              label="Scenario and replay help"
              content="Choose a dataset and scenario to replay representative industrial data through the historian. The controls here are for test and validation workflows, not for live plant writes."
            />
          </CardTitle>
          <CardDescription className="text-text-secondary">Select dataset and scenario for ground-truth testing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-secondary">Dataset</label>
            <DropdownMenu>
               <DropdownMenuTrigger asChild>
                 <button type="button" className="inline-flex h-9 w-full max-w-[10rem] items-center justify-between rounded-lg border border-border-subtle bg-surface-2 px-3 text-sm cursor-pointer">{selectedDataset === "ai4i" ? "AI4I Predictive" : "Synthetic"}</button>
               </DropdownMenuTrigger>
               <DropdownMenuContent>
                 <DropdownMenuItem onClick={() => setSelectedDataset("ai4i")}>AI4I Predictive</DropdownMenuItem>
                 <DropdownMenuItem onClick={() => setSelectedDataset("synthetic")}>Synthetic</DropdownMenuItem>
                 </DropdownMenuContent>
               </DropdownMenu>
         </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-secondary">Scenario</label>
              <SearchableSelect
                value={selectedScenario}
                options={(scenariosQuery.data ?? []).map((scenario) => ({
                  value: scenario.id,
                  label: scenario.name,
                  searchText: `${scenario.id} ${scenario.description ?? ""}`,
                }))}
                onChange={setSelectedScenario}
                placeholder="Select a scenario"
                searchPlaceholder="Search scenarios..."
                className="w-full max-w-[14rem]"
              />
            </div>
             <div className="flex items-end gap-2">
               {replayQuery.data?.running ? (
                 <button onClick={() => stopReplayMutation.mutate()} className="action-danger inline-flex h-9 items-center gap-2 rounded-lg px-4 text-sm font-medium"><Square className="size-4" />Stop</button>
               ) : (
                 <button onClick={() => startReplayMutation.mutate()} className="action-primary inline-flex h-9 items-center gap-2 rounded-lg px-4 text-sm font-medium"><Play className="size-4" />Start Replay</button>
               )}
         </div>
         </div>
           {replayQuery.data?.running ? (
             <div className="space-y-2">
               <div className="flex items-center justify-between text-xs">
                 <span className="text-text-secondary">Progress</span>
                 <span className="font-mono text-text-primary">{replayQuery.data.progress_percent ?? 0}%</span>
           </div>
               <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${replayQuery.data.progress_percent ?? 0}%` }} />
          </div>
              <div className="text-xs text-text-secondary">{replayQuery.data.events_emitted ?? 0} events emitted</div>
        </div>
          ) : null}
      </CardContent>
</Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <FolderTree className="size-4 text-accent" />
              Asset Hierarchy
              <HelpTip
                label="Asset hierarchy help"
                content="This tree mirrors the configured asset model and is used to pick tags for trends. If a site has its own topology, it should come from the asset registry or manifest."
              />
            </CardTitle>
            <CardDescription className="text-text-secondary">Click a tag to view its trend</CardDescription>
          </CardHeader>
          <CardContent className="max-h-96 overflow-y-auto p-4">
            {assetsQuery.isLoading ? (
              <div className="space-y-2"><Skeleton className="h-5 w-full bg-surface-2" /><Skeleton className="h-5 w-3/4 bg-surface-2" /></div>
            ) : (
              <AssetTree nodes={assetsQuery.data ?? []} onSelect={(assetId, tag) => setSelectedAsset({ assetId, tag })} selected={selectedAsset} />
            )}
      </CardContent>
</Card>

        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <TrendingUp className="size-4 text-accent" />
              Historical Trend
              <HelpTip
                label="Historical trend help"
                content="Trend charts show historian readings for a single selected tag. Use this view to inspect time windows, detect drift, and compare against replay data."
              />
            </CardTitle>
            <CardDescription className="text-text-secondary">{selectedAsset ? `${selectedAsset.assetId}.${selectedAsset.tag}` : "Select an asset tag"}</CardDescription>
          </CardHeader>
          <CardContent className="p-4">
            <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
              <label className="block space-y-1.5 text-xs font-medium text-text-secondary">
                <span>Asset tag</span>
              <SearchableSelect
                value={selectedAsset ? `${selectedAsset.assetId}::${selectedAsset.tag}` : ""}
                onChange={(value) => {
                  const [assetId, tag] = value.split("::");
                  setSelectedAsset(assetId && tag ? { assetId, tag } : null);
                }}
                placeholder="Select an asset tag"
                searchPlaceholder="Search assets and tags..."
                disabled={catalogQuery.isLoading}
                options={(catalogQuery.data?.items ?? []).map((item) => ({
                  value: `${item.asset_id}::${item.tag}`,
                  label: `${item.site_id} / ${item.asset_name} / ${item.tag} (${item.source})`,
                  searchText: `${item.site_id} ${item.asset_id} ${item.asset_name} ${item.tag} ${item.source}`,
                }))}
                />
              </label>
              <label className="block space-y-1.5 text-xs font-medium text-text-secondary">
                <span>Time span</span>
                <select className="app-select" value={trendHours} onChange={(event) => setTrendHours(Number(event.target.value))}>
                  {HISTORIAN_TREND_RANGE_OPTIONS.map((option) => <option key={option.hours} value={option.hours}>{option.label}</option>)}
                </select>
              </label>
            </div>
            {selectedAsset ? (trendQuery.isLoading ? <Skeleton className="h-64 w-full bg-surface-2" /> : <TrendChart data={trendQuery.data?.map((d: any) => ({ time: d.time, value: d.value })) ?? []} tag={selectedAsset.tag} unit={catalogQuery.data?.items.find((item) => item.asset_id === selectedAsset.assetId && item.tag === selectedAsset.tag)?.unit} />) : (
              <p className="py-8 text-center text-sm text-text-secondary">Select a tag above or click one in the asset hierarchy to view its trend.</p>
            )}
          </CardContent>
</Card>
      </div>

      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <AlertTriangle className="size-4 text-accent" />
                Alarms & Events
                <HelpTip
                  label="Alarms and events help"
                  content="This table shows processed events that crossed warning or critical thresholds. It is the operational alert surface for historians and dashboards. The refresh control changes how often the panel redraws from the live historian stream."
                />
              </CardTitle>
              <CardDescription className="text-text-secondary">Recent warning and critical events from processed stream</CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <RefreshMenu label="Refresh" value={alarmsRefreshMs} onChange={setAlarmsRefreshMs} />
              <button
                type="button"
                onClick={() => setAlarmsExpanded((value) => !value)}
                className="inline-flex h-8 items-center gap-2 rounded-full border border-border-subtle bg-surface-2 px-3 text-xs font-medium text-text-secondary transition-colors hover:bg-accent-subtle hover:text-accent"
              >
                {alarmsExpanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                {alarmsExpanded ? "Show latest 5" : `Show all (${alarmsData.length})`}
              </button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-border-subtle hover:bg-transparent">
                  <TableHead className="text-text-secondary">Time</TableHead>
                  <TableHead className="text-text-secondary">Asset</TableHead>
                  <TableHead className="text-text-secondary">Tag</TableHead>
                  <TableHead className="text-text-secondary">Severity</TableHead>
                  <TableHead className="text-text-secondary">Message</TableHead>
                  <TableHead className="text-text-secondary">Rules</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isAlarmsLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={6}>
                        <Skeleton className="h-5 w-full bg-surface-2" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : visibleAlarms?.length ? (
                  visibleAlarms.map((alarm: any, i: number) => (
                    <TableRow key={i} className="border-border-subtle hover:bg-surface-2">
                      <TableCell className="font-mono text-xs">{new Date(alarm.time).toLocaleTimeString()}</TableCell>
                      <TableCell className="text-sm font-medium">{alarm.asset_id}</TableCell>
                      <TableCell className="text-sm">{alarm.tag}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={alarm.severity === "critical" ? "border-error/30 bg-error/10 text-error" : "border-warning/30 bg-warning/10 text-warning"}
                        >
                          {alarm.severity}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-text-secondary">{alarm.message}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {alarm.triggered_rules?.map((rule: string, j: number) => (
                            <Badge key={j} variant="secondary" className="text-[10px]">
                              {rule}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-sm text-text-secondary">
                      No alarms in the selected window
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
            {!alarmsExpanded && alarmsData.length > 5 ? (
              <div className="border-t border-border-subtle px-4 py-3 text-xs text-text-secondary">
                Showing the latest 5 entries. Expand the panel to inspect the full alarm history.
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

    <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <Database className="size-4 text-accent" />
                Raw Events
                <HelpTip
                  label="Raw events help"
                  content="Use this view to inspect historian tables after ingestion. The dropdown switches between raw industrial events, processed events, and AI-enriched summaries. The refresh control only changes how often the live table redraws in the browser."
                />
              </CardTitle>
              <CardDescription className="text-text-secondary">Recent events from the historian</CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <RefreshMenu label="Refresh" value={eventsRefreshMs} onChange={setEventsRefreshMs} />
              <button
                type="button"
                onClick={() => setEventsExpanded((value) => !value)}
                className="inline-flex h-8 items-center gap-2 rounded-full border border-border-subtle bg-surface-2 px-3 text-xs font-medium text-text-secondary transition-colors hover:bg-accent-subtle hover:text-accent"
              >
                {eventsExpanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                {eventsExpanded ? "Show latest 5" : `Show all (${eventsData.length})`}
              </button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-2">
            <SearchableSelect
              value={selectedTable}
              onChange={setSelectedTable}
              placeholder="Select historian table"
              searchPlaceholder="Search historian tables..."
              className="w-full max-w-[16rem]"
              options={[
                { value: "industrial_events", label: "Industrial events", searchText: "raw telemetry industrial" },
                { value: "processed_events", label: "Processed events", searchText: "normalized scored" },
                { value: "ai_enriched", label: "AI-enriched events", searchText: "predictions summaries" },
              ]}
            />
        </div>
          <Table>
            <TableHeader>
              <TableRow className="border-border-subtle hover:bg-transparent">
                <TableHead className="text-text-secondary">Time</TableHead>
                <TableHead className="text-text-secondary">Asset</TableHead>
                <TableHead className="text-text-secondary">Tag</TableHead>
                <TableHead className="text-text-secondary">Value</TableHead>
                <TableHead className="text-text-secondary">Quality</TableHead>
                <TableHead className="text-text-secondary">Fault</TableHead>
                <TableHead className="text-text-secondary">Severity</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isEventsLoading ? (Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}><TableCell colSpan={7}><Skeleton className="h-5 w-full bg-surface-2" /></TableCell></TableRow>
              ))) : visibleEvents?.length ? (visibleEvents.map((event: any, i: number) => (
                <TableRow key={i} className="border-border-subtle hover:bg-surface-2">
                  <TableCell className="font-mono text-xs">{formatEventTime(event.time)}</TableCell>
                  <TableCell className="text-sm font-medium">{event.asset_id || "n/a"}</TableCell>
                  <TableCell className="text-sm">{event.tag || "n/a"}</TableCell>
                  <TableCell className="font-mono text-sm">{formatEventValue(event.value)}</TableCell>
                  <TableCell><Badge variant="outline" className={event.quality === "good" ? "border-success/30 bg-success/10 text-success" : "border-error/30 bg-error/10 text-error"}>{event.quality || "unknown"}</Badge></TableCell>
                  <TableCell className="text-sm text-text-secondary">{event.fault_type || "n/a"}</TableCell>
                  <TableCell><Badge variant="outline" className={event.ground_truth_severity === "critical" ? "border-error/30 bg-error/10 text-error" : event.ground_truth_severity === "warning" ? "border-warning/30 bg-warning/10 text-warning" : "border-success/30 bg-success/10 text-success"}>{event.ground_truth_severity || "normal"}</Badge></TableCell>
                </TableRow>
              ))) : (
                <TableRow><TableCell colSpan={7} className="py-8 text-center text-sm text-text-secondary">No events in the selected table</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
          {!eventsExpanded && eventsData.length > 5 ? (
            <div className="border-t border-border-subtle px-4 py-3 text-xs text-text-secondary">
              Showing the latest 5 entries. Expand the panel to inspect the full event list.
            </div>
          ) : null}
      </CardContent>
</Card>
    </div>
  );
}
