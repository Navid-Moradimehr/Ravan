"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Clock3, FileText, ShieldCheck, Activity } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { HelpTip } from "@/components/help-tip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";
import { getAssetTagCatalog } from "@/lib/api";

type Policy = {
  enabled: boolean;
  scheduled_enabled: boolean;
  scheduled_interval_seconds: number;
  anomaly_enabled: boolean;
  anomaly_duration_seconds: number;
  anomaly_severity: string;
  anomaly_min_samples: number;
  anomaly_rearm_seconds: number;
  anomaly_cooldown_seconds: number;
  exclude_replay: boolean;
  max_evidence_events: number;
};

type Job = {
  job_id: string;
  site_id: string;
  report_type: string;
  trigger_reason: string;
  status: string;
  attempts: number;
  last_error?: string | null;
  created_at: string;
  updated_at?: string;
};

type ReportingStatus = {
  site_id: string;
  policy: Policy;
  source: string;
  min_interval_seconds: number;
  max_interval_seconds: number;
};

const defaultPolicy: Policy = {
  enabled: true,
  scheduled_enabled: true,
  scheduled_interval_seconds: 3600,
  anomaly_enabled: false,
  anomaly_duration_seconds: 20,
  anomaly_severity: "critical",
  anomaly_min_samples: 3,
  anomaly_rearm_seconds: 60,
  anomaly_cooldown_seconds: 1800,
  exclude_replay: true,
  max_evidence_events: 100,
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function statusVariant(status: string): "default" | "outline" | "destructive" {
  if (status === "completed") return "default";
  if (status === "failed") return "destructive";
  return "outline";
}

export default function AIReportingPage() {
  const [policy, setPolicy] = useState<Policy>(defaultPolicy);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState<ReportingStatus | null>(null);
  const [siteId, setSiteId] = useState("*");
  const [loaded, setLoaded] = useState(false);
  const siteCatalog = useQuery({
    queryKey: ["ai-reporting", "sites"],
    queryFn: async () => {
      const [assetTags, connections] = await Promise.all([
        getAssetTagCatalog(),
        requestJson<{ connections: Array<{ site_id: string }> }>("/api/connections"),
      ]);
      return Array.from(new Set([
        ...assetTags.items.map((item) => item.site_id),
        ...connections.connections.map((item) => item.site_id),
      ])).filter(Boolean).sort();
    },
  });
  const update = <K extends keyof Policy>(key: K, value: Policy[K]) => setPolicy((current) => ({ ...current, [key]: value }));

  async function load() {
    try {
      const query = `?site_id=${encodeURIComponent(siteId)}`;
      const [result, recent, currentStatus] = await Promise.all([
        requestJson<{ policy: Policy }>(`/api/ai/reporting-policy${query}`),
        requestJson<Job[]>(`/api/ai/reports?limit=20&site_id=${encodeURIComponent(siteId === "*" ? "" : siteId)}`),
        requestJson<ReportingStatus>(`/api/ai/reporting-status${query}`),
      ]);
      setPolicy(result.policy);
      setJobs(recent);
      setStatus(currentStatus);
      setLoaded(true);
    } catch (error) {
      showToast({ title: "AI reporting unavailable", description: formatErrorMessage(error), variant: "error" });
    }
  }

  async function save() {
    try {
      await requestJson(`/api/ai/reporting-policy?site_id=${encodeURIComponent(siteId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(policy),
      });
      showToast({ title: "Reporting policy saved", description: "The gateway will reload it within a few seconds.", variant: "success" });
      await load();
    } catch (error) {
      showToast({ title: "Policy not saved", description: formatErrorMessage(error), variant: "error" });
    }
  }

  async function generate() {
    try {
      const job = await requestJson<Job>("/api/ai/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_id: siteId, report_type: "manual", trigger_reason: "operator_requested" }),
      });
      setJobs((items) => [job, ...items]);
      showToast({ title: "Report job queued", description: "The request is recorded for the AI gateway.", variant: "success" });
    } catch (error) {
      showToast({ title: "Report not queued", description: formatErrorMessage(error), variant: "error" });
    }
  }

  return (
    <DashboardFrame>
      <SectionHeader
        eyebrow="Intelligence plane"
        title="AI reporting"
        description="Control bounded, observable summaries of processed industrial data without changing deterministic processing."
        actions={<Button variant="outline" onClick={load}>{loaded ? "Refresh status" : "Load policy"}</Button>}
      />

      <Card className="app-card">
        <CardHeader className="app-card-header">
          <CardTitle className="flex items-center gap-2"><Activity className="size-4 text-accent" /> Reporting scope <HelpTip label="Reporting scope help" content="Site ID is the deployment boundary used by events, source connections, historian data, and reporting policies. It is not an asset ID. Select a known site or use the shared * policy." /></CardTitle>
          <CardDescription>Site IDs come from the asset/tag catalog and registered source connections. Load the persisted policy before editing it.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <label className="min-w-56 space-y-1 text-sm">Site ID<select aria-label="Site ID" className="app-select w-full" value={siteId} onChange={(event) => setSiteId(event.target.value)}><option value="*">All sites (shared policy)</option>{siteCatalog.data?.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          {status ? <div className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-secondary">Source: <span className="font-medium text-text-primary">{status.source}</span><br />Allowed interval: {status.min_interval_seconds / 60} min to {status.max_interval_seconds / 3600} hr</div> : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_.85fr]">
        <Card className="app-card">
          <CardHeader className="app-card-header">
            <CardTitle className="flex items-center gap-2"><BrainCircuit className="size-4 text-accent" /> Reporting policy <HelpTip label="AI reporting help" content="Scheduled reports use bounded historian evidence. The gateway does not send every event to a model. Anomaly reports are opt-in and require sustained severity, minimum samples, and cooldown rules." /></CardTitle>
            <CardDescription>Intervals are bounded from 10 minutes to one day. All controls map directly to the persisted AIReportingPolicy contract.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 p-4 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={policy.enabled} onChange={(event) => update("enabled", event.target.checked)} /> AI reporting enabled</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={policy.scheduled_enabled} onChange={(event) => update("scheduled_enabled", event.target.checked)} /> Scheduled reports</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={policy.anomaly_enabled} onChange={(event) => update("anomaly_enabled", event.target.checked)} /> Sustained anomaly reports</label>
            <label className="space-y-1 text-sm">Interval seconds<Input type="number" min={600} max={86400} value={policy.scheduled_interval_seconds} onChange={(event) => update("scheduled_interval_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 text-sm">Anomaly duration seconds<Input type="number" min={20} max={600} value={policy.anomaly_duration_seconds} onChange={(event) => update("anomaly_duration_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 text-sm">Severity<select className="app-select w-full" value={policy.anomaly_severity} onChange={(event) => update("anomaly_severity", event.target.value)}><option value="critical">Critical only</option><option value="warning">Warning and critical</option><option value="any">Any severity</option></select></label>
            <label className="space-y-1 text-sm">Minimum samples<Input type="number" min={3} max={1000} value={policy.anomaly_min_samples} onChange={(event) => update("anomaly_min_samples", Number(event.target.value))} /></label>
            <label className="space-y-1 text-sm">Rearm seconds<Input type="number" min={0} max={86400} value={policy.anomaly_rearm_seconds} onChange={(event) => update("anomaly_rearm_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 text-sm">Cooldown seconds<Input type="number" min={0} max={86400} value={policy.anomaly_cooldown_seconds} onChange={(event) => update("anomaly_cooldown_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 text-sm">Evidence events<Input type="number" min={1} max={1000} value={policy.max_evidence_events} onChange={(event) => update("max_evidence_events", Number(event.target.value))} /></label>
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={policy.exclude_replay} onChange={(event) => update("exclude_replay", event.target.checked)} /> Exclude replay-triggered reports</label>
            <div className="flex flex-wrap gap-2 sm:col-span-2"><Button onClick={save}>Save policy</Button><Button variant="secondary" onClick={generate}>Generate report now</Button></div>
          </CardContent>
        </Card>

        <Card className="app-card">
          <CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><Clock3 className="size-4 text-accent" /> Job history <HelpTip label="Job history help" content="Jobs are durable requests. Pending means queued, completed means the gateway produced a report, and failed means the latest attempt needs operator attention. Attempts and the last error are shown when available." /></CardTitle><CardDescription>Durable requests and their processing state for the selected site scope.</CardDescription></CardHeader>
          <CardContent className="space-y-2 p-4">{jobs.length ? jobs.map((job) => <div key={job.job_id} className="rounded-lg border border-border-subtle bg-surface-0 p-3"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-medium">{job.report_type} - {job.trigger_reason}</p><p className="text-xs text-text-secondary">{job.site_id} - {formatDate(job.created_at)}</p></div><Badge variant={statusVariant(job.status)}>{job.status}</Badge></div><p className="mt-2 text-xs text-text-secondary">Attempts: {job.attempts}</p>{job.last_error ? <p className="mt-2 break-words text-xs text-error">{job.last_error}</p> : null}</div>) : <div className="rounded-lg border border-dashed border-border-subtle p-5 text-sm text-text-secondary">{loaded ? "No report jobs recorded yet." : "Load the policy to inspect report history."}</div>}</CardContent>
        </Card>
      </div>

      <Card className="app-card"><CardContent className="flex gap-3 p-4 text-sm text-text-secondary"><ShieldCheck className="size-5 shrink-0 text-success" /><p>AI reporting is advisory. It publishes versioned output events and never performs plant actions. Model endpoints, credentials, retention, and deployment authorization remain user-owned.</p><FileText className="hidden size-5 shrink-0 text-accent sm:block" /></CardContent></Card>
    </DashboardFrame>
  );
}
