"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Activity, BrainCircuit, Clock3, FileText, Filter, ShieldCheck } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { HelpTip } from "@/components/help-tip";
import { AIReportJob, BriefingEmptyState, BriefingFailure, OperationalBriefingDetail } from "@/components/operational-briefing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";
import { getAssetTagCatalog } from "@/lib/api";

type Policy = {
  enabled: boolean;
  scheduled_enabled: boolean;
  scheduled_interval_seconds: number;
  anomaly_enabled: boolean;
  recovery_enabled: boolean;
  anomaly_duration_seconds: number;
  anomaly_severity: string;
  anomaly_min_samples: number;
  anomaly_rearm_seconds: number;
  anomaly_cooldown_seconds: number;
  exclude_replay: boolean;
  max_evidence_events: number;
};

type ReportingStatus = { site_id: string; policy: Policy; source: string; min_interval_seconds: number; max_interval_seconds: number };
type ProviderStatus = { reachable: boolean; status: string; provider?: string | null; model?: string | null; credential_configured: boolean; last_error?: string | null; degraded_reason?: string | null };

const defaultPolicy: Policy = {
  enabled: true,
  scheduled_enabled: true,
  scheduled_interval_seconds: 3600,
  anomaly_enabled: false,
  recovery_enabled: true,
  anomaly_duration_seconds: 20,
  anomaly_severity: "critical",
  anomaly_min_samples: 3,
  anomaly_rearm_seconds: 60,
  anomaly_cooldown_seconds: 1800,
  exclude_replay: true,
  max_evidence_events: 100,
};

