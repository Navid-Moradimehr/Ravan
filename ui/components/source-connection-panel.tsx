"use client";

import { useState } from "react";
import { Cable, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, CircleCheck, CircleX, Pencil, Plus, Power, Radio, Router, Server, TestTube, Trash2 } from "lucide-react";
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
  activation_ready?: boolean;
  activation_errors?: string[];
  capabilities?: string[];
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
  const [credentialRefs, setCredentialRefs] = useState({ username: "", password: "", token: "", api_key: "", client_id: "", client_secret: "", certificate: "", private_key: "", ca_cert: "", client_cert: "", client_key: "" });
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
  const [connectionsExpanded, setConnectionsExpanded] = useState(false);
  const [connectionPage, setConnectionPage] = useState(1);
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [step, setStep] = useState(1);
  const [restMethod, setRestMethod] = useState("GET");
  const [restInterval, setRestInterval] = useState("60");
  const [restTimeout, setRestTimeout] = useState("15");
  const [restRecordsPath, setRestRecordsPath] = useState("");
  const [restSourcePath, setRestSourcePath] = useState("source_id");
  const [restAssetPath, setRestAssetPath] = useState("asset_id");
  const [restTagPath, setRestTagPath] = useState("tag");
  const [restValuePath, setRestValuePath] = useState("value");
  const [restTimestampPath, setRestTimestampPath] = useState("timestamp");
  const [restQualityPath, setRestQualityPath] = useState("quality");
  const [restUnitPath, setRestUnitPath] = useState("unit");
  const [restAuthType, setRestAuthType] = useState("none");
  const [restAuthName, setRestAuthName] = useState("X-API-Key");
  const [restAuthLocation, setRestAuthLocation] = useState("header");
  const [restPageMode, setRestPageMode] = useState("none");
  const [restMaxPages, setRestMaxPages] = useState("10");
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
    mutationFn: (id: string) => requestJson<{ valid: boolean; activation_ready?: boolean; errors: string[]; missing_fields?: string[]; runtime_supported?: boolean; runtime_note?: string }>(`/api/connections/${encodeURIComponent(id)}/validate`, { method: "POST" }),
    onSuccess: (result) => {
      if (!result.valid) {
        showToast({ title: "Connection definition has errors", description: result.errors.join(" "), variant: "error" });
        return;
      }
      if (result.activation_ready === false) {
        showToast({ title: "Activation needs more configuration", description: (result.missing_fields ?? result.errors).join(" "), variant: "warning" });
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
      showToast({ title: "Connection is ready", description: "Configuration is complete. Test connectivity, then Enable the source.", variant: "success" });
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
    setName(""); setProtocol("opcua"); setSiteId("demo-site"); setEndpoint(""); setCredentialRef(""); setCredentialRefs({ username: "", password: "", token: "", api_key: "", client_id: "", client_secret: "", certificate: "", private_key: "", ca_cert: "", client_cert: "", client_key: "" }); setSourceId(""); setConfigJson(emptyJson); setMappingsJson("[]"); setMappingRows([{ ...emptyMapping }]); setNodesText(""); setTopic(""); setMqttQos("1"); setPayloadMode("json"); setModbusAsset(""); setRegistersText(""); setRtuPort(""); setBaudrate("9600"); setSlaveId("1"); setEditingId(null); setStep(1); setPreviewResult(null); setRestMethod("GET"); setRestInterval("60"); setRestTimeout("15"); setRestRecordsPath(""); setRestSourcePath("source_id"); setRestAssetPath("asset_id"); setRestTagPath("tag"); setRestValuePath("value"); setRestTimestampPath("timestamp"); setRestQualityPath("quality"); setRestUnitPath("unit"); setRestAuthType("none"); setRestAuthName("X-API-Key"); setRestAuthLocation("header"); setRestPageMode("none"); setRestMaxPages("10");
  }

  function parseJson(value: string, label: string) {
    try { return JSON.parse(value); } catch { throw new Error(`${label} must be valid JSON.`); }
  }

  function payload() {
    let config: Record<string, unknown> = {};
    if (protocol === "opcua") config = { nodes: nodesText.split(/[\n,]/).map((item) => item.trim()).filter(Boolean) };
    else if (["mqtt", "sparkplug_b"].includes(protocol)) config = { topic, qos: Number(mqttQos), payload_mode: protocol === "sparkplug_b" ? "sparkplug_b" : payloadMode };
    else if (protocol === "modbus") config = { asset_id: modbusAsset, registers: registersText.split("\n").map((line) => { const [address, tag, unit, scale, offset, unit_id] = line.split(",").map((item) => item.trim()); return { address: Number(address), tag, unit, scale: Number(scale || 1), offset: Number(offset || 0), unit_id: Number(unit_id || 1) }; }).filter((item) => Number.isFinite(item.address) && item.tag) };
    else if (protocol === "modbus_rtu") config = { port: rtuPort, baudrate: Number(baudrate), slave_id: Number(slaveId), registers: registersText };
    else if (protocol === "rest") config = { method: restMethod, poll_interval_seconds: Number(restInterval), timeout_seconds: Number(restTimeout), response: { records_path: restRecordsPath, field_paths: { source_id: restSourcePath, asset_id: restAssetPath, tag: restTagPath, value: restValuePath, ts_source: restTimestampPath, quality: restQualityPath, unit: restUnitPath } }, pagination: { mode: restPageMode, max_pages: Number(restMaxPages) }, auth: { type: restAuthType, name: restAuthName, location: restAuthLocation } };
    else if (protocol === "http_push") config = { content_type: "application/json", max_batch_size: 1000 };
    else config = parseJson(configJson, "Advanced protocol configuration");
    const mappings = mappingRows.filter((row) => row.source_field.trim() || row.asset_id.trim() || row.tag.trim()).map((row) => ({ source_field: row.source_field.trim(), asset_id: row.asset_id.trim(), tag: row.tag.trim(), unit: row.unit.trim(), scale: Number(row.scale || 1), offset: Number(row.offset || 0) }));
    const refs = Object.fromEntries(Object.entries(credentialRefs).filter(([, value]) => value.trim()));
    return { name, source_protocol: protocol, site_id: siteId, endpoint, source_id: sourceId, credential_ref: credentialRef, credential_refs: refs, config, mappings };
  }

  function edit(connection: Connection) {
    const config = connection.config ?? {};
    const rows = (connection.mappings ?? []).map((row) => ({ source_field: String(row.source_field ?? ""), asset_id: String(row.asset_id ?? ""), tag: String(row.tag ?? ""), unit: String(row.unit ?? ""), scale: String(row.scale ?? 1), offset: String(row.offset ?? 0) }));
    const response = (config.response ?? {}) as Record<string, any>;
    const paths = (response.field_paths ?? {}) as Record<string, any>;
    const auth = (config.auth ?? {}) as Record<string, any>;
    setEditingId(connection.connection_id); setName(connection.name); setProtocol(connection.source_protocol); setSiteId(connection.site_id); setEndpoint(connection.endpoint); setCredentialRef(connection.credential_ref ?? ""); setCredentialRefs({ username: connection.credential_refs?.username ?? "", password: connection.credential_refs?.password ?? "", token: connection.credential_refs?.token ?? "", api_key: connection.credential_refs?.api_key ?? "", client_id: connection.credential_refs?.client_id ?? "", client_secret: connection.credential_refs?.client_secret ?? "", certificate: connection.credential_refs?.certificate ?? "", private_key: connection.credential_refs?.private_key ?? "", ca_cert: connection.credential_refs?.ca_cert ?? "", client_cert: connection.credential_refs?.client_cert ?? "", client_key: connection.credential_refs?.client_key ?? "" }); setSourceId(connection.source_id ?? ""); setConfigJson(JSON.stringify(config, null, 2)); setMappingsJson(JSON.stringify(connection.mappings ?? [], null, 2)); setMappingRows(rows.length ? rows : [{ ...emptyMapping }]); setNodesText(Array.isArray(config.nodes) ? config.nodes.join("\n") : ""); setTopic(String(config.topic ?? "")); setMqttQos(String(config.qos ?? 1)); setPayloadMode(String(config.payload_mode ?? "json")); setModbusAsset(String(config.asset_id ?? "")); setRegistersText(Array.isArray(config.registers) ? config.registers.map((row: any) => [row.address, row.tag, row.unit ?? "", row.scale ?? 1, row.offset ?? 0, row.unit_id ?? 1].join(",")).join("\n") : String(config.registers ?? "")); setRtuPort(String(config.port ?? "")); setBaudrate(String(config.baudrate ?? 9600)); setSlaveId(String(config.slave_id ?? 1)); setRestMethod(String(config.method ?? "GET")); setRestInterval(String(config.poll_interval_seconds ?? 60)); setRestTimeout(String(config.timeout_seconds ?? 15)); setRestRecordsPath(String(response.records_path ?? "")); setRestSourcePath(String(paths.source_id ?? "source_id")); setRestAssetPath(String(paths.asset_id ?? "asset_id")); setRestTagPath(String(paths.tag ?? "tag")); setRestValuePath(String(paths.value ?? "value")); setRestTimestampPath(String(paths.ts_source ?? "timestamp")); setRestQualityPath(String(paths.quality ?? "quality")); setRestUnitPath(String(paths.unit ?? "unit")); setRestAuthType(String(auth.type ?? "none")); setRestAuthName(String(auth.name ?? "X-API-Key")); setRestAuthLocation(String(auth.location ?? "header")); setRestPageMode(String((config.pagination as any)?.mode ?? "none")); setRestMaxPages(String((config.pagination as any)?.max_pages ?? 10)); setStep(1); setPreviewResult(null);
  }
  function saveConnection() {
    try {
      const body = payload();
      editingId ? update.mutate({ id: editingId, payload: body }) : add.mutate(body);
    } catch (error) {
      showToast({ title: "Source not saved", description: formatErrorMessage(error), variant: "error" });
    }
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
  const allConnections = connections.data?.connections ?? [];
  const totalConnectionPages = Math.max(1, Math.ceil(allConnections.length / 20));
  const visibleConnections = connectionsExpanded
    ? allConnections.slice((Math.min(connectionPage, totalConnectionPages) - 1) * 20, Math.min(connectionPage, totalConnectionPages) * 20)
    : allConnections.slice(0, 5);

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
        <div className="grid gap-2 rounded-lg border border-border-subtle bg-surface-1 p-2 sm:grid-cols-5">
          {["Identity", "Connectivity", "Discover / sample", "Map data", "Review / enable"].map((label, index) => <button key={label} type="button" onClick={() => setStep(index + 1)} className={`rounded-md px-2 py-2 text-left text-xs transition-colors ${step === index + 1 ? "bg-accent/15 text-accent" : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"}`}><span className="mr-1 font-mono">0{index + 1}</span>{label}</button>)}
        </div>
        <div className={`${step === 1 ? "" : "hidden"} grid gap-3 md:grid-cols-2 xl:grid-cols-5`}>
          <label className="space-y-1 text-xs text-text-secondary">Connection name<Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Connection name" /></label>
          <label className="space-y-1 text-xs text-text-secondary">Protocol<select aria-label="Source protocol" value={protocol} onChange={(event) => setProtocol(event.target.value)} className="app-select w-full">
            <option value="opcua">OPC UA</option><option value="mqtt">MQTT</option><option value="sparkplug_b">Sparkplug B over MQTT</option><option value="modbus">Modbus TCP</option><option value="modbus_rtu">Modbus RTU</option><option value="rest">REST Pull</option><option value="http_push">HTTP Push</option><option value="file">File reference</option><option value="dataset">Dataset replay reference</option><option value="mock">Mock generator reference</option>
          </select></label>
          <label className="space-y-1 text-xs text-text-secondary">Site ID<Input value={siteId} onChange={(event) => setSiteId(event.target.value)} placeholder="Site ID" /></label>
          <label className="space-y-1 text-xs text-text-secondary">Endpoint<Input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="opc.tcp://host:4840" /></label>
          <div className="flex items-end gap-2"><Button onClick={() => { if (!name || !siteId) return; setStep(2); }} disabled={!name || !siteId}><ChevronRight className="size-4" /> Configure source</Button>{editingId ? <Button variant="outline" onClick={resetForm}>Cancel</Button> : null}</div>
        </div>
        <div className={`${step === 2 ? "" : "hidden"} space-y-3`}><div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Endpoint / URL<Input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder={protocol === "http_push" ? "Generated after activation" : "opc.tcp://host:4840"} /></label><label className="space-y-1 text-xs text-text-secondary">Legacy credential reference<Input value={credentialRef} onChange={(event) => setCredentialRef(event.target.value)} placeholder="secret://plant-a/source" /></label><label className="space-y-1 text-xs text-text-secondary">Source ID<Input value={sourceId} onChange={(event) => setSourceId(event.target.value)} placeholder="Optional source identifier" /></label></div><div className="rounded-lg border border-border-subtle bg-surface-1 p-3"><div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium">Protocol settings</p><HelpTip label="Protocol settings help" content="These fields become the edge connector definition. Use env://NAME, file://path, path://path, or secret://provider references. The platform reads referenced values only inside the runtime." /></div>
          {protocol === "opcua" ? <label className="block space-y-1 text-xs text-text-secondary">OPC UA node IDs, one per line<textarea className="app-textarea min-h-20 w-full" value={nodesText} onChange={(event) => setNodesText(event.target.value)} placeholder="Discover in the next step, or enter ns=2;s=Pump-01.Temperature" /></label> : null}
          {["mqtt", "sparkplug_b"].includes(protocol) ? <div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Topic filter<Input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="factory/+/+/+" /></label><label className="space-y-1 text-xs text-text-secondary">QoS<Input type="number" min="0" max="2" value={mqttQos} onChange={(event) => setMqttQos(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Payload mode<select className="app-select w-full" value={payloadMode} onChange={(event) => setPayloadMode(event.target.value)}><option value="json">JSON</option><option value="sparkplug_b">Sparkplug B</option></select></label></div> : null}
          {protocol === "modbus" ? <div className="space-y-3"><label className="block space-y-1 text-xs text-text-secondary">Asset ID<Input value={modbusAsset} onChange={(event) => setModbusAsset(event.target.value)} placeholder="Pump-03" /></label><label className="block space-y-1 text-xs text-text-secondary">Holding registers<textarea className="app-textarea min-h-20 w-full font-mono text-xs" value={registersText} onChange={(event) => setRegistersText(event.target.value)} placeholder="address,tag,unit,scale,offset,unit_id&#10;0,Temperature,C,0.1,0,1" /></label></div> : null}
          {protocol === "modbus_rtu" ? <div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Serial port<Input value={rtuPort} onChange={(event) => setRtuPort(event.target.value)} placeholder="/dev/ttyUSB0 or COM3" /></label><label className="space-y-1 text-xs text-text-secondary">Baud rate<Input type="number" value={baudrate} onChange={(event) => setBaudrate(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Slave ID<Input type="number" value={slaveId} onChange={(event) => setSlaveId(event.target.value)} /></label></div> : null}
          {protocol === "rest" ? <div className="space-y-3"><div className="grid gap-3 md:grid-cols-4"><label className="space-y-1 text-xs text-text-secondary">Method<select className="app-select w-full" value={restMethod} onChange={(event) => setRestMethod(event.target.value)}><option>GET</option><option>POST</option></select></label><label className="space-y-1 text-xs text-text-secondary">Poll seconds<Input type="number" min="1" max="86400" value={restInterval} onChange={(event) => setRestInterval(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Timeout seconds<Input type="number" min="1" max="300" value={restTimeout} onChange={(event) => setRestTimeout(event.target.value)} /></label><label className="space-y-1 text-xs text-text-secondary">Records path<Input value={restRecordsPath} onChange={(event) => setRestRecordsPath(event.target.value)} placeholder="data.items" /></label></div><div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Auth<select className="app-select w-full" value={restAuthType} onChange={(event) => setRestAuthType(event.target.value)}><option value="none">None</option><option value="basic">Basic</option><option value="bearer">Bearer token</option><option value="api_key">API key</option><option value="oauth2_client_credentials">OAuth2 client credentials</option><option value="mtls">mTLS</option></select></label>{restAuthType === "api_key" ? <label className="space-y-1 text-xs text-text-secondary">Key name<Input value={restAuthName} onChange={(event) => setRestAuthName(event.target.value)} /></label> : null}{restAuthType === "api_key" ? <label className="space-y-1 text-xs text-text-secondary">Key location<select className="app-select w-full" value={restAuthLocation} onChange={(event) => setRestAuthLocation(event.target.value)}><option value="header">Header</option><option value="query">Query</option></select></label> : null}</div><div className="grid gap-3 md:grid-cols-4"><Input aria-label="REST source field path" value={restSourcePath} onChange={(event) => setRestSourcePath(event.target.value)} placeholder="source_id" /><Input aria-label="REST asset field path" value={restAssetPath} onChange={(event) => setRestAssetPath(event.target.value)} placeholder="asset_id" /><Input aria-label="REST tag field path" value={restTagPath} onChange={(event) => setRestTagPath(event.target.value)} placeholder="tag" /><Input aria-label="REST value field path" value={restValuePath} onChange={(event) => setRestValuePath(event.target.value)} placeholder="value" /></div><div className="grid gap-3 md:grid-cols-3"><label className="space-y-1 text-xs text-text-secondary">Pagination<select className="app-select w-full" value={restPageMode} onChange={(event) => setRestPageMode(event.target.value)}><option value="none">None</option><option value="page">Page</option><option value="offset">Offset</option><option value="cursor">Cursor</option></select></label><label className="space-y-1 text-xs text-text-secondary">Max pages<Input type="number" min="1" max="100" value={restMaxPages} onChange={(event) => setRestMaxPages(event.target.value)} /></label><p className="self-end text-xs text-text-secondary">Field paths are dotted JSON paths. Asset, tag, and value are required for activation.</p></div></div> : null}
          {["file", "dataset", "mock"].includes(protocol) ? <label className="block space-y-1 text-xs text-text-secondary">Advanced configuration JSON<textarea aria-label="Advanced protocol configuration JSON" className="app-textarea min-h-20 w-full font-mono text-xs" value={configJson} onChange={(event) => setConfigJson(event.target.value)} /></label> : null}
          <div className="mt-3 grid gap-3 md:grid-cols-2"><label className="space-y-1 text-xs text-text-secondary">Username reference<Input value={credentialRefs.username} onChange={(event) => setCredentialRefs({ ...credentialRefs, username: event.target.value })} placeholder="env://PLC_USERNAME" /></label><label className="space-y-1 text-xs text-text-secondary">Password reference<Input value={credentialRefs.password} onChange={(event) => setCredentialRefs({ ...credentialRefs, password: event.target.value })} placeholder="file://C:/secrets/plc-password" /></label><label className="space-y-1 text-xs text-text-secondary">Bearer/API key reference<Input value={restAuthType === "api_key" ? credentialRefs.api_key : credentialRefs.token} onChange={(event) => setCredentialRefs({ ...credentialRefs, token: restAuthType === "bearer" ? event.target.value : credentialRefs.token, api_key: restAuthType === "api_key" ? event.target.value : credentialRefs.api_key })} placeholder="env://API_TOKEN" /></label><label className="space-y-1 text-xs text-text-secondary">Certificate path reference<Input value={credentialRefs.certificate} onChange={(event) => setCredentialRefs({ ...credentialRefs, certificate: event.target.value })} placeholder="path://C:/secrets/client.crt" /></label><label className="space-y-1 text-xs text-text-secondary">Private key path reference<Input value={credentialRefs.private_key} onChange={(event) => setCredentialRefs({ ...credentialRefs, private_key: event.target.value })} placeholder="path://C:/secrets/client.key" /></label><div className="text-xs leading-5 text-text-secondary">References are pointers only. The deployment supplies the actual secret values.</div></div>
        </div><div className="flex justify-between gap-2"><Button variant="outline" onClick={() => setStep(1)}>Back</Button><Button onClick={() => setStep(3)}><ChevronRight className="size-4" /> Discover or sample</Button></div></div>
        {step === 3 ? <div className="rounded-lg border border-border-subtle bg-surface-1 p-4"><p className="text-sm font-medium">Discover or sample data</p><p className="mt-1 text-xs leading-5 text-text-secondary">Save the draft first, then use Preview on the source card to browse OPC UA tags or inspect the declared Modbus, MQTT, and REST shape. Discovery never enables ingestion or publishes data.</p>{previewResult ? <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-surface-2 p-3 font-mono text-xs text-text-secondary">{JSON.stringify(previewResult, null, 2)}</pre> : <p className="mt-3 text-xs text-text-muted">No preview has been run for this draft yet. Save it, then select Preview on the source card.</p>}<div className="mt-4 flex justify-between gap-2"><Button variant="outline" onClick={() => setStep(2)}>Back</Button><Button onClick={() => setStep(4)}><ChevronRight className="size-4" /> Map data</Button></div></div> : null}
        {step === 4 ? <div className="rounded-lg border border-border-subtle bg-surface-1 p-3"><div className="mb-2 flex items-center justify-between"><div><p className="text-sm font-medium">Signal mapping</p><p className="text-xs text-text-secondary">Map source fields to the platform&apos;s asset and tag identity.</p></div><Button variant="outline" size="sm" onClick={() => setMappingRows([...mappingRows, { ...emptyMapping }])}><Plus className="size-4" /> Add mapping</Button></div><div className="space-y-2">{mappingRows.map((row, index) => <div key={index} className="grid gap-2 rounded-md border border-border-subtle p-2 md:grid-cols-[1.2fr_1fr_1fr_.8fr_.6fr_.6fr_auto]"><Input placeholder="Source field" value={row.source_field} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, source_field: event.target.value } : item))} /><Input placeholder="Asset ID" value={row.asset_id} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, asset_id: event.target.value } : item))} /><Input placeholder="Tag" value={row.tag} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, tag: event.target.value } : item))} /><Input placeholder="Unit" value={row.unit} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, unit: event.target.value } : item))} /><Input placeholder="Scale" value={row.scale} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, scale: event.target.value } : item))} /><Input placeholder="Offset" value={row.offset} onChange={(event) => setMappingRows(mappingRows.map((item, i) => i === index ? { ...item, offset: event.target.value } : item))} /><Button variant="ghost" size="sm" aria-label={`Remove mapping ${index + 1}`} onClick={() => setMappingRows(mappingRows.length === 1 ? [{ ...emptyMapping }] : mappingRows.filter((_, i) => i !== index))}>Remove</Button></div>)}</div><div className="mt-4 flex justify-between gap-2"><Button variant="outline" onClick={() => setStep(3)}>Back</Button><Button onClick={() => setStep(5)}><ChevronRight className="size-4" /> Review</Button></div></div> : null}
        {step === 5 ? <div className="space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-4"><p className="text-sm font-medium">Review and save</p><p className="text-xs leading-5 text-text-secondary">Save creates or updates the draft. Validate and Test on the source card show readiness and connectivity; Enable starts supported runtime sources. REST Pull and HTTP Push use the same canonical Kafka, DLQ, lineage, and historian fan-out path.</p><pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-surface-2 p-3 font-mono text-xs text-text-secondary">{JSON.stringify({ name, protocol, siteId, endpoint: endpoint || "generated by platform", sourceId, mappings: mappingRows.filter((row) => row.source_field || row.asset_id || row.tag).length }, null, 2)}</pre><div className="flex justify-between gap-2"><Button variant="outline" onClick={() => setStep(4)}>Back</Button><Button disabled={add.isPending || update.isPending} onClick={saveConnection}><Plus className="size-4" /> {editingId ? "Update draft" : "Save draft"}</Button></div></div> : null}
        {connections.isError ? <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm">{formatErrorMessage(connections.error, "Connections could not be loaded.")}</p> : null}
        {sourceHealth.isError ? <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-text-primary">Mapping diagnostics are temporarily unavailable, so live match counts are hidden until the observability endpoint recovers.</p> : null}
        <div className="space-y-2">
          {allConnections.length > 0 ? <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle bg-surface-1 px-3 py-2"><p className="text-xs text-text-secondary">{connectionsExpanded ? `Showing ${Math.min(connectionPage, totalConnectionPages)} of ${totalConnectionPages} pages` : `Showing ${Math.min(5, allConnections.length)} of ${allConnections.length} sources`}</p><div className="flex items-center gap-2">{connectionsExpanded && totalConnectionPages > 1 ? <><Button variant="ghost" size="sm" onClick={() => setConnectionPage((page) => Math.max(1, page - 1))} disabled={connectionPage <= 1}><ChevronLeft className="size-4" /> Previous</Button><span className="min-w-16 text-center text-xs text-text-secondary">Page {Math.min(connectionPage, totalConnectionPages)} / {totalConnectionPages}</span><Button variant="ghost" size="sm" onClick={() => setConnectionPage((page) => Math.min(totalConnectionPages, page + 1))} disabled={connectionPage >= totalConnectionPages}>Next <ChevronRight className="size-4" /></Button></> : null}<Button variant="outline" size="sm" onClick={() => { setConnectionsExpanded((expanded) => !expanded); setConnectionPage(1); }}>{connectionsExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />} {connectionsExpanded ? "Show fewer" : "Show all sources"}</Button></div></div> : null}
          {visibleConnections.map((connection) => {
            const Icon = iconFor(connection.source_protocol);
            const health = sourceHealth.data?.current.find((item) => item.connection_id === connection.connection_id);
            const mappingSummary = health && typeof health.mapping_seen === "number" ? `${health.mapping_matched ?? 0}/${health.mapping_seen} matched` : "";
            const mappingWarning = health && typeof health.mapping_missed === "number" && health.mapping_missed > 0;
            const retired = connection.state === "retired";
            const runtimeSupported = connection.runtime_supported !== false && !retired;
            return <div key={connection.connection_id} className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 ${retired ? "border-border-subtle bg-surface-1 opacity-85" : "border-border-subtle bg-surface-0"}`}>
              <div className="flex min-w-0 items-center gap-3"><Icon className="size-4 shrink-0 text-accent" /><div className="min-w-0"><p className="truncate text-sm font-medium">{connection.name}</p><p className="truncate font-mono text-xs text-text-secondary">{connection.endpoint}</p></div></div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{connection.source_protocol}</Badge><Badge variant="outline">v{connection.config_version}</Badge><Badge variant={retired ? "secondary" : "outline"}>{connection.state}</Badge>{runtimeSupported ? <Badge variant="outline" className={connection.activation_ready === false ? "border-warning/30 bg-warning/10 text-warning" : "border-success/30 bg-success/10 text-success"}>{connection.activation_ready === false ? "needs setup" : "runtime-ready"}</Badge> : <Badge variant="outline" className="border-warning/30 bg-warning/10 text-warning">{retired ? "archived" : "reference-only"}</Badge>}
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
              {connection.activation_ready === false && connection.activation_errors?.length ? <p className="w-full text-xs text-warning">Activation requirements: {connection.activation_errors.join(" ")}</p> : null}
              {!runtimeSupported ? <p className="w-full text-xs text-warning">{connection.runtime_note ?? "This source is a reference and is not started by the edge runtime."}</p> : null}
            </div>;
          })}
          {!connections.isLoading && allConnections.length === 0 ? <p className="text-sm text-text-secondary">No registry connections yet. Existing environment-variable sources remain available to the edge runtime.</p> : null}
        </div>
        {previewResult ? <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium">Preview result</p><Button variant="ghost" size="sm" onClick={() => setPreviewResult(null)}>Dismiss</Button></div><pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-text-secondary">{JSON.stringify(previewResult, null, 2)}</pre></div> : null}
      </CardContent>
    </Card>
  );
}
