"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Database, FolderTree, Play, Square, TrendingUp } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { getHistorianTrend, getAssetHierarchy, getScenarios, getReplayStatus, startReplay, stopReplay, subscribeHistorianStream, subscribeEventsWebSocket, type HistorianStreamPayload } from "@/lib/api";

function TrendChart({ data }: { data: { time: string; value: number }[] }) {
  if (!data.length) return <p className="text-sm text-text-secondary">No data</p>;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 400;
  const height = 120;
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((d.value - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-32">
      <polyline fill="none" stroke="var(--accent)" strokeWidth={2} points={points} />
      {data.map((d, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((d.value - min) / range) * height;
        return <circle key={i} cx={x} cy={y} r={3} fill="var(--accent)" />;
      })}
    </svg>
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
  const queryClient = useQueryClient();

  // WebSocket-driven state for alarms and events
  const [streamAlarms, setStreamAlarms] = useState<any[]>([]);
  const [streamEvents, setStreamEvents] = useState<any[]>([]);
  const [isStreamConnected, setIsStreamConnected] = useState(false);
  const prevAlarmsRef = useRef<string>("");
  const prevEventsRef = useRef<string>("");

  const handleAlarmPayload = useCallback((payload: HistorianStreamPayload) => {
    if (payload.type === "init" || payload.type === "update") {
      if (payload.alarms) {
        const serialized = JSON.stringify(payload.alarms);
        if (serialized !== prevAlarmsRef.current) {
          prevAlarmsRef.current = serialized;
          setStreamAlarms(payload.alarms);
        }
      }
    }
  }, []);

  const handleEventPayload = useCallback((payload: HistorianStreamPayload) => {
    if (payload.type === "init" || payload.type === "update") {
      if (payload.events) {
        const serialized = JSON.stringify(payload.events);
        if (serialized !== prevEventsRef.current) {
          prevEventsRef.current = serialized;
          setStreamEvents(payload.events);
        }
      }
    }
  }, []);

  useEffect(() => {
    const wsBase = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8020";
    const cleanupAlarms = subscribeHistorianStream({
      onPayload: handleAlarmPayload,
      onConnect: () => setIsStreamConnected(true),
      onDisconnect: () => setIsStreamConnected(false),
      onError: () => setIsStreamConnected(false),
    }, wsBase);
    const cleanupEvents = subscribeEventsWebSocket({
      onPayload: handleEventPayload,
      onConnect: () => setIsStreamConnected(true),
      onDisconnect: () => setIsStreamConnected(false),
      onError: () => setIsStreamConnected(false),
    }, wsBase);
    return () => {
      cleanupAlarms();
      cleanupEvents();
    };
  }, [handleAlarmPayload, handleEventPayload]);

  const trendQuery = useQuery({ queryKey: ["historian", "trend", selectedAsset?.assetId, selectedAsset?.tag], queryFn: () => selectedAsset ? getHistorianTrend(selectedAsset.assetId, selectedAsset.tag, 1) : Promise.resolve([]), enabled: !!selectedAsset });
  const assetsQuery = useQuery({ queryKey: ["historian", "assets"], queryFn: getAssetHierarchy });
  const scenariosQuery = useQuery({ queryKey: ["historian", "scenarios"], queryFn: getScenarios });
  const replayQuery = useQuery({ queryKey: ["historian", "replay"], queryFn: getReplayStatus, refetchInterval: 10000 });

  const startReplayMutation = useMutation({ mutationFn: () => startReplay(selectedDataset, selectedScenario), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["historian", "replay"] }); } });
  const stopReplayMutation = useMutation({ mutationFn: stopReplay, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["historian", "replay"] }); } });

  const alarmsData = streamAlarms;
  const eventsData = streamEvents;
  const isAlarmsLoading = !isStreamConnected && streamAlarms.length === 0;
  const isEventsLoading = !isStreamConnected && streamEvents.length === 0;

  return (
    <div className="space-y-5">
      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold"><Play className="size-4 text-accent" />Scenario & Replay</CardTitle>
          <CardDescription className="text-text-secondary">Select dataset and scenario for ground-truth testing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-secondary">Dataset</label>
              <DropdownMenu>
                 <DropdownMenuTrigger>
                   <div className="inline-flex h-9 w-40 items-center justify-between rounded-lg border border-border-subtle bg-surface-2 px-3 text-sm cursor-pointer">{selectedDataset === "ai4i" ? "AI4I Predictive" : "Synthetic"}</div>
                 </DropdownMenuTrigger>
                 <DropdownMenuContent>
                   <DropdownMenuItem onClick={() => setSelectedDataset("ai4i")}>AI4I Predictive</DropdownMenuItem>
                   <DropdownMenuItem onClick={() => setSelectedDataset("synthetic")}>Synthetic</DropdownMenuItem>
                 </DropdownMenuContent>
               </DropdownMenu>
             </div>
             <div className="space-y-1.5">
               <label className="text-xs font-medium text-text-secondary">Scenario</label>
               <DropdownMenu>
                 <DropdownMenuTrigger>
                   <div className="inline-flex h-9 w-48 items-center justify-between rounded-lg border border-border-subtle bg-surface-2 px-3 text-sm cursor-pointer">{scenariosQuery.data?.find((s) => s.id === selectedScenario)?.name ?? "Normal"}</div>
                 </DropdownMenuTrigger>
                 <DropdownMenuContent>
                   {scenariosQuery.data?.map((s) => (
                     <DropdownMenuItem key={s.id} onClick={() => setSelectedScenario(s.id)}>{s.name}</DropdownMenuItem>
                   ))}
                 </DropdownMenuContent>
               </DropdownMenu>
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
            <CardTitle className="flex items-center gap-2 text-base font-semibold"><FolderTree className="size-4 text-accent" />Asset Hierarchy</CardTitle>
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
            <CardTitle className="flex items-center gap-2 text-base font-semibold"><TrendingUp className="size-4 text-accent" />Historical Trend</CardTitle>
            <CardDescription className="text-text-secondary">{selectedAsset ? `${selectedAsset.assetId}.${selectedAsset.tag}` : "Select an asset tag"}</CardDescription>
          </CardHeader>
          <CardContent className="p-4">
            {selectedAsset ? (trendQuery.isLoading ? <Skeleton className="h-32 w-full bg-surface-2" /> : <TrendChart data={trendQuery.data?.map((d: any) => ({ time: d.time, value: d.value })) ?? []} />) : (
              <p className="py-8 text-center text-sm text-text-secondary">Select a tag from the asset hierarchy to view its trend</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold"><AlertTriangle className="size-4 text-accent" />Alarms & Events</CardTitle>
          <CardDescription className="text-text-secondary">Recent warning and critical events from processed stream</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
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
              {isAlarmsLoading ? (Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}><TableCell colSpan={6}><Skeleton className="h-5 w-full bg-surface-2" /></TableCell></TableRow>
              ))) : alarmsData?.length ? (alarmsData.map((alarm: any, i: number) => (
                <TableRow key={i} className="border-border-subtle hover:bg-surface-2">
                  <TableCell className="font-mono text-xs">{new Date(alarm.time).toLocaleTimeString()}</TableCell>
                  <TableCell className="text-sm font-medium">{alarm.asset_id}</TableCell>
                  <TableCell className="text-sm">{alarm.tag}</TableCell>
                  <TableCell><Badge variant="outline" className={alarm.severity === "critical" ? "border-error/30 bg-error/10 text-error" : "border-warning/30 bg-warning/10 text-warning"}>{alarm.severity}</Badge></TableCell>
                  <TableCell className="text-sm text-text-secondary">{alarm.message}</TableCell>
                  <TableCell><div className="flex flex-wrap gap-1">{alarm.triggered_rules?.map((rule: string, j: number) => (<Badge key={j} variant="secondary" className="text-[10px]">{rule}</Badge>))}</div></TableCell>
                </TableRow>
              ))) : (
                <TableRow><TableCell colSpan={6} className="py-8 text-center text-sm text-text-secondary">No alarms in the selected window</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold"><Database className="size-4 text-accent" />Raw Events</CardTitle>
          <CardDescription className="text-text-secondary">Recent events from the historian</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-2">
            <DropdownMenu>
              <DropdownMenuTrigger>
                <div className="inline-flex h-9 w-48 items-center justify-between rounded-lg border border-border-subtle bg-surface-2 px-3 text-sm cursor-pointer">{selectedTable === "industrial_events" ? "Industrial" : selectedTable === "processed_events" ? "Processed" : "AI Enriched"}</div>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setSelectedTable("industrial_events")}>Industrial</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSelectedTable("processed_events")}>Processed</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSelectedTable("ai_enriched")}>AI Enriched</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
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
              ))) : eventsData?.length ? (eventsData.map((event: any, i: number) => (
                <TableRow key={i} className="border-border-subtle hover:bg-surface-2">
                  <TableCell className="font-mono text-xs">{new Date(event.time).toLocaleTimeString()}</TableCell>
                  <TableCell className="text-sm font-medium">{event.asset_id}</TableCell>
                  <TableCell className="text-sm">{event.tag}</TableCell>
                  <TableCell className="font-mono text-sm">{Number(event.value).toFixed(2)}</TableCell>
                  <TableCell><Badge variant="outline" className={event.quality === "good" ? "border-success/30 bg-success/10 text-success" : "border-error/30 bg-error/10 text-error"}>{event.quality}</Badge></TableCell>
                  <TableCell className="text-sm text-text-secondary">{event.fault_type}</TableCell>
                  <TableCell><Badge variant="outline" className={event.ground_truth_severity === "critical" ? "border-error/30 bg-error/10 text-error" : event.ground_truth_severity === "warning" ? "border-warning/30 bg-warning/10 text-warning" : "border-success/30 bg-success/10 text-success"}>{event.ground_truth_severity}</Badge></TableCell>
                </TableRow>
              ))) : (
                <TableRow><TableCell colSpan={7} className="py-8 text-center text-sm text-text-secondary">No events in the selected table</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
