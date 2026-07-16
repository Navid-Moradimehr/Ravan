import { AlertTriangle, CheckCircle2, CircleDot, ClipboardCheck, FileWarning, RadioTower } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { HelpTip } from "@/components/help-tip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type BriefingIssue = {
  issue_id: string;
  status: "new" | "ongoing" | "worsening" | "resolved";
  severity: "normal" | "warning" | "critical" | "unknown";
  asset_id: string;
  tag: string;
  observation: string;
  evidence_event_ids: string[];
};

export type OperationalBriefing = {
  schema_version: string;
  headline: string;
  situation_status: "normal" | "attention" | "critical" | "recovering" | "unknown";
  executive_summary: string;
  key_updates: string[];
  active_issues: BriefingIssue[];
  resolved_issues: BriefingIssue[];
  affected_assets: string[];
  recommended_checks: string[];
  evidence_references: string[];
  data_gaps: string[];
  limitations: string[];
  continuity: Record<string, unknown>;
  confidence: "low" | "medium" | "high";
};

export type AIReportJob = {
  job_id: string;
  site_id: string;
  report_type: string;
  trigger_reason: string;
  window_start?: string | null;
  window_end?: string | null;
  status: string;
  attempts: number;
  last_error?: string | null;
  result?: {
    event_id?: string;
    briefing?: OperationalBriefing;
    generation?: Record<string, unknown>;
    evidence_event_ids?: string[];
  } | null;
  created_at: string;
  updated_at?: string;
  delivery?: {
    job_persisted: boolean;
    provider_response_received: boolean;
    kafka_acknowledged: boolean;
    historian_persisted: boolean;
    projection_error?: string | null;
    api_retrieved: boolean;
  };
};

