"use client";

import { useState } from "react";
import { Cable, CircleCheck, CircleX, Plus, Radio, Router, Server, TestTube } from "lucide-react";
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
  state: string;
  config_version: number;
};

async function getConnections(): Promise<{ connections: Connection[] }> {
  return requestJson("/api/connections");
}

function iconFor(protocol: string) {
  if (protocol === "opcua") return Server;
  if (protocol === "mqtt" || protocol === "sparkplug_b") return Radio;
  if (protocol === "modbus" || protocol === "modbus_rtu") return Router;
  return Cable;
}

export function SourceConnectionPanel() {
  const [name, setName] = useState("");
  const [protocol, setProtocol] = useState("opcua");
  const [siteId, setSiteId] = useState("demo-site");
  const [endpoint, setEndpoint] = useState("");
  const [credentialRef, setCredentialRef] = useState("");
  const queryClient = useQueryClient();
  const connections = useQuery({ queryKey: ["connections"], queryFn: getConnections });
  const add = useMutation({
    mutationFn: (payload: object) => requestJson("/api/connections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      setName(""); setEndpoint(""); setCredentialRef("");
      showToast({ title: "Connection saved", description: "The source is configured but remains disabled until it is validated and enabled.", variant: "success" });
    },
    onError: (error) => showToast({ title: "Connection not saved", description: formatErrorMessage(error, "The source definition could not be saved."), variant: "error" }),
  });
  const test = useMutation({
    mutationFn: (id: string) => requestJson(`/api/connections/${encodeURIComponent(id)}/test`, { method: "POST" }),
    onSuccess: (result: any) => showToast({ title: `Connection test: ${result.network_test}`, description: result.network_error || "No data was published by the test.", variant: result.network_test === "reachable" || result.network_test === "not_required" ? "success" : "error" }),
    onError: (error) => showToast({ title: "Connection test failed", description: formatErrorMessage(error, "The connection test could not run."), variant: "error" }),
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
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Connection name" />
          <select value={protocol} onChange={(event) => setProtocol(event.target.value)} className="h-9 rounded-lg border border-border-subtle bg-surface-0 px-3 text-sm text-text-primary">
            <option value="opcua">OPC UA</option><option value="mqtt">MQTT</option><option value="modbus">Modbus TCP</option><option value="modbus_rtu">Modbus RTU</option><option value="rest">REST</option>
          </select>
          <Input value={siteId} onChange={(event) => setSiteId(event.target.value)} placeholder="Site ID" />
          <Input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="opc.tcp://host:4840" />
          <Button disabled={!name || !endpoint || add.isPending} onClick={() => add.mutate({ name, source_protocol: protocol, site_id: siteId, endpoint, credential_ref: credentialRef })}><Plus className="size-4" /> Save</Button>
        </div>
        <Input value={credentialRef} onChange={(event) => setCredentialRef(event.target.value)} placeholder="Credential reference, e.g. secret://plant-a/opcua/pump" />
        <p className="text-xs leading-5 text-text-secondary">Save creates metadata only. It does not connect, publish, or store secrets. Network testing and activation require the operator&apos;s configured API security boundary.</p>
        {connections.isError ? <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm">{formatErrorMessage(connections.error, "Connections could not be loaded.")}</p> : null}
        <div className="space-y-2">
          {(connections.data?.connections ?? []).map((connection) => {
            const Icon = iconFor(connection.source_protocol);
            return <div key={connection.connection_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-0 p-3">
              <div className="flex min-w-0 items-center gap-3"><Icon className="size-4 shrink-0 text-accent" /><div className="min-w-0"><p className="truncate text-sm font-medium">{connection.name}</p><p className="truncate font-mono text-xs text-text-secondary">{connection.endpoint}</p></div></div>
              <div className="flex items-center gap-2"><Badge variant="outline">{connection.source_protocol}</Badge><Badge variant="outline">v{connection.config_version}</Badge><Badge variant="outline">{connection.state}</Badge><Button variant="ghost" size="sm" onClick={() => test.mutate(connection.connection_id)} disabled={test.isPending}><TestTube className="size-4" /> Test</Button>{connection.state === "enabled" ? <CircleCheck className="size-4 text-success" /> : <CircleX className="size-4 text-text-muted" />}</div>
            </div>;
          })}
          {!connections.isLoading && (connections.data?.connections ?? []).length === 0 ? <p className="text-sm text-text-secondary">No registry connections yet. Existing environment-variable sources remain available to the edge runtime.</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}
