"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Save, Upload } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { HelpTip } from "@/components/help-tip";
import { getAssetTagCatalog, getThresholdPolicies, getThresholdPolicySync, saveThresholdPolicy, type AssetTagCatalogItem, type ThresholdPolicy, type ThresholdPolicySyncState } from "@/lib/api";

const emptyPolicy = (item: AssetTagCatalogItem): ThresholdPolicy => ({
  site_id: item.site_id,
  asset_id: item.asset_id,
  tag: item.tag,
  unit: item.unit,
  mode: "outside_range",
  warning_low: item.warning_low ?? null,
  warning_high: item.warning_high ?? null,
  critical_low: item.critical_low ?? null,
  critical_high: item.critical_high ?? null,
  deadband: 0,
  on_delay_seconds: 0,
  off_delay_seconds: 0,
  enabled: true,
  source: "user",
});

export function ThresholdPolicyPanel() {
  const [items, setItems] = useState<AssetTagCatalogItem[]>([]);
  const [policies, setPolicies] = useState<ThresholdPolicy[]>([]);
  const [sync, setSync] = useState<ThresholdPolicySyncState | null>(null);
  const [selected, setSelected] = useState("");
  const [policy, setPolicy] = useState<ThresholdPolicy | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([getAssetTagCatalog(), getThresholdPolicies(), getThresholdPolicySync()])
      .then(([catalog, current, syncState]) => { setItems(catalog.items); setPolicies(current.policies); setSync(syncState); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Threshold policies could not be loaded."));
  }, []);

  const selectedItem = useMemo(() => items.find((item) => `${item.site_id}::${item.asset_id}::${item.tag}` === selected), [items, selected]);

  const selectItem = (value: string) => {
    setSelected(value);
    const item = items.find((candidate) => `${candidate.site_id}::${candidate.asset_id}::${candidate.tag}` === value);
    if (!item) { setPolicy(null); return; }
    const current = policies.find((candidate) => candidate.site_id === item.site_id && candidate.asset_id === item.asset_id && candidate.tag === item.tag);
    setPolicy(current ? { ...current } : emptyPolicy(item));
    setMessage(null);
  };

  const update = (patch: Partial<ThresholdPolicy>) => setPolicy((current) => current ? { ...current, ...patch } : current);

  const save = async () => {
    if (!policy) return;
    setError(null); setMessage(null);
    try {
      const result = await saveThresholdPolicy(policy);
      setPolicies((current) => [...current.filter((item) => !(item.site_id === policy.site_id && item.asset_id === policy.asset_id && item.tag === policy.tag)), result.policy]);
      setPolicy(result.policy);
      setMessage("Policy saved. New processed events will record this policy version.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Policy could not be saved.");
    }
  };

  const importPolicies = async (file: File | undefined) => {
    if (!file) return;
    setError(null); setMessage(null);
    try {
      const parsed = JSON.parse(await file.text()) as { policies?: ThresholdPolicy[] } | ThresholdPolicy[];
      const incoming = Array.isArray(parsed) ? parsed : parsed.policies ?? [];
      if (!incoming.length) throw new Error("The policy file contains no policies.");
      for (const item of incoming) await saveThresholdPolicy({ ...item, source: "external_import" });
      const current = await getThresholdPolicies();
      setPolicies(current.policies);
      setMessage(`${incoming.length} external policies imported. They now take precedence over manifest defaults.`);
      if (selectedItem) selectItem(`${selectedItem.site_id}::${selectedItem.asset_id}::${selectedItem.tag}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The policy file could not be imported.");
    } finally {
      if (importInputRef.current) importInputRef.current.value = "";
    }
  };

  return <Card className="app-card" id="threshold-policies">
      <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-base"><AlertTriangle className="size-4 text-accent" />Alarm and threshold policies <HelpTip label="Threshold policy help" content="Choose a discovered signal, review the registry or imported limits, and save an explicit platform policy. User policies take precedence over imported and manifest defaults. Delays and deadband are stored with the policy for deterministic runtime handling." /></CardTitle>
      <CardDescription>Configure warning and critical boundaries without changing connector code. The catalog includes configured and observed signals.</CardDescription>
      {sync ? <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        <span className="rounded-full border border-border-subtle bg-surface-2 px-2 py-1">Sync {sync.status}</span>
        <span>Published {sync.published}</span>
        <span>Pending {sync.pending_outbox}</span>
        {sync.last_error ? <span className="text-error">{sync.last_error}</span> : null}
      </div> : null}
    </CardHeader>
    <CardContent className="space-y-4 p-4">
      {error ? <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm">{error}</p> : null}
      {message ? <p className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm">{message}</p> : null}
      <label className="block space-y-1 text-sm"><span className="text-text-secondary">Asset and tag</span><select value={selected} onChange={(event) => selectItem(event.target.value)} className="app-select"><option value="">Select a discovered signal</option>{items.map((item) => <option key={`${item.site_id}::${item.asset_id}::${item.tag}`} value={`${item.site_id}::${item.asset_id}::${item.tag}`}>{item.site_id} / {item.asset_name} / {item.tag} ({item.source})</option>)}</select></label>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-secondary"><span>Import limits exported by a PLC, OPC UA/DCS tool, or approved site workflow as JSON.</span><><input ref={importInputRef} type="file" accept="application/json,.json" className="hidden" onChange={(event) => importPolicies(event.target.files?.[0])} /><Button type="button" variant="outline" size="sm" onClick={() => importInputRef.current?.click()}><Upload className="mr-2 size-4" />Import JSON</Button></></div>
      {policy ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <label className="space-y-1 text-xs text-text-secondary"><span>Mode</span><select value={policy.mode} onChange={(event) => update({ mode: event.target.value as ThresholdPolicy["mode"] })} className="app-select"><option value="outside_range">Outside range</option><option value="above">Above</option><option value="below">Below</option><option value="between_range">Between range</option><option value="bad_quality">Bad quality</option></select></label>
        {(["warning_low", "warning_high", "critical_low", "critical_high"] as const).map((field) => <label key={field} className="space-y-1 text-xs text-text-secondary"><span>{field.replaceAll("_", " ")}</span><Input type="number" value={policy[field] ?? ""} onChange={(event) => update({ [field]: event.target.value === "" ? null : Number(event.target.value) })} /></label>)}
        <label className="space-y-1 text-xs text-text-secondary"><span>Deadband</span><Input type="number" min={0} value={policy.deadband} onChange={(event) => update({ deadband: Math.max(0, Number(event.target.value) || 0) })} /></label>
        <label className="space-y-1 text-xs text-text-secondary"><span>On delay seconds</span><Input type="number" min={0} value={policy.on_delay_seconds} onChange={(event) => update({ on_delay_seconds: Math.max(0, Number(event.target.value) || 0) })} /></label>
        <label className="space-y-1 text-xs text-text-secondary"><span>Off delay seconds</span><Input type="number" min={0} value={policy.off_delay_seconds} onChange={(event) => update({ off_delay_seconds: Math.max(0, Number(event.target.value) || 0) })} /></label>
        <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={policy.enabled} onChange={(event) => update({ enabled: event.target.checked })} /> Enabled</label>
        <div className="flex items-end justify-end sm:col-span-2"><Button type="button" onClick={save}><Save className="mr-2 size-4" />Save policy</Button></div>
      </div> : <p className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-4 text-sm text-text-secondary">Select a signal to review its limits. If no signal is listed, start the source/fanout path or add it to the asset registry.</p>}
      {selectedItem ? <p className="text-xs leading-5 text-text-secondary">Current source: {policy?.source ?? selectedItem.source}. Registry values are defaults; an explicit saved policy becomes authoritative for future processing.</p> : null}
    </CardContent>
  </Card>;
}