function formatDate(value?: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function ReportSection({ title, items, tone = "default" }: { title: string; items: string[]; tone?: "default" | "warning" }) {
  if (!items.length) return null;
  return (
    <section className={cn("rounded-xl border p-4", tone === "warning" ? "border-warning/25 bg-warning/5" : "border-border-subtle bg-surface-2/55")}>
      <h3 className="font-heading text-sm font-semibold tracking-tight text-text-primary">{title}</h3>
      <ul className="mt-3 space-y-2 font-sans text-sm leading-6 text-text-secondary">
        {items.map((item, index) => <li key={`${title}-${index}`} className="flex gap-2"><CircleDot className="mt-2 size-2.5 shrink-0 text-accent" /><span>{item}</span></li>)}
      </ul>
    </section>
  );
}

function IssueList({ title, issues, resolved = false }: { title: string; issues: BriefingIssue[]; resolved?: boolean }) {
  if (!issues.length) return null;
  return (
    <section>
      <h3 className="font-heading text-sm font-semibold tracking-tight text-text-primary">{title}</h3>
      <div className="mt-3 grid gap-3">
        {issues.map((issue) => (
          <article key={issue.issue_id} className="rounded-xl border border-border-subtle bg-surface-2/60 p-4">
            <div className="flex flex-wrap items-center gap-2">
              {resolved ? <CheckCircle2 className="size-4 text-success" /> : <AlertTriangle className={cn("size-4", issue.severity === "critical" ? "text-error" : "text-warning")} />}
              <span className="font-heading text-sm font-semibold text-text-primary">{issue.asset_id}</span>
              <span className="font-mono text-xs text-text-muted">{issue.tag}</span>
              <Badge variant="outline" className="ml-auto capitalize">{issue.status}</Badge>
            </div>
            <p className="mt-3 font-sans text-sm leading-6 text-text-secondary">{issue.observation}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function OperationalBriefingDetail({ job }: { job: AIReportJob }) {
  const briefing = job.result?.briefing;
  if (!briefing) {
    return <div className="rounded-xl border border-dashed border-border-subtle p-8 text-center font-sans text-sm text-text-secondary">This job has no completed briefing content yet.</div>;
  }
  const generation = job.result?.generation ?? {};
  const delivery = job.delivery;
  return (
    <article className="space-y-5" aria-label={`Operational briefing: ${briefing.headline}`}>
      <header className="overflow-hidden rounded-xl border border-border bg-surface-1">
        <div className="border-b border-border-subtle bg-surface-2/65 p-5">
          <div className="flex items-start gap-2"><h2 className="text-balance font-heading text-2xl font-semibold leading-tight tracking-tight text-text-primary">{briefing.headline}</h2><HelpTip label="Briefing detail help" content="This is a validated structured report stored in the durable job record. The sections below show model output, evidence IDs, fallback state, Kafka acknowledgement, and historian persistence separately." /></div>
          <p className="mt-3 max-w-3xl font-sans text-sm leading-7 text-text-secondary">{briefing.executive_summary}</p>
        </div>
        <div className="grid gap-px bg-border-subtle sm:grid-cols-3">
          <div className="bg-surface-1 px-4 py-3"><p className="label-overline">Generated</p><p className="mt-1 font-sans text-sm text-text-primary">{formatDate(job.updated_at ?? job.created_at)}</p></div>
          <div className="bg-surface-1 px-4 py-3"><p className="label-overline">Confidence</p><p className="mt-1 font-sans text-sm capitalize text-text-primary">{briefing.confidence}</p></div>
          <div className="bg-surface-1 px-4 py-3"><p className="label-overline">Evidence</p><p className="mt-1 font-sans text-sm text-text-primary">{briefing.evidence_references.length} references</p></div>
        </div>
      </header>

      <ReportSection title="What changed" items={briefing.key_updates} />
      <IssueList title="Active issues" issues={briefing.active_issues} />
      <IssueList title="Resolved conditions" issues={briefing.resolved_issues} resolved />
      <ReportSection title="Recommended read-only checks" items={briefing.recommended_checks} />
      <ReportSection title="Data gaps" items={briefing.data_gaps} tone="warning" />
      <ReportSection title="Limitations" items={briefing.limitations} tone="warning" />

      {generation.used_fallback && generation.generation_error ? (
        <BriefingFailure message={`The configured model did not produce the displayed report. A deterministic fallback was used because: ${String(generation.generation_error)}`} />
      ) : null}

      {delivery && (!delivery.kafka_acknowledged || !delivery.historian_persisted) ? (
        <BriefingFailure message={delivery.projection_error || "The report is readable from the durable job record, but downstream Kafka or historian delivery has not been verified yet. This panel will refresh automatically."} />
      ) : null}

      <section className="rounded-xl border border-border-subtle bg-surface-2/50 p-4">
        <div className="flex items-center gap-2"><ClipboardCheck className="size-4 text-accent" /><h3 className="font-heading text-sm font-semibold text-text-primary">Evidence and generation record</h3></div>
        <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
          <div><p className="label-overline">Affected assets</p><p className="mt-1 font-sans leading-5 text-text-secondary">{briefing.affected_assets.join(", ") || "None identified"}</p></div>
          <div><p className="label-overline">Model</p><p className="mt-1 font-mono leading-5 text-text-secondary">{String(generation.model ?? "Not recorded")}</p></div>
          <div><p className="label-overline">Structured mode</p><p className="mt-1 font-mono leading-5 text-text-secondary">{String(generation.structured_mode ?? "Not recorded")}</p></div>
          <div><p className="label-overline">Prompt cache</p><p className="mt-1 font-mono leading-5 text-text-secondary">{String(generation.cache_mode ?? "Not recorded")} / {String(generation.cached_tokens ?? 0)} cached tokens</p></div>
          <div><p className="label-overline">Provider response</p><p className="mt-1 font-sans leading-5 text-text-secondary">{generation.provider_response_received ? "Received and validated" : generation.used_fallback ? "Unavailable; deterministic fallback shown" : "Not recorded"}</p></div>
          <div><p className="label-overline">Delivery</p><p className="mt-1 font-sans leading-5 text-text-secondary">{delivery ? `${delivery.kafka_acknowledged ? "Kafka acknowledged" : "Kafka pending"}; ${delivery.historian_persisted ? "historian verified" : "historian pending"}` : "Awaiting delivery verification"}</p></div>
        </div>
        <details className="mt-4 rounded-lg border border-border-subtle bg-surface-0/60 p-3">
          <summary className="cursor-pointer font-sans text-sm font-medium text-text-primary">Evidence IDs</summary>
          <p className="mt-3 break-words font-mono text-xs leading-5 text-text-muted">{briefing.evidence_references.join(" · ") || "No event IDs were available."}</p>
        </details>
      </section>
    </article>
  );
}

export function BriefingEmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-border-subtle bg-surface-2/25 p-8 text-center">
      <RadioTower className="mx-auto size-6 text-text-muted" />
      <h3 className="mt-3 font-heading text-base font-semibold text-text-primary">No operational briefings yet</h3>
      <p className="mx-auto mt-2 max-w-md font-sans text-sm leading-6 text-text-secondary">Enable a reporting policy or request a manual briefing. Completed output will appear here automatically.</p>
    </div>
  );
}

export function BriefingFailure({ message }: { message: string }) {
  return <div className="flex gap-3 rounded-xl border border-error/25 bg-error/5 p-4"><FileWarning className="size-5 shrink-0 text-error" /><p className="font-sans text-sm leading-6 text-text-secondary">{message}</p></div>;
}
