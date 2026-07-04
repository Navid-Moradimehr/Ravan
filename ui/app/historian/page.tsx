import { DatabaseZap } from "lucide-react";
import { DashboardFrame } from "@/components/dashboard-frame";
import { SectionHeader } from "@/components/section-header";
import { HistorianDashboard } from "@/components/historian-views";
import { SqlQueryPanel } from "@/components/sql-query-panel";
import { NotificationPanel } from "@/components/notification-panel";
import { DashboardBuilder } from "@/components/dashboard-builder";
import { WebhookPanel } from "@/components/webhook-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HistorianPage() {
  return (
    <DashboardFrame
      rightRail={
        <Card className="app-card overflow-hidden">
          <CardHeader className="app-card-header rounded-none border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <DatabaseZap aria-hidden="true" className="size-4 text-accent" />
              Historian notes
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-4 text-sm leading-6 text-text-secondary">
            <p>Queries, retention, backups, replay, and dashboards live here.</p>
            <p>The page is intentionally after storage, not part of the raw ingest path.</p>
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
        <HistorianDashboard />
        <SqlQueryPanel />
        <WebhookPanel />
        <NotificationPanel />
        <DashboardBuilder />
      </div>
    </DashboardFrame>
  );
}
