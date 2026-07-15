"use client";

import { useState } from "react";
import { CheckCircle2, Database, FileCheck2, ShieldAlert } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { HelpTip } from "@/components/help-tip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatErrorMessage, requestJson } from "@/lib/http";

const example = JSON.stringify({ manifest_version: 2, dataset_id: "plant-a-pump-v1", site_ids: ["plant-a"], time_range: { start: "2026-01-01T00:00:00Z", end: "2026-01-01T01:00:00Z" }, purpose: "dreamer", observation_sources: "exports/observations.jsonl", action_sources: "exports/actions.jsonl", outcome_sources: "exports/outcomes.jsonl", episode_definition: { boundary: "industrial.boundary.v1" }, alignment: { sample_interval_ms: 1000, max_skew_ms: 250 }, provenance: { source: "historian-and-operational-events" } }, null, 2);

export default function DatasetsPage() {
  const [manifest, setManifest] = useState(example);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function validate() {
    setBusy(true); setError("");
    try {
      setResult(await requestJson("/api/datasets/manifests/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: manifest }));
    } catch (err) { setError(formatErrorMessage(err, "Manifest validation failed")); }
    finally { setBusy(false); }
  }
  return <DashboardFrame>
    <header className="space-y-3"><div className="label-overline">Intelligence plane</div><h1 className="font-heading text-3xl font-semibold tracking-tight">Data readiness</h1><p className="max-w-3xl text-sm leading-6 text-text-secondary">Prepare versioned evidence bundles for downstream model training without moving model code, rewards, or plant safety decisions into the platform.</p></header>
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,.8fr)]">
      <Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><FileCheck2 className="size-4 text-accent" />Manifest validator <HelpTip label="Manifest validator help" content="Validate the dataset contract before a build. The platform checks time alignment and required evidence references; it does not infer rewards or train models." /></CardTitle><CardDescription>Paste the JSON representation of a manifest. The CLI also accepts YAML for reproducible offline builds.</CardDescription></CardHeader><CardContent className="space-y-3"><textarea value={manifest} onChange={(event) => setManifest(event.target.value)} className="min-h-[420px] w-full rounded-lg border border-border-subtle bg-surface-2 p-3 font-mono text-xs text-text-primary outline-none focus:border-accent" aria-label="Dataset manifest JSON" /><div className="flex flex-wrap gap-2"><Button onClick={validate} disabled={busy}><CheckCircle2 className="size-4" />{busy ? "Validating..." : "Validate manifest"}</Button><Button variant="outline" onClick={() => setManifest(example)}>Load example</Button></div>{error && <p className="rounded-lg border border-error/30 bg-error/10 p-3 text-sm text-error"><ShieldAlert className="mr-2 inline size-4" />{error}</p>}{result !== null && <pre className="max-h-64 overflow-auto rounded-lg border border-border-subtle bg-surface-2 p-3 text-xs text-text-secondary">{JSON.stringify(result, null, 2)}</pre>}</CardContent></Card>
      <div className="space-y-4"><Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><Database className="size-4 text-accent" />What the platform owns <HelpTip label="Platform ownership help" content="The platform owns the contract, bounded alignment, missing-value masks, lineage, and quality report. Users own source exports, episode truth, reward definitions, model code, GPUs, and storage credentials." /></CardTitle></CardHeader><CardContent><ul className="space-y-3 text-sm leading-6 text-text-secondary"><li>Fixed-grid alignment with explicit skew tolerance.</li><li>Separate steps, actions, outcomes, and artifact references.</li><li>Manifest hash, lineage, semantic context, and quality report.</li><li>No silent interpolation, reward inference, or control execution.</li></ul></CardContent></Card><Card className="app-card"><CardHeader className="app-card-header"><CardTitle>Next step</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-text-secondary">After validation, use the CLI or optional `world-model` worker to build the bundle. The worker is not required for normal telemetry and historian deployments.</p></CardContent></Card></div>
    </div>
  </DashboardFrame>;
}
