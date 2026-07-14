"use client";

import { useState } from "react";
import { BrainCircuit, Clock3, FileText, ShieldCheck } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { HelpTip } from "@/components/help-tip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";

type Policy = { enabled: boolean; scheduled_enabled: boolean; scheduled_interval_seconds: number; anomaly_enabled: boolean; anomaly_duration_seconds: number; anomaly_severity: string; anomaly_min_samples: number; anomaly_rearm_seconds: number; anomaly_cooldown_seconds: number; exclude_replay: boolean; max_evidence_events: number };
type Job = { job_id: string; site_id: string; report_type: string; trigger_reason: string; status: string; attempts: number; created_at: string };

const defaultPolicy: Policy = { enabled: true, scheduled_enabled: true, scheduled_interval_seconds: 3600, anomaly_enabled: false, anomaly_duration_seconds: 20, anomaly_severity: "critical", anomaly_min_samples: 3, anomaly_rearm_seconds: 60, anomaly_cooldown_seconds: 1800, exclude_replay: true, max_evidence_events: 100 };

export default function AIReportingPage() {
  const [policy, setPolicy] = useState<Policy>(defaultPolicy);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loaded, setLoaded] = useState(false);
  const update = <K extends keyof Policy>(key: K, value: Policy[K]) => setPolicy((current) => ({ ...current, [key]: value }));

  async function load() {
    try {
      const [result, recent] = await Promise.all([requestJson<{ policy: Policy }>("/api/ai/reporting-policy"), requestJson<Job[]>("/api/ai/reports?limit=20")]);
      setPolicy(result.policy); setJobs(recent); setLoaded(true);
    } catch (error) { showToast({ title: "AI reporting unavailable", description: formatErrorMessage(error), variant: "error" }); }
  }

  async function save() {
    try { await requestJson("/api/ai/reporting-policy", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(policy) }); showToast({ title: "Reporting policy saved", description: "The gateway will reload it within a few seconds.", variant: "success" }); }
    catch (error) { showToast({ title: "Policy not saved", description: formatErrorMessage(error), variant: "error" }); }
  }

  async function generate() {
    try { const job = await requestJson<Job>("/api/ai/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ report_type: "manual", trigger_reason: "operator_requested" }) }); setJobs((items) => [job, ...items]); showToast({ title: "Report job queued", description: "The request is recorded for the AI gateway.", variant: "success" }); }
    catch (error) { showToast({ title: "Report not queued", description: formatErrorMessage(error), variant: "error" }); }
  }

  return <DashboardFrame><SectionHeader eyebrow="Intelligence plane" title="AI reporting" description="Control bounded, observable summaries of processed industrial data without changing deterministic processing." actions={<Button variant="outline" onClick={load}>{loaded ? "Refresh" : "Load policy"}</Button>} />
    <div className="grid gap-4 xl:grid-cols-[1.15fr_.85fr]">
      <Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><BrainCircuit className="size-4 text-accent" /> Reporting policy <HelpTip label="AI reporting help" content="Scheduled reports use bounded historian evidence. The gateway does not send every event to a model. Anomaly reports are opt-in and require sustained severity." /></CardTitle><CardDescription>Default interval is one hour. Allowed interval: 10 minutes to one day.</CardDescription></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={policy.scheduled_enabled} onChange={(e) => update("scheduled_enabled", e.target.checked)} /> Scheduled reports</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={policy.anomaly_enabled} onChange={(e) => update("anomaly_enabled", e.target.checked)} /> Sustained anomaly reports</label>
        <label className="space-y-1 text-sm">Interval seconds<Input type="number" min={600} max={86400} value={policy.scheduled_interval_seconds} onChange={(e) => update("scheduled_interval_seconds", Number(e.target.value))} /></label>
        <label className="space-y-1 text-sm">Anomaly duration seconds<Input type="number" min={20} max={600} value={policy.anomaly_duration_seconds} onChange={(e) => update("anomaly_duration_seconds", Number(e.target.value))} /></label>
        <label className="space-y-1 text-sm">Severity<select className="app-select w-full" value={policy.anomaly_severity} onChange={(e) => update("anomaly_severity", e.target.value)}><option value="critical">Critical only</option><option value="warning">Warning and critical</option><option value="any">Any severity</option></select></label>
        <label className="space-y-1 text-sm">Evidence events<Input type="number" min={1} max={1000} value={policy.max_evidence_events} onChange={(e) => update("max_evidence_events", Number(e.target.value))} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={policy.exclude_replay} onChange={(e) => update("exclude_replay", e.target.checked)} /> Exclude replay-triggered reports</label>
        <div className="flex flex-wrap gap-2 sm:col-span-2"><Button onClick={save}>Save policy</Button><Button variant="secondary" onClick={generate}>Generate report now</Button></div>
      </CardContent></Card>
      <Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><Clock3 className="size-4 text-accent" /> Job history</CardTitle><CardDescription>Durable requests and their processing state.</CardDescription></CardHeader><CardContent className="space-y-2">{jobs.length ? jobs.map((job) => <div key={job.job_id} className="flex items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-0 p-3"><div><p className="text-sm font-medium">{job.report_type} · {job.trigger_reason}</p><p className="text-xs text-text-secondary">{job.site_id} · {new Date(job.created_at).toLocaleString()}</p></div><Badge variant={job.status === "completed" ? "default" : "outline"}>{job.status}</Badge></div>) : <div className="rounded-lg border border-dashed border-border-subtle p-5 text-sm text-text-secondary">{loaded ? "No report jobs recorded yet." : "Load the policy to inspect report history."}</div>}</CardContent></Card>
    </div>
    <Card className="app-card"><CardContent className="flex gap-3 p-4 text-sm text-text-secondary"><ShieldCheck className="size-5 shrink-0 text-success" /><p>AI reporting is advisory. It publishes versioned output events and never performs plant actions. Model endpoints, credentials, retention, and deployment authorization remain user-owned.</p><FileText className="hidden size-5 shrink-0 text-accent sm:block" /></CardContent></Card>
  </DashboardFrame>;
}
