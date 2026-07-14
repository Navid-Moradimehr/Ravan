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
  credential_refs?: Record<string, string>;
  source_id?: string;
  config?: Record<string, unknown>;
  mappings?: Array<Record<string, unknown>>;
  state: string;
  config_version: number;
  retired_at?: string | null;
  retired_reason?: string;
  runtime_supported?: boolean;
  runtime_note?: string;
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

type MappingRow = {
  source_field: string;
  asset_id: string;
  tag: string;
  unit: string;
  scale: string;
  offset: string;
};

const emptyMapping: MappingRow = { source_field: "", asset_id: "", tag: "", unit: "", scale: "1", offset: "0" };

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
  const [credentialRefs, setCredentialRefs] = useState({ username: "", password: "", certificate: "", private_key: "", ca_cert: "", client_cert: "", client_key: "" });
  const [sourceId, setSourceId] = useState("");
  const [configJson, setConfigJson] = useState(emptyJson);
  const [mappingsJson, setMappingsJson] = useState("[]");
  const [mappingRows, setMappingRows] = useState<MappingRow[]>([{ ...emptyMapping }]);
  const [nodesText, setNodesText] = useState("");
  const [topic, setTopic] = useState("");
  const [mqttQos, setMqttQos] = useState("1");
  const [payloadMode, setPayloadMode] = useState("json");
  const [modbusAsset, setModbusAsset] = useState("");
  const [registersText, setRegistersText] = useState("");
  const [rtuPort, setRtuPort] = useState("");
  const [baudrate, setBaudrate] = useState("9600");
  const [slaveId, setSlaveId] = useState("1");
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
    mutationFn: (id: string) => requestJson<{ valid: boolean; errors: string[]; runtime_supported?: boolean; runtime_note?: string }>(`/api/connections/${encodeURIComponent(id)}/validate`, { method: "POST" }),
    onSuccess: (result) => {
      if (!result.valid) {
        showToast({ title: "Connection definition has errors", description: result.errors.join(" "), variant: "error" });
        return;
      }
      if (result.runtime_supported === false) {
        showToast({
          title: "Connection is metadata only",
          description: result.runtime_note ?? "This protocol is not started by the edge runtime.",
          variant: "warning",
        });
        return;
      }
      showToast({ title: "Connection definition is valid", description: "Network connectivity was not tested.", variant: "success" });
    },
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
    setName(""); setEndpoint(""); setCredentialRef(""); setCredentialRefs({ username: "", password: "", certificate: "", private_key: "", ca_cert: "", client_cert: "", client_key: "" }); setSourceId(""); setConfigJson(emptyJson); setMappingsJson("[]"); setMappingRows([{ ...emptyMapping }]); setNodesText(""); setTopic(""); setMqttQos("1"); setPayloadMode("json"); setModbusAsset(""); setRegistersText(""); setRtuPort(""); setBaudrate("9600"); setSlaveId("1"); setEditingId(null);
  }

  function parseJson(value: string, label: string) {
    try { return JSON.parse(value); } catch { throw new Error(`${label} must be valid JSON.`); }
  }

  function payload() {
    let config: Record<string, unknown> = {};
    if (["opcua", "opcua_discovery"].includes(protocol)) config = { nodes: nodesText.split(/[\n,]/).map((item) => item.trim()).filter(Boolean) };
    else if (["mqtt", "sparkplug_b"].includes(protocol)) config = { topic, qos: Number(mqttQos), payload_mode: protocol === "sparkplug_b" ? "sparkplug_b" : payloadMode };
    else if (protocol === "modbus") config = { asset_id: modbusAsset, registers: registersText.split("\n").map((line) => { const [address, tag, unit, scale, offset, unit_id] = line.split(",").map((item) => item.trim()); return { address: Number(address), tag, unit, scale: Number(scale || 1), offset: Number(offset || 0), unit_id: Number(unit_id || 1) }; }).filter((item) => Number.isFinite(item.address) && item.tag) };
    else if (protocol === "modbus_rtu") config = { port: rtuPort, baudrate: Number(baudrate), slave_id: Number(slaveId), registers: registersText };
    else config = parseJson(configJson, "Advanced protocol configuration");
    const mappings = mappingRows.filter((row) => row.source_field.trim() || row.asset_id.trim() || row.tag.trim()).map((row) => ({ source_field: row.source_field.trim(), asset_id: row.asset_id.trim(), tag: row.tag.trim(), unit: row.unit.trim(), scale: Number(row.scale || 1), offset: Number(row.offset || 0) }));
    const refs = Object.fromEntries(Object.entries(credentialRefs).filter(([, value]) => value.trim()));
    return { name, source_protocol: protocol, site_id: siteId, endpoint, source_id: sourceId, credential_ref: credentialRef, credential_refs: refs, config, mappings };
  }

  function edit(connection: Connection) {
    const config = connection.config ?? {};
    const rows = (connection.mappings ?? []).map((row) => ({ source_field: String(row.source_field ?? ""), asset_id: String(row.asset_id ?? ""), tag: String(row.tag ?? ""), unit: String(row.unit ?? ""), scale: String(row.scale ?? 1), offset: String(row.offset ?? 0) }));
    setEditingId(connection.connection_id); setName(connection.name); setProtocol(connection.source_protocol); setSiteId(connection.site_id); setEndpoint(connection.endpoint); setCredentialRef(connection.credential_ref ?? ""); setCredentialRefs({ username: connection.credential_refs?.username ?? "", password: connection.credential_refs?.password ?? "", certificate: connection.credential_refs?.certificate ?? "", private_key: connection.credential_refs?.private_key ?? "", ca_cert: connection.credential_refs?.ca_cert ?? "", client_cert: connection.credential_refs?.client_cert ?? "", client_key: connection.credential_refs?.client_key ?? "" }); setSourceId(connection.source_id ?? ""); setConfigJson(JSON.stringify(config, null, 2)); setMappingsJson(JSON.stringify(connection.mappings ?? [], null, 2)); setMappingRows(rows.length ? rows : [{ ...emptyMapping }]); setNodesText(Array.isArray(config.nodes) ? config.nodes.join("\n") : ""); setTopic(String(config.topic ?? "")); setMqttQos(String(config.qos ?? 1)); setPayloadMode(String(config.payload_mode ?? "json")); setModbusAsset(String(config.asset_id ?? "")); setRegistersText(Array.isArray(config.registers) ? config.registers.map((row: any) => [row.address, row.tag, row.unit ?? "", row.scale ?? 1, row.offset ?? 0, row.unit_id ?? 1].join(",")).join("\n") : String(config.registers ?? "")); setRtuPort(String(config.port ?? "")); setBaudrate(String(config.baudrate ?? 9600)); setSlaveId(String(config.slave_id ?? 1)); setPreviewResult(null);
  }
  const lifecycle = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "enable" | "disable" }) => requestJson(`/api/connections/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["connections"] }); queryClient.invalidateQueries({ queryKey: ["source-health"] }); showToast({ title: "Source state updated", description: "The edge runtime will reconcile the new desired state.", variant: "success" }); },
    onError: (error) => showToast({ title: "Source state not updated", description: formatErrorMessage(error), variant: "error" }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => requestJson(`/api/connections/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["connections"] }); showToast({ title: "Source retired", description: "The source was removed from the active runtime and preserved for history.", variant: "success" }); },
    onError: (error) => showToast({ title: "Source not retired", description: formatErrorMessage(error), variant: "error" }),
  });
  const restore = useMutation({
    mutationFn: (id: string) => requestJson(`/api/connections/${encodeURIComponent(id)}/restore`, { method: "POST" }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["connections"] }); showToast({ title: "Source restored", description: "The source can now be validated and enabled again.", variant: "success" }); },
    onError: (error) => showToast({ title: "Source not restored", description: formatErrorMessage(error), variant: "error" }),
  });

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Cable className="size-4 text-accent" /> Source connections
          <HelpTip label="Source connections help" content="Add a PLC, sensor gateway, broker, or supported source without editing backend code. Choose a protocol, enter its endpoint and fields, reference operator-managed credentials, save, test, preview when available, and press Enable. The platform stores definitions and runtime state, never secret values." />
        </CardTitle>
        <CardDescription className="text-text-secondary">The operational bridge between plant protocols and Kafka.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <label className="space-y-1 text-xs text-text-secondary">Connection name<Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Connection name" /></label>
          <label className="space-y-1 text-xs text-text-secondary">Protocol<select aria-label="Source protocol" value={protocol} onChange={(event) => setProtocol(event.target.value)} className="app-select w-full">
            <option value="opcua">OPC UA</option><option value="mqtt">MQTT</option><option value="sparkplug_b">Sparkplug B over MQTT</option><option value="modbus">Modbus TCP</option><option value="modbus_rtu">Modbus RTU</option><option value="opcua_discovery">OPC UA Discovery</option><option value="rest">REST (metadata-only)</option><option value="file">File (metadata-only)</option><option value="dataset">Dataset replay (metadata-only)</option><option value="mock">Mock generator (metadata-only)</option>
          </select></label>
          <label className="space-y-1 text-xs text-text-secondary">Site ID<Input value={siteId} onChange={(event) => setSiteId(event.target.value)} placeholder="Site ID" /></label>
          <label className="space-y-1 text-xs text-text-secondary">Endpoint<Input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="opc.tcp://host:4840" /></label>
          <div className="flex items-end gap-2"><Button disabled={!name || !endpoint || add.isPending || update.isPending} onClick={() => { try { const body = payload(); editingId ? update.mutate({ id: editingId, payload: body }) : add.mutate(body); } catch (error) { showToast({ title: "Source not saved", description: formatErrorMessage(error), variant: "error" }); } }}><Plus className="size-4" /> {editingId ? "Update" : "Save"}</Button>{editingId ? <Button variant="outline" onClick={resetForm}>Cancel</Button> : null}</div>
        </div>
        <div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Legacy credential reference<Input value={credentialRef} onChange={(event) => setCredentialRef(event.target.value)} placeholder="secret://plant-a/opcua/pump" /></label><label className="space-y-1 text-xs text-text-secondary">Source ID<Input value={sourceId} onChange={(event) => setSourceId(event.target.value)} placeholder="Optional source identifier" /></label><div className="text-xs leading-5 text-text-secondary">References point to operator-managed secrets. Values are never accepted or returned by this UI.</div></div>
        <div className="rounded-lg border border-border-subtle bg-surface-1 p-3"><div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium">Protocol settings</p><HelpTip label="Protocol settings help" content="These fields become the edge connector definition. Use env://NAME or file://path references for credentials. The platform reads the referenced value only inside the edge runtime." /></div>
          {["opcua", "opcua_discovery"].includes(protocol) ? <label className="block space-y-1 text-xs text-text-secondary">OPC UA node IDs, one per line<textarea className="app-textarea min-h-20 w-full" value={nodesText} onChange={(event) => setNodesText(event.target.value)} placeholder="ns=2;s=Pump-01.Temperature" /></label> : null}
          {["mqtt", "sparkplug_b"].includes(protocol) ? <div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Topic filter<Input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="factory/+/+/+" /></label><label className="space-y-1 text-xs text-text-secondary">QoS<Input type="number" min="0" max="2" value={mqttQos} onChange={(event) => setMqttQos(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Payload mode<select className="app-select w-full" value={payloadMode} onChange={(event) => setPayloadMode(event.target.value)}><option value="json">JSON</option><option value="sparkplug_b">Sparkplug B</option></select></label></div> : null}
          {protocol === "modbus" ? <div className="space-y-3"><label className="block space-y-1 text-xs text-text-secondary">Asset ID<Input value={modbusAsset} onChange={(event) => setModbusAsset(event.target.value)} placeholder="Pump-03" /></label><label className="block space-y-1 text-xs text-text-secondary">Holding registers<textarea className="app-textarea min-h-20 w-full font-mono text-xs" value={registersText} onChange={(event) => setRegistersText(event.target.value)} placeholder="address,tag,unit,scale,offset,unit_id&#10;0,Temperature,C,0.1,0,1" /></label></div> : null}
          {protocol === "modbus_rtu" ? <div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Serial port<Input value={rtuPort} onChange={(event) => setRtuPort(event.target.value)} placeholder="/dev/ttyUSB0 or COM3" /></label><label className="space-y-1 text-xs text-text-secondary">Baud rate<Input type="number" value={baudrate} onChange={(event) => setBaudrate(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Slave ID<Input type="number" value={slaveId} onChange={(event) => setSlaveId(event.target.value)} /></label></div> : null}
          {["rest", "file", "dataset", "mock"].includes(protocol) ? <label className="block space-y-1 text-xs text-text-secondary">Advanced configuration JSON<textarea aria-label="Advanced protocol configuration JSON" className="app-textarea min-h-20 w-full font-mono text-xs" value={configJson} onChange={(event) => setConfigJson(event.target.value)} /></label> : null}
          <div className="mt-3 grid gap-3 md:grid-cols-2"><label className="space-y-1 text-xs text-text-secondary">Username reference<Input value={credentialRefs.username} onChange={(event) => setCredentialRefs({ ...credentialRefs, username: event.target.value })} placeholder="env://PLC_USERNAME" /></label><label className="space-y-1 text-xs text-text-secondary">Password reference<Input value={credentialRefs.password} onChange={(event) => setCredentialRefs({ ...credentialRefs, password: event.target.value })} placeholder="file://C:/secrets/plc-password" /></label><label className="space-y-1 text-xs text-text-secondary">Certificate path reference<Input value={credentialRefs.certificate} onChange={(event) => setCredentialRefs({ ...credentialRefs, certificate: event.target.value })} placeholder="path://C:/secrets/client.crt" /></label><label className="space-y-1 text-xs text-text-secondary">Private key path reference<Input value={credentialRefs.private_key} onChange={(event) => setCredentialRefs({ ...credentialRefs, private_key: event.target.value })} placeholder="path://C:/secrets/client.key" /></label><label className="space-y-1 text-xs text-text-secondary">MQTT CA path reference<Input value={credentialRefs.ca_cert} onChange={(event) => setCredentialRefs({ ...credentialRefs, ca_cert: event.target.value })} placeholder="path://C:/secrets/ca.crt" /></label><label className="space-y-1 text-xs text-text-secondary">MQTT client certificate/key paths<Input value={credentialRefs.client_cert} onChange={(event) => setCredentialRefs({ ...credentialRefs, client_cert: event.target.value })} placeholder="path://C:/secrets/client.crt" /><Input value={credentialRefs.client_key} onChange={(event) => setCredentialRefs({ ...credentialRefs, client_key: event.target.value })} placeholder="path://C:/secrets/client.key" /></label></div>
        </div>
        <div className="rounded-lg border border-border-subtle bg-surface-1 p-3"><div className="mb-2 flex items-center justify-between"><div><p className="text-sm font-medium">Signal mapping</p><p className="text-xs text-text-secondary">Map discovered source fields to the platform&apos;s asset and tag identity.</p></div><Button variant="outline" size="sm" onClick={() => setMappingRows([...mappingRows, { ...emptyMapping }])}><Plus className="size-4" /> Add mapping</Button></div><div className="space-y-2">{mappingRows.map((row, index) => <div key={index} className="grid gap-2 rounded-md border border-border-subtle p-2 md:grid-cols-[1.2fr_1fr_1fr_.8fr_.6fr_.6fr_auto]"><Input placeholder="Source field" value={row.source_field} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, source_field: event.target.value } : item))} /><Input placeholder="Asset ID" value={row.asset_id} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, asset_id: event.target.value } : item))} /><Input placeholder="Tag" value={row.tag} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, tag: event.target.value } : item))} /><Input placeholder="Unit" value={row.unit} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, unit: event.target.value } : item))} /><Input placeholder="Scale" value={row.scale} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, scale: event.target.value } : item))} /><Input placeholder="Offset" value={row.offset} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, offset: event.target.value } : item))} /><Button variant="ghost" size="sm" aria-label={`Remove mapping ${index + 1}`} onClick={() => setMappingRows(mappingRows.length === 1 ? [{ ...emptyMapping }] : mappingRows.filter((_, i) => i !== index))}>Remove</Button></div>)}</div></div>
        <p className="text-xs leading-5 text-text-secondary">Save stores the desired connection definition. Test performs a bounded connection check, and Enable activates the connector from this page. No backend code change or manual lifecycle API call is required for supported runtime protocols. REST, file, dataset, and mock remain metadata-only until their dedicated ingestion workflows are used.</p>
        <p className="text-xs leading-5 text-text-secondary">Editing preserves the source&apos;s current runtime state. Retiring a source archives it for audit and replacement history instead of deleting it outright.</p>
        {connections.isError ? <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm">{formatErrorMessage(connections.error, "Connections could not be loaded.")}</p> : null}
        {sourceHealth.isError ? <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-text-primary">Mapping diagnostics are temporarily unavailable, so live match counts are hidden until the observability endpoint recovers.</p> : null}
        <div className="space-y-2">
          {(connections.data?.connections ?? []).map((connection) => {
            const Icon = iconFor(connection.source_protocol);
            const health = sourceHealth.data?.current.find((item) => item.connection_id === connection.connection_id);
            const mappingSummary = health && typeof health.mapping_seen === "number" ? `${health.mapping_matched ?? 0}/${health.mapping_seen} matched` : "";
            const mappingWarning = health && typeof health.mapping_missed === "number" && health.mapping_missed > 0;
            const retired = connection.state === "retired";
            const runtimeSupported = connection.runtime_supported !== false && !retired;
            return <div key={connection.connection_id} className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 ${retired ? "border-border-subtle bg-surface-1 opacity-85" : "border-border-subtle bg-surface-0"}`}>
              <div className="flex min-w-0 items-center gap-3"><Icon className="size-4 shrink-0 text-accent" /><div className="min-w-0"><p className="truncate text-sm font-medium">{connection.name}</p><p className="truncate font-mono text-xs text-text-secondary">{connection.endpoint}</p></div></div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{connection.source_protocol}</Badge><Badge variant="outline">v{connection.config_version}</Badge><Badge variant={retired ? "secondary" : "outline"}>{connection.state}</Badge>{runtimeSupported ? <Badge variant="outline" className="border-success/30 bg-success/10 text-success">runtime-ready</Badge> : <Badge variant="outline" className="border-warning/30 bg-warning/10 text-warning">{retired ? "archived" : "metadata-only"}</Badge>}
                {mappingSummary ? <Badge variant={mappingWarning ? "destructive" : "outline"}>{mappingSummary}</Badge> : null}
                <Button variant="ghost" size="sm" onClick={() => edit(connection)}><Pencil className="size-4" /> Edit</Button>
                {!retired ? <Button variant="ghost" size="sm" onClick={() => validate.mutate(connection.connection_id)} disabled={validate.isPending}>Validate</Button> : null}
                {!retired ? <Button variant="ghost" size="sm" onClick={() => test.mutate(connection.connection_id)} disabled={test.isPending}><TestTube className="size-4" /> Test</Button> : null}
                {!retired ? <Button variant="ghost" size="sm" onClick={() => preview.mutate(connection.connection_id)} disabled={preview.isPending}>Preview</Button> : null}
                {!retired ? <Button variant="ghost" size="sm" onClick={() => lifecycle.mutate({ id: connection.connection_id, action: connection.state === "enabled" ? "disable" : "enable" })} disabled={lifecycle.isPending || !runtimeSupported}><Power className="size-4" /> {connection.state === "enabled" ? "Disable" : "Enable"}</Button> : null}
                {retired ? <Button variant="ghost" size="sm" onClick={() => restore.mutate(connection.connection_id)} disabled={restore.isPending}><Power className="size-4" /> Restore</Button> : <Button variant="ghost" size="sm" onClick={() => { if (window.confirm(`Retire ${connection.name}? It will be preserved for audit history.`)) remove.mutate(connection.connection_id); }} disabled={remove.isPending}><Trash2 className="size-4" /> Retire</Button>}
                {connection.state === "enabled" ? <CircleCheck className="size-4 text-success" /> : <CircleX className="size-4 text-text-muted" />}
              </div>
              {mappingWarning ? <p className="w-full text-xs text-warning">Configured mappings are enabled, but live traffic has produced mapping misses. Check source_field, source_id, and tag alignment.</p> : null}
              {retired ? <p className="w-full text-xs text-text-secondary">This source is archived. Its record stays available for audit and replacement history until you restore it.</p> : null}
              {!runtimeSupported ? <p className="w-full text-xs text-warning">{connection.runtime_note ?? "This source is metadata only and cannot be started by the edge runtime."}</p> : null}
            </div>;
          })}
          {!connections.isLoading && (connections.data?.connections ?? []).length === 0 ? <p className="text-sm text-text-secondary">No registry connections yet. Existing environment-variable sources remain available to the edge runtime.</p> : null}
        </div>
        {previewResult ? <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium">Preview result</p><Button variant="ghost" size="sm" onClick={() => setPreviewResult(null)}>Dismiss</Button></div><pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-text-secondary">{JSON.stringify(previewResult, null, 2)}</pre></div> : null}
      </CardContent>
    </Card>
  );
}
