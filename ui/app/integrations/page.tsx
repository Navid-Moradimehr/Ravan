import Link from "next/link";
import { ArrowRight, BarChart3, Cable, DatabaseZap, Webhook } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HelpTip } from "@/components/help-tip";
import { SourceConnectionPanel } from "@/components/source-connection-panel";
import { ThresholdPolicyPanel } from "@/components/threshold-policy-panel";

type SurfaceAction = {
  label: string;
  href: string;
  tone: "primary" | "secondary";
};

type SurfaceCard = {
  title: string;
  description: string;
  note: string;
  icon: typeof Cable;
  action: SurfaceAction;
  guide?: {
    heading: string;
    steps: string[];
    location: string[];
  };
};

const editableSurfaces: SurfaceCard[] = [
  {
    title: "Source connections",
    description: "Register OPC UA, MQTT, Modbus, Sparkplug B, REST Pull, HTTP Push, and reference sources.",
    note: "Use the guided editor to save drafts, test readiness, preview supported sources, and activate runtime connections without backend code changes.",
    icon: Cable,
    action: { label: "Open editor", href: "#source-connections", tone: "primary" },
  },
  {
    title: "Webhooks",
    description: "Outbound HTTP notifications for alarms and anomaly events.",
    note: "Managed from the historian workspace.",
    icon: Webhook,
    action: { label: "Open editor", href: "/historian#webhooks", tone: "primary" },
  },
  {
    title: "Notifications",
    description: "Email, Slack, and webhook destinations for alert delivery.",
    note: "Managed from the historian workspace.",
    icon: BarChart3,
    action: { label: "Open editor", href: "/historian#notifications", tone: "primary" },
  },
  {
    title: "SQL Query",
    description: "Ad-hoc historian SQL for ops, audit, and validation work.",
    note: "Managed from the historian workspace.",
    icon: DatabaseZap,
    action: { label: "Open editor", href: "/historian#sql-query", tone: "primary" },
  },
  {
    title: "Dashboard builder",
    description: "Saved local dashboard layouts for monitoring and troubleshooting.",
    note: "Managed from the historian workspace.",
    icon: BarChart3,
    action: { label: "Open builder", href: "/historian#dashboard-builder", tone: "primary" },
  },
];

