import { BarChart3, Cable, DatabaseZap, Webhook } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const integrations = [
  { title: "Debezium CDC", description: "PostgreSQL orders into Kafka topics.", tone: "default" },
  { title: "Kafka sinks", description: "Outbound bridge to MQTT, AMQP, and external listeners.", tone: "info" },
  { title: "Webhooks", description: "HTTP notifications for external systems.", tone: "warning" },
  { title: "AI providers", description: "OpenAI-compatible, LM Studio, vLLM, Ollama, and local models.", tone: "default" },
  { title: "Connector catalog", description: "MQTT, OPC UA, Modbus, SQL, REST, and file adapters.", tone: "default" },
  { title: "Reports", description: "Operational and compliance reporting after storage.", tone: "info" },
];

export default function IntegrationsPage() {
  return (
    <DashboardFrame
      rightRail={
        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <Webhook aria-hidden="true" className="size-4 text-accent" />
              Integration boundary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
            <p>These are post-ingest or external-system surfaces.</p>
            <p>Keep plant-specific credentials and endpoint policies on the operator side for self-hosted deployments.</p>
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
              the platform owns and what the deployment owner must supply.
            </p>
          </div>
        </header>

        <SectionHeader
          title="Integration catalog"
          eyebrow="Surface area"
          description="Post-storage sinks and external-system bridges."
          icon={BarChart3}
        />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {integrations.map((item) => (
            <Card key={item.title} className="border-border bg-surface-2">
              <CardHeader>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription>{item.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Badge variant="outline" className="border-border-subtle bg-surface-0 text-text-secondary">
                  {item.tone}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>

        <SectionHeader
          title="Data ownership boundary"
          eyebrow="Policy"
          description="What the platform owns versus what the user must bring."
          icon={Cable}
        />
        <div className="grid gap-3 md:grid-cols-2">
          <Card className="border-border bg-surface-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <DatabaseZap aria-hidden="true" className="size-4 text-accent" />
                Platform-owned
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-6 text-text-secondary">
              Connectors, schemas, routes, retry logic, dashboards, benchmarks, and operator tooling.
            </CardContent>
          </Card>
          <Card className="border-border bg-surface-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Webhook aria-hidden="true" className="size-4 text-accent" />
                User-owned
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-6 text-text-secondary">
              Secrets, endpoint URLs, broker credentials, cloud accounts, plant networking, and site security policy.
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardFrame>
  );
}
