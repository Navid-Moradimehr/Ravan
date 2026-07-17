import Link from "next/link";
import { Activity, AlertTriangle, BarChart3, BookOpen, Cable, Database, FileCheck2, Gauge, GitBranch, HardDrive, Radio, ShieldCheck, Terminal, Workflow } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type GuideSectionProps = {
  id: string;
  eyebrow: string;
  title: string;
  icon: typeof Cable;
  purpose: string;
  steps: string[];
  ownership: string;
  href: string;
  action: string;
};

const sections: GuideSectionProps[] = [
  {
    id: "overview",
    eyebrow: "01 · Orientation",
    title: "Operations overview",
    icon: Activity,
    purpose: "Use the landing page as a concise control-room summary. It shows the current telemetry state, pipeline stages, health snapshot, AI briefing preview, and links to the detailed routes.",
    steps: ["Start here after deployment to see whether telemetry and observability are online.", "Treat fallback or degraded badges as a signal to open Observability, not as live plant data.", "Use the route cards to move into source setup, historian work, pipeline inspection, or data readiness."],
    ownership: "The platform owns the status aggregation. Users own the underlying infrastructure, thresholds, credentials, and interpretation of plant health.",
    href: "/",
    action: "Open operations overview",
  },
  {
    id: "sources",
    eyebrow: "02 · Ingestion",
    title: "Source connections",
    icon: Cable,
    purpose: "Register the bridge between an industrial protocol and the platform. The editor supports OPC UA, MQTT, Sparkplug B, Modbus TCP/RTU, REST Pull, HTTP Push, and reference-based sources.",
    steps: ["Open Integrations and create a source with a stable name, site ID, protocol, endpoint, and operator-managed credential references.", "Configure protocol fields, preview or discover data when supported, then map source fields to platform asset and tag identities.", "Save the draft, validate it, test connectivity, and enable it only after the result is acceptable.", "After activation, verify the source in Source connections, Kafka UI, Edge Metrics, Historian, and Observability."],
    ownership: "The platform owns the connection contract, canonical event mapping, validation, versioning, and runtime reconciliation. Users provide network reachability, PLC/API details, credentials, TLS trust, register/node selections, and site semantics.",
    href: "/integrations#source-connections",
    action: "Open source connections",
  },
  {
    id: "pipeline",
    eyebrow: "03 · Event flow",
    title: "Pipeline and processing",
    icon: GitBranch,
    purpose: "Trace how source data becomes canonical events and moves through Kafka, validation, normalization, Flink or fallback processing, DLQ handling, and downstream fan-out.",
    steps: ["Use Pipeline to understand stage boundaries and topic movement; it is a flow explanation and boundary view, not the primary source editor.", "Use Processing to inspect deterministic scoring, keyed windows, rules, and processing runtime signals.", "When an event is rejected or malformed, inspect the DLQ and error details before changing a source mapping.", "Use Kafka UI to inspect actual topic payloads and consumer lag when the UI summary is not enough."],
    ownership: "The platform owns canonical event contracts, Kafka topics, deterministic processing, replayability, and DLQ semantics. Users own business rules, plant-specific mappings, retention, partition sizing, and production capacity planning.",
    href: "/pipeline",
    action: "Open pipeline view",
  },
  {
    id: "historian",
    eyebrow: "04 · Historical memory",
    title: "Historian and operational data",
    icon: Database,
    purpose: "Use the historian for time-series trends, raw events, alarms, SQL queries, replay, backups, notifications, webhooks, and custom dashboards.",
    steps: ["Choose an asset and tag in Historical Trend to inspect a bounded time range.", "Use SQL Query for controlled analysis against the historian; include time and asset/tag filters for large datasets.", "Use Scenario & Replay to reproduce a known event sequence without reconnecting to the physical source.", "Use Custom Dashboard to save operator views locally, then configure notifications or webhooks for external delivery.", "Run backup and restore drills before relying on the historian as an operational record."],
    ownership: "The platform owns historian schemas, canonical writes, query boundaries, replay contracts, and backup workflows. Users own retention duration, backup destination, SQL access policy, alert recipients, and external system endpoints.",
    href: "/historian",
    action: "Open historian tools",
  },
  {
    id: "observability",
    eyebrow: "05 · Operations",
    title: "Observability",
    icon: Gauge,
    purpose: "Determine whether the platform is receiving, processing, storing, and exposing data correctly. This is where you investigate latency, throughput, reconnects, DLQ volume, and degraded dependencies.",
    steps: ["Check the source and service status first.", "Compare ingest throughput, processing throughput, historian writes, consumer lag, and AI latency.", "Open Prometheus for raw metrics and Grafana for dashboards when a panel needs deeper time-range analysis.", "Use source-health and mapping diagnostics to distinguish a disconnected source from a connected source with incorrect field mappings."],
    ownership: "The platform exposes metrics, health contracts, and diagnostics. Users operate Prometheus/Grafana retention, alert rules, dashboards, routing, and escalation procedures.",
    href: "/observability",
    action: "Open observability",
  },
  {
    id: "kafka",
    eyebrow: "06 · Broker operations",
    title: "Kafka UI, Grafana, and Prometheus",
    icon: BarChart3,
    purpose: "These companion tools provide deeper operations views. Kafka UI is for topics, partitions, consumer groups, offsets, and payloads; Grafana is for dashboards; Prometheus is for querying scraped metrics.",
    steps: ["Use Kafka UI to confirm producers are publishing and consumers are advancing; inspect lag before assuming the historian is slow.", "Use Grafana to compare service-level behavior over time and create organization-specific operational panels.", "Use Prometheus directly when validating a metric name, scrape target, or alert expression.", "Do not treat these tools as source configuration screens; source definitions remain owned by the platform Integrations page."],
    ownership: "The platform provides the integration points and standard metrics. Users own dashboards, alert rules, broker sizing, access control, and retention policies for these companion tools.",
    href: "http://localhost:18080",
    action: "Open Kafka UI",
  },
  {
    id: "ai",
    eyebrow: "07 · Intelligence",
    title: "Operational briefings and AI gateway",
    icon: Workflow,
    purpose: "Use AI reporting for scheduled operational summaries and anomaly briefings generated from bounded evidence. The AI gateway remains provider-neutral and supports local or user-configured model endpoints.",
    steps: ["Configure the reporting policy and scope in Operational briefings.", "Set the reporting interval and anomaly behavior conservatively for the available model capacity.", "Generate or wait for a report, then read the stored briefing, evidence record, provider status, and delivery state.", "If the gateway is degraded, inspect its health and logs before trusting a fallback response."],
    ownership: "The platform owns report contracts, evidence selection, short-memory continuity, provider-neutral gateway interfaces, and audit records. Users own model endpoints, API keys, prompts or skills, GPU capacity, approval policy, and whether AI output is used operationally.",
    href: "/ai-reporting",
    action: "Open operational briefings",
  },
  {
    id: "datasets",
    eyebrow: "08 · AI readiness",
    title: "Data readiness and datasets",
    icon: FileCheck2,
    purpose: "Prepare versioned dataset manifests for replay, benchmarking, analytics, and future world-model or predictive-maintenance workflows.",
    steps: ["Define the site, time range, observation sources, action sources, outcomes, episode boundaries, and alignment tolerance.", "Validate the manifest before building or exporting a dataset.", "Keep provenance and source configuration versions with every training or benchmark artifact.", "Use a user-owned lakehouse, S3-compatible bucket, or other storage for long-term analytical datasets when required."],
    ownership: "The platform owns manifest validation, alignment contracts, lineage fields, and quality reporting. Users own episode truth, reward definitions, labels, model code, storage credentials, and training infrastructure.",
    href: "/datasets",
    action: "Open data readiness",
  },
  {
    id: "integrations",
    eyebrow: "09 · External systems",
    title: "Webhooks, notifications, sinks, and connectors",
    icon: Radio,
    purpose: "Move selected platform outputs to external systems without coupling the core event path to a company’s MES, ERP, email, lakehouse, or notification provider.",
    steps: ["Configure the external endpoint and delivery policy in the relevant panel or deployment configuration.", "Use a test action before enabling production delivery.", "Check delivery response, retries, DLQ behavior, and idempotency when a destination is unavailable.", "For lakehouse or S3 use, configure the optional sink and user-owned bucket credentials outside the source editor."],
    ownership: "The platform owns connector contracts, canonical sink payloads, retry boundaries, and delivery diagnostics. Users own endpoint URLs, certificates, secrets, destination schemas, downstream transformations, and retention.",
    href: "/integrations",
    action: "Open integrations",
  },
  {
    id: "recovery",
    eyebrow: "10 · Reliability",
    title: "Backups, replay, and recovery",
    icon: HardDrive,
    purpose: "Protect operational history and make failures reproducible. Recovery is a deployment responsibility as much as a feature of the application.",
    steps: ["Run a backup drill against a clean restore target.", "Verify historian row identity, timestamps, event IDs, and query behavior after restore.", "Use Kafka replay or dataset replay to reproduce processing behavior after a code or configuration change.", "Document the restore owner, backup location, retention, and acceptable data-loss window for each site."],
    ownership: "The platform provides backup and replay contracts. Users own storage durability, off-site copies, encryption, restore scheduling, disaster-recovery objectives, and operator runbooks.",
    href: "/historian#backup",
    action: "Open recovery tools",
  },
  {
    id: "cli",
    eyebrow: "11 · Deployment",
    title: "CLI and deployment operations",
    icon: Terminal,
    purpose: "Use the CLI and deployment profiles for repeatable startup, diagnostics, benchmarks, release gates, site validation, and local or Kubernetes rehearsals.",
    steps: ["Run `datastreamctl doctor` before diagnosing a deployment.", "Use the site profile and project manifest to make runtime assumptions explicit.", "Use Docker Compose for a single server or edge deployment; use Kubernetes and Flink Operator workflows only when the organization owns that operational complexity.", "Keep secrets, TLS, identity, authorization, broker endpoints, storage endpoints, and retention settings in deployment-owned configuration."],
    ownership: "The platform owns CLI contracts, health checks, deployment manifests, and release gates. Users own OS services, container runtime, Kubernetes cluster, secrets, IAM, network segmentation, storage, and production change control.",
    href: "/integrations#setup-guide",
    action: "Open deployment guidance",
  },
  {
    id: "security",
    eyebrow: "12 · Governance",
    title: "Security and ownership boundaries",
    icon: ShieldCheck,
    purpose: "The open-source installation intentionally leaves authentication, authorization, network perimeter, and secret management configurable for each organization.",
    steps: ["Place the platform behind the organization’s approved network boundary and ingress policy.", "Configure authentication and authorization at the organization’s chosen API gateway or identity layer.", "Supply secrets through deployment-managed references; never paste secret values into source metadata or support reports.", "Restrict Kafka, historian, Grafana, Prometheus, and AI endpoints according to operator roles and site boundaries."],
    ownership: "The platform provides contracts, references, audit fields, and safe boundaries. Users own identity provider integration, RBAC policy, TLS certificates, firewall rules, secret rotation, vulnerability management, and compliance controls.",
    href: "/integrations#setup-guide",
    action: "Review integration setup",
  },
];