const catalogSurfaces: SurfaceCard[] = [
  {
    title: "Kafka federation",
    description: "Optional site-to-central replication for approved normalized and operational topics.",
    note: "Configured with the federation Compose profile and operator-owned central broker settings.",
    icon: Cable,
    action: { label: "Setup guide", href: "#kafka-federation", tone: "secondary" },
    guide: {
      heading: "How to configure Kafka federation",
      location: [
        "config/federation/mirrormaker2.properties",
        "docker/docker-compose.yml: federation profile",
        "GET /api/v1/metadata/federation: non-secret contract view",
      ],
      steps: [
        "Provision or select the central Kafka cluster and configure its network and TLS/SASL policy.",
        "Set CENTRAL_KAFKA_BROKERS and review FEDERATION_TOPICS before enabling the profile.",
        "Keep raw replication disabled unless retention and data-sharing approval are documented.",
      ],
    },
  },
  {
    title: "Iceberg dataset reads",
    description: "Compile selected MinIO/S3 Iceberg tables into portable training or replay bundles.",
    note: "Configured through an explicit CLI source file; credentials remain deployment-owned.",
    icon: DatabaseZap,
    action: { label: "Setup guide", href: "#iceberg-dataset-reads", tone: "secondary" },
    guide: {
      heading: "How to compile from Iceberg",
      location: [
        "services/common/training_dataset.py",
        "datastreamctl training-dataset compile",
        "docs/training-dataset-guide.md",
      ],
      steps: [
        "Create a dataset manifest with the sites, time range, purpose, and quality requirements.",
        "Create a JSON source file selecting only the approved Iceberg catalog tables.",
        "Run the compiler to produce Parquet, lineage, semantic context, and quality artifacts.",
      ],
    },
  },
  {
    title: "Debezium CDC",
    description: "PostgreSQL change capture into Kafka topics.",
    note: "Configured in the deployment stack, not in the UI.",
    icon: Cable,
    action: { label: "Setup guide", href: "#debezium-cdc", tone: "secondary" },
    guide: {
      heading: "How to configure Debezium CDC",
      location: [
        "docker/docker-compose.yml: connect service",
        "docker/postgres/init.sql: bootstrap database state",
      ],
      steps: [
        "Define the PostgreSQL connector in the Connect service or external Connect cluster.",
        "Point it at the source database and the Kafka broker in your deployment.",
        "Keep source credentials and network policy on the operator side.",
      ],
    },
  },
  {
    title: "Kafka sinks",
    description: "Fan normalized events to historian, downstream Kafka, or an optional Iceberg lakehouse.",
    note: "Configured from runtime and fan-out settings.",
    icon: Cable,
    action: { label: "Setup guide", href: "#kafka-sinks", tone: "secondary" },
    guide: {
      heading: "How to configure Kafka sinks",
      location: [
        "docker/docker-compose.yml: fanout and ai-fanout services",
        "services/processor/normalized_fanout.py",
        "services/sinks/kafka_sink.py",
      ],
      steps: [
        "Choose one or more sink names: `historian`, `kafka`, or `lakehouse`.",
        "Set `FANOUT_SINKS` (or `SINKS`) and the corresponding broker/catalog variables in the deployment environment.",
        "Keep external Kafka, object-store, and catalog credentials outside the platform core.",
      ],
    },
  },
  {
    title: "AI providers",
    description: "OpenAI-compatible, LM Studio, vLLM, Ollama, and local models.",
    note: "Configured through environment variables and provider routing.",
    icon: DatabaseZap,
    action: { label: "Setup guide", href: "#ai-providers", tone: "secondary" },
    guide: {
      heading: "How to configure AI providers",
      location: [
        "docker/docker-compose.yml: ai-gateway service",
        "services/ai_gateway/providers.py",
      ],
      steps: [
        "Set `LLM_PROVIDER`, `LLM_ENDPOINT_URL`, `LLM_MODEL_ID`, and the provider credential in the deployment environment.",
        "Choose the local or remote provider endpoint per deployment.",
        "Leave provider credentials and GPU sizing to the operator.",
      ],
    },
  },
  {
    title: "Reports",
    description: "Operational and compliance reporting after storage.",
    note: "Configured through the reports API rather than a dedicated UI today.",
    icon: BarChart3,
    action: { label: "Setup guide", href: "#reports", tone: "secondary" },
    guide: {
      heading: "How to configure reports",
      location: [
        "services/api_service/routers/reports.py",
        "UI historian workspace for query validation",
      ],
      steps: [
        "Create report templates through the reports API.",
        "Tie the template query to the historian data you want to export.",
        "Schedule generation from the API or your deployment automation until a dedicated report UI exists.",
      ],
    },
  },
];

