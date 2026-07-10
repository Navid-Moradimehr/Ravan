"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowRight, BarChart3, Cable, DatabaseZap, Gauge, LayoutDashboard, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TopBar } from "@/components/top-bar";
import { Separator } from "@/components/ui/separator";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
};

const navItems: NavItem[] = [
  { href: "/", label: "Command center", icon: LayoutDashboard, description: "Overview and quick actions" },
  { href: "/historian", label: "Historian", icon: DatabaseZap, description: "Storage, queries, backup" },
  { href: "/observability", label: "Observability", icon: Gauge, description: "Health, metrics, latency" },
  { href: "/integrations", label: "Integrations", icon: BarChart3, description: "CDC, webhooks, models" },
  { href: "/pipeline", label: "Pipeline", icon: Cable, description: "Ingress, normalization, DLQ" },
];

type DashboardFrameProps = {
  children: ReactNode;
  rightRail?: ReactNode;
  systemStatus?: "online" | "degraded" | "offline";
};

export function DashboardFrame({ children, rightRail, systemStatus = "online" }: DashboardFrameProps) {
  const pathname = usePathname();

  return (
    <div className="industrial-shell min-h-dvh bg-surface-0 text-text-primary">
      <TopBar systemStatus={systemStatus} />

      <main className="mx-auto grid max-w-[1560px] gap-5 px-4 py-5 grid-cols-1 lg:grid-cols-[248px_minmax(0,1fr)_320px]">
        <aside className="panel-rail hidden flex-col rounded-xl p-4 lg:sticky lg:top-[4.5rem] lg:flex lg:h-[calc(100dvh-5.5rem)]">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg border border-accent/40 bg-accent-subtle text-accent">
              <LayoutDashboard aria-hidden="true" className="size-5" />
            </span>
            <div className="leading-tight">
              <div className="label-overline">LSE</div>
              <div className="font-heading text-sm font-semibold">Industrial Control Plane</div>
            </div>
          </div>

          <Separator className="my-4 bg-border-subtle" />

          <nav aria-label="Primary" className="space-y-1">
            <p className="label-overline mb-2 px-2">Navigate</p>
            {navItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors",
                    active ? "nav-active border-accent/30" : "nav-muted border-transparent",
                  )}
                >
                  <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="block text-xs leading-5 text-text-secondary">{item.description}</span>
                  </span>
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto rounded-lg border border-border-subtle bg-surface-2 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <ArrowRight aria-hidden="true" className="size-4 text-accent" />
              Hardware-free mode
            </div>
            <p className="mt-2 text-pretty text-xs leading-5 text-text-secondary">
              Kafka, Flink, TimescaleDB, and local simulators keep the full industrial flow repeatable without plant access.
            </p>
          </div>
        </aside>

        <div className="min-w-0 space-y-6">
          <nav aria-label="Primary" className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
            {navItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium whitespace-nowrap",
                    active ? "border-accent/30 bg-accent-subtle text-accent" : "border-border-subtle bg-surface-2 text-text-secondary",
                  )}
                >
                  <Icon aria-hidden="true" className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {children}
        </div>

        <aside className="space-y-4">{rightRail}</aside>
      </main>
    </div>
  );
}