function GuideSection({ id, eyebrow, title, icon: Icon, purpose, steps, ownership, href, action }: GuideSectionProps) {
  return (
    <section id={id} className="scroll-mt-24">
      <Card className="app-card overflow-hidden">
        <CardHeader className="app-card-header border-b">
          <p className="label-overline">{eyebrow}</p>
          <CardTitle className="flex items-center gap-2 text-lg"><span className="flex size-8 items-center justify-center rounded-lg border border-accent/30 bg-accent-subtle text-accent"><Icon aria-hidden="true" className="size-4" /></span>{title}</CardTitle>
          <CardDescription className="max-w-3xl leading-6">{purpose}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 p-4 md:grid-cols-[minmax(0,1.35fr)_minmax(240px,.65fr)]">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">How to use it</h3>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-text-secondary">{steps.map((step) => <li key={step}>{step}</li>)}</ol>
          </div>
          <div className="space-y-4">
            <div className="rounded-lg border border-border-subtle bg-surface-2 p-3"><h3 className="text-sm font-semibold text-text-primary">Ownership boundary</h3><p className="mt-2 text-xs leading-5 text-text-secondary">{ownership}</p></div>
            <Link href={href} className="action-secondary inline-flex min-h-9 w-full items-center justify-center rounded-lg px-3 text-sm font-semibold transition-colors">{action}</Link>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

export default function HelpGuidancePage() {
  return <DashboardFrame>
    <div className="space-y-6">
      <header className="app-card overflow-hidden">
        <div className="border-b border-border-subtle px-6 py-6">
          <p className="label-overline">Platform handbook</p>
          <h1 className="mt-2 max-w-3xl font-heading text-3xl font-semibold tracking-tight md:text-4xl">Help & guidance</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary md:text-base">A practical guide to using the platform from first deployment through source connection, event processing, historian operations, observability, AI reporting, dataset preparation, and recovery.</p>
        </div>
        <div className="grid gap-3 bg-surface-0/40 px-6 py-4 sm:grid-cols-3">
          <div><p className="text-sm font-semibold text-text-primary">First setup</p><p className="mt-1 text-xs leading-5 text-text-secondary">Configure the deployment, then register and validate a source.</p></div>
          <div><p className="text-sm font-semibold text-text-primary">Daily operation</p><p className="mt-1 text-xs leading-5 text-text-secondary">Check source health, event flow, historian writes, and alerts.</p></div>
          <div><p className="text-sm font-semibold text-text-primary">Advanced use</p><p className="mt-1 text-xs leading-5 text-text-secondary">Prepare datasets, connect AI providers, replay events, and operate sinks.</p></div>
        </div>
      </header>

      <Card className="app-card">
        <CardHeader className="app-card-header border-b"><CardTitle className="flex items-center gap-2"><BookOpen className="size-4 text-accent" /> Guide contents</CardTitle><CardDescription>Jump to a subject, then follow its ownership boundary and operational steps.</CardDescription></CardHeader>
        <CardContent className="grid gap-x-6 gap-y-2 p-4 sm:grid-cols-2 xl:grid-cols-3">{sections.map(({ id, eyebrow, title }) => <a key={id} href={`#${id}`} className="rounded-lg border border-transparent px-3 py-2 transition-colors hover:border-accent/30 hover:bg-accent-subtle"><span className="block text-[0.68rem] font-mono uppercase tracking-[0.18em] text-accent">{eyebrow}</span><span className="text-sm font-medium text-text-primary">{title}</span></a>)}</CardContent>
      </Card>

      <div className="space-y-4">{sections.map((section) => <GuideSection key={section.id} {...section} />)}</div>

      <Card className="app-card border-warning/30 bg-warning/5"><CardContent className="flex items-start gap-3 p-4"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" /><div><p className="text-sm font-semibold text-text-primary">Production boundary</p><p className="mt-1 text-sm leading-6 text-text-secondary">This handbook describes the platform contracts and user workflow. A production installation still requires organization-owned authentication, authorization, network segmentation, TLS, secrets, retention, backup, capacity, and real-device acceptance testing.</p></div></CardContent></Card>
    </div>
  </DashboardFrame>;
}
