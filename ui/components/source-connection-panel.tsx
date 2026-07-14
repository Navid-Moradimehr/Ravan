"use client";

import { useState } from "react";
import { Cable, CircleCheck, CircleX, Pencil, Plus, Power, Radio, Router, Server, TestTube, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { HelpTip } from "@/components/help-tip";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";

type Connection = {
  connection_id: string;
  name: string;
  source_protocol: string;
  site_id: string;
  endpoint: string;
  credential_ref?: string;
  source_id?: string;
  config?: Record<string, unknown>;
  mappings?: Array<Record<string, unknown>>;
  state: string;
  config_version: number;
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
  last_mapping_match?: string;
  last_mapping_miss?: string;
};

async function getConnections(): Promise<{ connections: Connection[] }> {
  return requestJson("/api/connections");
}

async function getSourceHealth(): Promise<{ current: SourceHealth[] }> {
  return requestJson("/api/observability/source-health");
}

function iconFor(protocol: string) {
  if (protocol === "opcua") return Server;
  if (protocol === "mqtt" || protocol === "sparkplug_b") return Radio;
  if (protocol === "modbus" || protocol === "modbus_rtu") return Router;
  return Cable;
}

export function SourceConnectionPanel() {
  const emptyJson = "{}";
  const [name, setName] = useState("");
  const [protocol, setProtocol] = useState("opcua");
  const [siteId, setSiteId] = useState("demo-site");
  const [endpoint, setEndpoint] = useState("");
  const [credentialRef, setCredentialRef] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [configJson, setConfigJson] = useState(emptyJson);
  const [mappingsJson, setMappingsJson] = useState("[]");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);
  const queryClient = useQueryClient();
  const connections = useQuery({ queryKey: ["connections"], queryFn: getConnections });
  const sourceHealth = useQuery({ queryKey: ["source-health"], queryFn: getSourceHealth, refetchInterval: 10000 });
  const add = useMutation({
    mutationFn: (payload: object) => requestJson("/api/connections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      resetForm();
      showToast({ title: "Connection saved", description: "The source is configured but remains disabled until it is validated and enabled.", variant: "success" });
    },
    onError: (error) => showToast({ title: "Connection not saved", description: formatErrorMessage(error, "The source definition could not be saved."), variant: "error" }),
  });
  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: object }) => requestJson(`/api/connections/${encodeURIComponent(id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["connections"] }); resetForm(); showToast({ title: "Connection updated", description: "The source definition was saved without exposing secret values.", variant: "success" }); },
    onError: (error) => showToast({ title: "Connection not updated", description: formatErrorMessage(error, "The source definition could not be updated."), variant: "error" }),
  });
  const validate = useMutation({
    mutationFn: (id: string) => requestJson<{ valid: boolean; errors: string[] }>(`/api/connections/${encodeURIComponent(id)}/validate`, { method: "POST" }),
    onSuccess: (result) => showToast({ title: result.valid ? "Connection definition is valid" : "Connection definition has errors", description: result.valid ? "Network connectivity was not tested." : result.errors.join(" "), variant: result.valid ? "success" : "error" }),
    onError: (error) => showToast({ title: "Validation failed", description: formatErrorMessage(error, "The source definition could not be validated."), variant: "error" }),
  });
  const test = useMutation({
    mutationFn: (id: string) => requestJson(`/api/connections/${encodeURIComponent(id)}/test`, { method: "POST" }),
    onSuccess: (result: any) => showToast({ title: `Connection test: ${result.network_test}`, description: result.network_error || "No data was published by the test.", variant: result.network_test === "reachable" || result.network_test === "not_required" ? "success" : "error" }),
    onError: (error) => showToast({ title: "Connection test failed", description: formatErrorMessage(error, "The connection test could not run."), variant: "error" }),
  });
  const preview = useMutation({
    mutationFn: (id: string) => requestJson<Record<string, unknown>>(`/api/connections/${encodeURIComponent(id)}/preview`, { method: "POST" }),
    onSuccess: (result: Record<string, unknown>) => { setPreviewResult(result); showToast({ title: "Source preview ready", description: result.tags ? `${(result.tags as unknown[]).length} OPC UA tags discovered.` : `Preview mode: ${String(result.preview)}.`, variant: "success" }); },
    onError: (error) => showToast({ title: "Source preview failed", description: formatErrorMessage(error, "The source preview could not run."), variant: "error" }),
  });

  function resetForm() {
    setName(""); setEndpoint(""); setCredentialRef(""); setSourceId(""); setConfigJson(emptyJson); setMappingsJson("[]"); setEditingId(null);
  }

  function parseJson(value: string, label: string) {
    try { return JSON.parse(value); } catch { throw new Error(`${label} must be valid JSON.`); }
  }

  function payload() {
    const config = parseJson(configJson, "Protocol configuration");
    const mappings = parseJson(mappingsJson, "Mappings");
    if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error("Protocol configuration must be a JSON object.");
    if (!Array.isArray(mappings)) throw new Error("Mappings must be a JSON array.");
    return { name, source_protocol: protocol, site_id: siteId, endpoint, source_id: sourceId, credential_ref: credentialRef, config, mappings };
  }

  function edit(connection: Connection) {
    setEditingId(connection.connection_id); setName(connection.name); setProtocol(connection.source_protocol); setSiteId(connection.site_id); setEndpoint(connection.endpoint); setCredentialRef(connection.credential_ref ?? ""); setSourceId(connection.source_id ?? ""); setConfigJson(JSON.stringify(connection.config ?? {}, null, 2)); setMappingsJson(JSON.stringify(connection.mappings ?? [], null, 2)); setPreviewResult(null);
  }
  const lifecycle = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "enable" | "disable" }) => requestJson(`/api/connections/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["connections"] }); queryClient.invalidateQueries({ queryKey: ["source-health"] }); showToast({ title: "Source state updated", description: "The edge runtime will reconcile the new desired state.", variant: "success" }); },
    onError: (error) => showToast({ title: "Source state not updated", description: formatErrorMessage(error), variant: "error" }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => requestJson(`/api/connections/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["connections"] }); showToast({ title: "Source removed", description: "The edge runtime will stop it on the next reconciliation.", variant: "success" }); },
    onError: (error) => showToast({ title: "Source not removed", description: formatErrorMessage(error), variant: "error" }),
  });

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Cable className="size-4 text-accent" /> Source connections
          <HelpTip label="Source connections help" content="Create a deployment source definition here. The platform stores endpoint metadata and a reference to operator-managed credentials; it never stores passwords or certificates. Save, test, then enable the source through the deployment/API security boundary." />
        </CardTitle>
        <CardDescription className="text-text-secondary">The operational bridge between plant protocols and Kafka.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <label className="space-y-1 text-xs text-text-secondary">Connection name<Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Connection name" /></label>
          <label className="space-y-1 text-xs text-text-secondary">Protocol<select aria-label="Source protocol" value={protocol} onChange={(event) => setProtocol(event.target.value)} className="app-select w-full">
            <option value="opcua">OPC UA</option><option value="mqtt">MQTT</option><option value="modbus">Modbus TCP</option><option value="modbus_rtu">Modbus RTU</option><option value="rest">REST</option>
          </select></label>
          <label className="space-y-1 text-xs text-text-secondary">Site ID<Input value={siteId} onChange={(event) => setSiteId(event.target.value)} placeholder="Site ID" /></label>
          <label className="space-y-1 text-xs text-text-secondary">Endpoint<Input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="opc.tcp://host:4840" /></label>
          <div className="flex items-end gap-2"><Button disabled={!name || !endpoint || add.isPending || update.isPending} onClick={() => { try { const body = payload(); editingId ? update.mutate({ id: editingId, payload: body }) : add.mutate(body); } catch (error) { showToast({ title: "Source not saved", description: formatErrorMessage(error), variant: "error" }); } }}><Plus className="size-4" /> {editingId ? "Update" : "Save"}</Button>{editingId ? <Button variant="outline" onClick={resetForm}>Cancel</Button> : null}</div>
        </div>
        <div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Credential reference<Input value={credentialRef} onChange={(event) => setCredentialRef(event.target.value)} placeholder="secret://plant-a/opcua/pump" /></label><label className="space-y-1 text-xs text-text-secondary">Source ID<Input value={sourceId} onChange={(event) => setSourceId(event.target.value)} placeholder="Optional source identifier" /></label><div className="text-xs leading-5 text-text-secondary">Credentials remain user-owned references. The editor never accepts or stores passwords, keys, or certificates.</div></div>
        <div className="grid gap-3 lg:grid-cols-2"><label className="space-y-1 text-xs text-text-secondary">Protocol configuration JSON<textarea aria-label="Protocol configuration JSON" className="app-textarea min-h-24 w-full font-mono text-xs" value={configJson} onChange={(event) => setConfigJson(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Field mappings JSON<textarea aria-label="Field mappings JSON" className="app-textarea min-h-24 w-full font-mono text-xs" value={mappingsJson} onChange={(event) => setMappingsJson(event.target.value)} /></label></div>
        <p className="text-xs leading-5 text-text-secondary">Save creates metadata only. It does not connect, publish, or store secrets. Test with the button, then activate with <code>POST /api/v1/connections/&lt;id&gt;/enable</code> through the operator&apos;s configured API security boundary.</p>
        {connections.isError ? <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm">{formatErrorMessage(connections.error, "Connections could not be loaded.")}</p> : null}
        {sourceHealth.isError ? <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-text-primary">Mapping diagnostics are temporarily unavailable, so live match counts are hidden until the observability endpoint recovers.</p> : null}
        <div className="space-y-2">
          {(connections.data?.connections ?? []).map((connection) => {
            const Icon = iconFor(connection.source_protocol);
            const health = sourceHealth.data?.current.find((item) => item.connection_id === connection.connection_id);
            const mappingSummary = health && typeof health.mapping_seen === "number" ? `${health.mapping_matched ?? 0}/${health.mapping_seen} matched` : "";
            const mappingWarning = health && typeof health.mapping_missed === "number" && health.mapping_missed > 0;
            return <div key={connection.connection_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-0 p-3">
              <div className="flex min-w-0 items-center gap-3"><Icon className="size-4 shrink-0 text-accent" /><div className="min-w-0"><p className="truncate text-sm font-medium">{connection.name}</p><p className="truncate font-mono text-xs text-text-secondary">{connection.endpoint}</p></div></div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{connection.source_protocol}</Badge><Badge variant="outline">v{connection.config_version}</Badge><Badge variant="outline">{connection.state}</Badge>
                {mappingSummary ? <Badge variant={mappingWarning ? "destructive" : "outline"}>{mappingSummary}</Badge> : null}
                <Button variant="ghost" size="sm" onClick={() => edit(connection)}><Pencil className="size-4" /> Edit</Button><Button variant="ghost" size="sm" onClick={() => validate.mutate(connection.connection_id)} disabled={validate.isPending}>Validate</Button><Button variant="ghost" size="sm" onClick={() => test.mutate(connection.connection_id)} disabled={test.isPending}><TestTube className="size-4" /> Test</Button><Button variant="ghost" size="sm" onClick={() => preview.mutate(connection.connection_id)} disabled={preview.isPending}>Preview</Button><Button variant="ghost" size="sm" onClick={() => lifecycle.mutate({ id: connection.connection_id, action: connection.state === "enabled" ? "disable" : "enable" })} disabled={lifecycle.isPending}><Power className="size-4" /> {connection.state === "enabled" ? "Disable" : "Enable"}</Button><Button variant="ghost" size="sm" onClick={() => { if (window.confirm(`Remove ${connection.name}?`)) remove.mutate(connection.connection_id); }} disabled={remove.isPending}><Trash2 className="size-4" /> Remove</Button>{connection.state === "enabled" ? <CircleCheck className="size-4 text-success" /> : <CircleX className="size-4 text-text-muted" />}</div>
              {mappingWarning ? <p className="w-full text-xs text-warning">Configured mappings are enabled, but live traffic has produced mapping misses. Check source_field, source_id, and tag alignment.</p> : null}
            </div>;
          })}
          {!connections.isLoading && (connections.data?.connections ?? []).length === 0 ? <p className="text-sm text-text-secondary">No registry connections yet. Existing environment-variable sources remain available to the edge runtime.</p> : null}
        </div>
        {previewResult ? <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium">Preview result</p><Button variant="ghost" size="sm" onClick={() => setPreviewResult(null)}>Dismiss</Button></div><pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-text-secondary">{JSON.stringify(previewResult, null, 2)}</pre></div> : null}
      </CardContent>
    </Card>
  );
}