function SurfaceCardView({ item }: { item: SurfaceCard }) {
  const Icon = item.icon;
  const ActionIcon = ArrowRight;

  return (
    <Card className="flex h-full flex-col border-border bg-surface-2">
      <CardHeader className="space-y-3">
        <div className="space-y-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="flex size-8 items-center justify-center rounded-lg border border-border-subtle bg-surface-0 text-accent">
              <Icon aria-hidden="true" className="size-4" />
            </span>
            <span className="min-w-0 break-words">{item.title}</span>
          </CardTitle>
          <CardDescription className="max-w-none break-words text-sm leading-6 text-text-secondary">{item.description}</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <p className="text-sm leading-6 text-text-secondary">{item.note}</p>
        <div className="mt-auto flex items-end justify-end">
          <Link
            href={item.action.href}
            className={item.action.tone === "primary"
              ? "action-primary inline-flex h-9 items-center gap-2 rounded-lg px-4 text-sm font-medium"
              : "action-secondary inline-flex h-9 items-center gap-2 rounded-lg px-4 text-sm font-medium"}
          >
            {item.action.label}
            <ActionIcon className="size-4" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

export default function IntegrationsPage() {
  return (
    <DashboardFrame
      rightRail={
        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <Webhook aria-hidden="true" className="size-4 text-accent" />
              Integration boundary
              <HelpTip
                label="Integration boundary help"
                content="This page is a catalog of integration surfaces. If a control is editable in the app, the button takes you to the owner screen. If not, the card explains the deployment-side location."
              />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
            <p>Editable controls live on their owner screens.</p>
            <p>Deployment-configured surfaces keep plant credentials and cloud endpoints on the operator side.</p>
          </CardContent>
        </Card>
      }
    >
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <p className="label-overline">Integrations</p>
            <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">CDC, webhooks, sinks, and model providers</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This route separates the post-storage and external-system surfaces from the core pipeline so operators can see what
              is editable inside the app and what must be configured in the deployment.
            </p>
          </div>
        </header>

        <div id="source-connections" className="scroll-mt-24">
          <SourceConnectionPanel />
        </div>
        <ThresholdPolicyPanel />

        <SectionHeader
          title="Editable surfaces"
          eyebrow="In app"
          description="These integrations have direct edit screens inside the platform."
          icon={BarChart3}
          actions={<HelpTip label="Editable surfaces help" content="Open the owner screen from each card. These surfaces are editable inside the platform UI." />}
        />
        <div className="grid gap-4 xl:grid-cols-2">
          {editableSurfaces.map((item) => (
            <SurfaceCardView key={item.title} item={item} />
          ))}
        </div>

        <SectionHeader
          title="Deployment-configured surfaces"
          eyebrow="Operator setup"
          description="These surfaces are cataloged here, but the actual configuration lives in deployment files or APIs."
          icon={Cable}
          actions={<HelpTip label="Deployment-configured surfaces help" content="These integrations are managed through compose files, environment variables, manifests, or APIs rather than an in-app editor." />}
        />
        <div className="grid gap-4 xl:grid-cols-2">
          {catalogSurfaces.map((item) => (
            <SurfaceCardView key={item.title} item={item} />
          ))}
        </div>

        <SectionHeader
          title="Setup guide"
          eyebrow="Where to configure"
          description="Use these pointers when a surface is not editable in the UI yet."
          icon={DatabaseZap}
          actions={<HelpTip label="Setup guide help" content="Use these steps for deployment-owned integrations. The UI points you to the config file or API where the setting actually lives." />}
        />
        <div className="space-y-4">
          {catalogSurfaces.map((item) => (
            <Card key={item.title} id={item.action.href.replace("#", "")} className="scroll-mt-24 border-border bg-surface-2">
              <CardHeader className="space-y-2">
                <div className="space-y-1">
                  <CardTitle className="text-base">{item.guide?.heading ?? item.title}</CardTitle>
                  <CardDescription className="max-w-none break-words">{item.description}</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="grid gap-5 xl:grid-cols-[1fr_1.15fr]">
                <div className="space-y-2 text-sm leading-6 text-text-secondary">
                  <p className="font-medium text-text-primary">Where it lives</p>
                  <ul className="space-y-1">
                    {item.guide?.location.map((line) => (
                      <li key={line} className="rounded-lg border border-border-subtle bg-surface-0 px-3 py-2 font-mono text-xs leading-5 break-words">
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="space-y-2 text-sm leading-6 text-text-secondary">
                  <p className="font-medium text-text-primary">How to use it</p>
                  <ol className="space-y-2">
                    {item.guide?.steps.map((step, index) => (
                      <li key={step} className="flex gap-2 rounded-lg border border-border-subtle bg-surface-0 px-3 py-2">
                        <span className="font-mono text-xs text-accent">{index + 1}.</span>
                        <span className="min-w-0 flex-1 break-words">{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </DashboardFrame>
  );
}