function formatDate(value?: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function statusVariant(status: string): "default" | "outline" | "destructive" {
  if (status === "completed") return "default";
  if (status === "failed") return "destructive";
  return "outline";
}

function AIReportingWorkspace() {
  const searchParams = useSearchParams();
  const linkedReport = searchParams.get("report");
  const [policy, setPolicy] = useState<Policy>(defaultPolicy);
  const [siteId, setSiteId] = useState("*");
  const [selectedId, setSelectedId] = useState<string | null>(linkedReport);
  const [reportType, setReportType] = useState("all");
  const [search, setSearch] = useState("");
  const [loaded, setLoaded] = useState(false);

  const siteCatalog = useQuery({
    queryKey: ["ai-reporting", "sites"],
    queryFn: async () => {
      const [assetTags, connections] = await Promise.all([getAssetTagCatalog(), requestJson<{ connections: Array<{ site_id: string }> }>("/api/connections")]);
      return Array.from(new Set([...assetTags.items.map((item) => item.site_id), ...connections.connections.map((item) => item.site_id)])).filter(Boolean).sort();
    },
  });
  const providerStatus = useQuery({
    queryKey: ["ai-reporting", "provider-status"],
    queryFn: () => requestJson<ProviderStatus>("/api/ai/provider-status"),
    refetchInterval: 15000,
  });

  const reports = useQuery({
    queryKey: ["ai-reporting", "reports", siteId, reportType],
    queryFn: () => requestJson<AIReportJob[]>(`/api/ai/reports?limit=100${siteId === "*" ? "" : `&site_id=${encodeURIComponent(siteId)}`}${reportType === "all" ? "" : `&report_type=${encodeURIComponent(reportType)}`}`),
    refetchInterval: 10000,
  });
  const reportDetail = useQuery({
    queryKey: ["ai-reporting", "detail", selectedId],
    queryFn: () => requestJson<AIReportJob>(`/api/ai/reports/${encodeURIComponent(selectedId ?? "")}`),
    enabled: Boolean(selectedId),
    refetchInterval: (query) => query.state.data?.delivery?.historian_persisted ? false : 5000,
  });

  const filteredReports = (reports.data ?? []).filter((job) => {
    const briefing = job.result?.briefing;
    const haystack = `${job.site_id} ${job.report_type} ${job.trigger_reason} ${briefing?.headline ?? ""} ${briefing?.executive_summary ?? ""}`.toLowerCase();
    return haystack.includes(search.trim().toLowerCase());
  });
  const completed = filteredReports.filter((job) => job.status === "completed" && job.result?.briefing);
  const activity = filteredReports.filter((job) => job.status !== "completed");
  const selected = reportDetail.data ?? filteredReports.find((job) => job.job_id === selectedId) ?? completed[0];

  useEffect(() => {
    if (!selectedId && completed[0]) setSelectedId(completed[0].job_id);
  }, [completed, selectedId]);

  const update = <K extends keyof Policy>(key: K, value: Policy[K]) => setPolicy((current) => ({ ...current, [key]: value }));

  async function loadPolicy() {
    try {
      const query = `?site_id=${encodeURIComponent(siteId)}`;
      const [result, currentStatus] = await Promise.all([
        requestJson<{ policy: Policy }>(`/api/ai/reporting-policy${query}`),
        requestJson<ReportingStatus>(`/api/ai/reporting-status${query}`),
      ]);
      setPolicy(result.policy);
      setLoaded(true);
      return currentStatus;
    } catch (error) {
      showToast({ title: "AI reporting unavailable", description: formatErrorMessage(error), variant: "error" });
      return null;
    }
  }

  async function save() {
    try {
      await requestJson(`/api/ai/reporting-policy?site_id=${encodeURIComponent(siteId)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(policy) });
      showToast({ title: "Reporting policy saved", description: "The gateway will reload it within a few seconds.", variant: "success" });
      await loadPolicy();
    } catch (error) {
      showToast({ title: "Policy not saved", description: formatErrorMessage(error), variant: "error" });
    }
  }

  async function generate() {
    try {
      const job = await requestJson<AIReportJob>("/api/ai/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ site_id: siteId, report_type: "manual", trigger_reason: "operator_requested" }) });
      setSelectedId(job.job_id);
      await reports.refetch();
      showToast({ title: "Briefing queued", description: "Its live state is visible in Activity.", variant: "success" });
    } catch (error) {
      showToast({ title: "Briefing not queued", description: formatErrorMessage(error), variant: "error" });
    }
  }

  return (
    <DashboardFrame>
      <SectionHeader
        eyebrow="Intelligence plane"
        title="Operational briefings"
        description="Readable, evidence-linked AI broadcasts for scheduled operations, sustained anomalies, recoveries, and operator requests."
        actions={<Button variant="outline" onClick={() => reports.refetch()}>Refresh briefings</Button>}
      >
        <span className="relative -top-1 font-mono text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-accent">
          beta
        </span>
      </SectionHeader>

      <Tabs defaultValue="reports" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="reports"><FileText className="mr-1 size-4" />Reports</TabsTrigger>
          <TabsTrigger value="activity"><Clock3 className="mr-1 size-4" />Activity {activity.length ? <span className="ml-1 rounded-full bg-accent-subtle px-1.5 text-xs text-accent">{activity.length}</span> : null}</TabsTrigger>
          <TabsTrigger value="policy"><BrainCircuit className="mr-1 size-4" />Policy</TabsTrigger>
        </TabsList>

        <TabsContent value="reports" className="space-y-4">
          <Card className="app-card">
            <CardContent className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_12rem_12rem]">
              <label className="space-y-1 font-sans text-sm"><span className="flex items-center gap-2"><Filter className="size-4 text-accent" />Search reports <HelpTip label="Report filters help" content="Filters apply to the durable report inbox already returned by the API. Search matches site, report type, trigger, headline, and summary; it does not send a new query to the model." /></span><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Headline, site, asset, or trigger" /></label>
              <label className="space-y-1 font-sans text-sm">Site<select className="app-select" value={siteId} onChange={(event) => setSiteId(event.target.value)}><option value="*">All sites</option>{siteCatalog.data?.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
              <label className="space-y-1 font-sans text-sm">Type<select className="app-select" value={reportType} onChange={(event) => setReportType(event.target.value)}><option value="all">All briefings</option><option value="scheduled">Scheduled</option><option value="anomaly">Anomaly</option><option value="recovery">Recovery</option><option value="manual">Manual</option></select></label>
            </CardContent>
          </Card>

          {reports.isError ? <BriefingFailure message={formatErrorMessage(reports.error)} /> : reports.isLoading ? <div className="grid gap-4 2xl:grid-cols-[21rem_minmax(0,1fr)]"><Skeleton className="h-96 bg-surface-2" /><Skeleton className="h-96 bg-surface-2" /></div> : completed.length ? (
            <div className="grid items-start gap-4 2xl:grid-cols-[21rem_minmax(0,1fr)]">
              <Card className="app-card overflow-hidden 2xl:sticky 2xl:top-[4.5rem]">
                <CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2 text-base">Report inbox <HelpTip label="Report inbox help" content="Completed scheduled, anomaly, recovery, and operator-requested jobs appear here after their structured output is persisted. Selecting one loads its durable detail and verifies downstream historian projection." /></CardTitle><CardDescription>{completed.length} completed briefing{completed.length === 1 ? "" : "s"}</CardDescription></CardHeader>
                <CardContent className="max-h-[70dvh] space-y-2 overflow-y-auto p-3">
                  {completed.map((job) => <button key={job.job_id} type="button" onClick={() => setSelectedId(job.job_id)} className={`w-full rounded-xl border p-3 text-left transition-colors ${selected?.job_id === job.job_id ? "border-accent/40 bg-accent-subtle" : "border-border-subtle bg-surface-2 hover:border-border-strong"}`}><p className="line-clamp-2 font-heading text-sm font-semibold leading-5 text-text-primary">{job.result?.briefing?.headline}</p><p className="mt-2 font-sans text-xs text-text-muted">{formatDate(job.updated_at ?? job.created_at)}</p></button>)}
                </CardContent>
              </Card>
              <Card className="app-card"><CardContent className="p-4 md:p-5">{reportDetail.isError ? <BriefingFailure message={`The report exists but its detail could not be retrieved: ${formatErrorMessage(reportDetail.error)}`} /> : selected ? <OperationalBriefingDetail job={selected} /> : <BriefingEmptyState />}</CardContent></Card>
            </div>
          ) : <BriefingEmptyState />}
        </TabsContent>

        <TabsContent value="activity">
          <Card className="app-card">
            <CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><Activity className="size-4 text-accent" />Generation activity <HelpTip label="Generation activity help" content="Pending reports are waiting for a durable worker. Processing reports have an active lease. Failed reports reached the retry limit; their last error remains visible for operators." /></CardTitle><CardDescription>Queue, retries, and failures for the selected site and report type.</CardDescription></CardHeader>
            <CardContent className="space-y-2 p-4">{activity.length ? activity.map((job) => <div key={job.job_id} className="rounded-xl border border-border-subtle bg-surface-2 p-4"><div className="flex flex-wrap items-start gap-2"><div className="min-w-0"><p className="font-heading text-sm font-semibold capitalize text-text-primary">{job.report_type} · {job.trigger_reason}</p><p className="mt-1 font-sans text-xs text-text-secondary">{job.site_id} · {formatDate(job.created_at)}</p></div><Badge variant={statusVariant(job.status)} className="ml-auto capitalize">{job.status}</Badge></div><p className="mt-3 font-sans text-xs text-text-secondary">Attempts: {job.attempts}</p>{job.last_error ? <p className="mt-2 break-words font-sans text-xs leading-5 text-error">{job.last_error}</p> : null}</div>) : <div className="rounded-xl border border-dashed border-border-subtle p-6 text-center font-sans text-sm text-text-secondary">No pending or failed report jobs.</div>}</CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="policy" className="space-y-4">
          {providerStatus.isError ? <BriefingFailure message={`Provider status could not be loaded: ${formatErrorMessage(providerStatus.error)}`} /> : (
            <Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2">Provider readiness <HelpTip label="Provider readiness help" content="The API probes the configured AI gateway health endpoint with a short timeout. It reports reachability, provider, model, and degraded state without returning API keys or other secrets." /></CardTitle><CardDescription>The gateway connection is checked without exposing credentials.</CardDescription></CardHeader><CardContent className="grid gap-3 p-4 sm:grid-cols-3"><div><p className="label-overline">Gateway</p><p className="mt-1 font-sans text-sm text-text-primary">{providerStatus.data?.reachable ? providerStatus.data.status : "Unavailable"}</p></div><div><p className="label-overline">Provider</p><p className="mt-1 font-mono text-sm text-text-primary">{providerStatus.data?.provider ?? "Not reported"} / {providerStatus.data?.model ?? "No model"}</p></div><div><p className="label-overline">Credential</p><p className="mt-1 font-sans text-sm text-text-primary">{providerStatus.data?.credential_configured ? "Configured" : "Not configured or not required locally"}</p></div>{providerStatus.data?.last_error ? <div className="sm:col-span-3"><BriefingFailure message={providerStatus.data.last_error} /></div> : null}</CardContent></Card>
          )}
          <Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2">Reporting scope <HelpTip label="Reporting scope help" content="A site-specific policy overrides the shared policy only for that site. Site IDs come from registered source connections and observed asset/tag metadata; this selector does not create a site." /></CardTitle><CardDescription>Policies are site-scoped and inherit from the shared policy when no site override exists.</CardDescription></CardHeader><CardContent className="flex flex-wrap items-end gap-3 p-4"><label className="min-w-56 space-y-1 font-sans text-sm">Site ID<select className="app-select" value={siteId} onChange={(event) => { setSiteId(event.target.value); setLoaded(false); }}><option value="*">All sites (shared policy)</option>{siteCatalog.data?.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><Button variant="outline" onClick={loadPolicy}>{loaded ? "Reload policy" : "Load policy"}</Button></CardContent></Card>
          <Card className="app-card"><CardHeader className="app-card-header"><CardTitle className="flex items-center gap-2"><BrainCircuit className="size-4 text-accent" />Reporting policy <HelpTip label="AI reporting help" content="Scheduled reports broadcast the bounded current situation. Anomaly reports require sustained severity and minimum samples. Recovery reports close a previously reported incident after the rearm period." /></CardTitle><CardDescription>Load the site policy before editing. Intervals remain bounded from 10 minutes to one day.</CardDescription></CardHeader><CardContent className="grid gap-4 p-4 sm:grid-cols-2">
            <label className="flex items-center gap-2 font-sans text-sm sm:col-span-2"><input type="checkbox" checked={policy.enabled} onChange={(event) => update("enabled", event.target.checked)} /> AI briefings enabled</label>
            <label className="flex items-center gap-2 font-sans text-sm"><input type="checkbox" checked={policy.scheduled_enabled} onChange={(event) => update("scheduled_enabled", event.target.checked)} /> Scheduled briefings</label>
            <label className="flex items-center gap-2 font-sans text-sm"><input type="checkbox" checked={policy.anomaly_enabled} onChange={(event) => update("anomaly_enabled", event.target.checked)} /> Sustained anomaly briefings</label>
            <label className="flex items-center gap-2 font-sans text-sm sm:col-span-2"><input type="checkbox" checked={policy.recovery_enabled} onChange={(event) => update("recovery_enabled", event.target.checked)} /> Create a closing briefing when a reported anomaly recovers</label>
            <label className="space-y-1 font-sans text-sm">Interval seconds<Input type="number" min={600} max={86400} value={policy.scheduled_interval_seconds} onChange={(event) => update("scheduled_interval_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 font-sans text-sm">Anomaly duration seconds<Input type="number" min={20} max={600} value={policy.anomaly_duration_seconds} onChange={(event) => update("anomaly_duration_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 font-sans text-sm">Severity<select className="app-select" value={policy.anomaly_severity} onChange={(event) => update("anomaly_severity", event.target.value)}><option value="critical">Critical only</option><option value="warning">Warning and critical</option><option value="any">Any severity</option></select></label>
            <label className="space-y-1 font-sans text-sm">Minimum samples<Input type="number" min={3} max={1000} value={policy.anomaly_min_samples} onChange={(event) => update("anomaly_min_samples", Number(event.target.value))} /></label>
            <label className="space-y-1 font-sans text-sm">Rearm seconds<Input type="number" min={0} max={86400} value={policy.anomaly_rearm_seconds} onChange={(event) => update("anomaly_rearm_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 font-sans text-sm">Cooldown seconds<Input type="number" min={0} max={86400} value={policy.anomaly_cooldown_seconds} onChange={(event) => update("anomaly_cooldown_seconds", Number(event.target.value))} /></label>
            <label className="space-y-1 font-sans text-sm">Evidence events<Input type="number" min={1} max={1000} value={policy.max_evidence_events} onChange={(event) => update("max_evidence_events", Number(event.target.value))} /></label>
            <label className="flex items-center gap-2 font-sans text-sm sm:col-span-2"><input type="checkbox" checked={policy.exclude_replay} onChange={(event) => update("exclude_replay", event.target.checked)} /> Exclude replay-triggered briefings</label>
            <div className="flex flex-wrap gap-2 sm:col-span-2"><Button onClick={save} disabled={!loaded}>Save policy</Button><Button variant="secondary" onClick={generate}>Generate briefing now</Button></div>
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      <Card className="app-card"><CardContent className="flex gap-3 p-4"><ShieldCheck className="size-5 shrink-0 text-success" /><div><div className="flex items-center gap-2"><p className="font-heading text-sm font-semibold text-text-primary">Governance boundary</p><HelpTip label="Governance boundary help" content="Briefings can read bounded evidence and publish advisory output. They cannot write PLC values, acknowledge alarms, or execute actions. Deployment owners remain responsible for credentials, retention, network policy, and authorization." /></div><p className="mt-1 font-sans text-sm leading-6 text-text-secondary">Operational briefings are advisory and read-only. They publish versioned output events and never perform plant actions. Provider credentials, retention, and deployment authorization remain operator-owned.</p></div></CardContent></Card>
    </DashboardFrame>
  );
}

export default function AIReportingPage() {
  return (
    <Suspense fallback={<DashboardFrame><Skeleton className="h-[38rem] w-full bg-surface-2" /></DashboardFrame>}>
      <AIReportingWorkspace />
    </Suspense>
  );
}
