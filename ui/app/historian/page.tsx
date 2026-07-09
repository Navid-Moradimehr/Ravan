import { DatabaseZap } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { HistorianDashboard } from "@/components/historian-views";
import { SqlQueryPanel } from "@/components/sql-query-panel";
import { NotificationPanel } from "@/components/notification-panel";
import { DashboardBuilder } from "@/components/dashboard-builder";
import { WebhookPanel } from "@/components/webhook-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { HelpTip } from "@/components/help-tip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function HistorianPage() {
  return (
    <DashboardFrame
      rightRail={
        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <DatabaseZap aria-hidden="true" className="size-4 text-accent" />
              Historian notes
              <HelpTip
                label="Historian notes help"
                content="The historian is the storage and query layer. This panel explains how to use trends, replay, SQL, and recovery tools without mixing them into the ingest path."
              />
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <Tabs defaultValue="about" className="gap-3">
              <TabsList variant="line" className="w-full justify-start border-b border-border-subtle pb-1">
                <TabsTrigger value="about">About</TabsTrigger>
                <TabsTrigger value="use">How to use</TabsTrigger>
              </TabsList>
              <TabsContent value="about" className="space-y-2 pt-3 text-sm leading-6 text-text-secondary">
                <p>
                  The historian is the platform&apos;s memory. It stores the events that have already been normalized and processed so
                  operators and analysts can query history instead of only watching live traffic.
                </p>
                <p>
                  This page is where you read back what happened, not where you configure the ingest path itself.
                </p>
              </TabsContent>
              <TabsContent value="use" className="space-y-2 pt-3 text-sm leading-6 text-text-secondary">
                <p>
                  Start with the dashboard, then open SQL if you need a custom question, use replay if you need to re-run a scenario,
                  and use webhooks or notifications if you want to connect the historian to external systems.
                </p>
                <p>
                  If you are new to the platform, think of the historian as the place where you ask, “What happened?”, while Kafka UI is
                  the place where you ask, “Did the event move through the broker?”
                </p>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      }
    >
      <div className="space-y-6">
        <header className="app-card overflow-hidden">
          <div className="border-b border-border-subtle px-6 py-5">
            <p className="label-overline">Historian</p>
            <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Storage, queries, and recovery</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This route groups the time-series store, SQL query tools, alerts, dashboards, and backup operations in one place.
            </p>
          </div>
        </header>

        <SectionHeader
          title="Historian workspace"
          eyebrow="Storage"
          description="Query, trend, replay, and manage the historian lifecycle."
          icon={DatabaseZap}
        />
        <section className="scroll-mt-24">
          <HistorianDashboard />
        </section>
        <section id="sql-query" className="scroll-mt-24">
          <SqlQueryPanel />
        </section>
        <section id="webhooks" className="scroll-mt-24">
          <WebhookPanel />
        </section>
        <section id="notifications" className="scroll-mt-24">
          <NotificationPanel />
        </section>
        <section id="dashboard-builder" className="scroll-mt-24">
          <DashboardBuilder />
        </section>
      </div>
    </DashboardFrame>
  );
}
