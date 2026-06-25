"use client";

import { Activity, Radio } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

export function TopBar({ systemStatus = "online" }: { systemStatus?: "online" | "degraded" | "offline" }) {
  const tone =
    systemStatus === "online"
      ? "border-success/40 bg-success/10 text-success"
      : systemStatus === "degraded"
        ? "border-warning/40 bg-warning/10 text-warning"
        : "border-error/40 bg-error/10 text-error";

  return (
    <header className="sticky top-0 z-30 border-b border-border-subtle bg-surface-0/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1560px] items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-lg border border-accent/40 bg-accent-subtle text-accent">
            <Radio aria-hidden="true" className="size-4" />
          </span>
          <div className="flex items-baseline gap-2">
            <span className="font-heading text-sm font-semibold tracking-tight text-text-primary">Stream Engine</span>
            <span className="hidden text-xs text-text-muted sm:inline">Control Plane</span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <span className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium sm:inline-flex ${tone}`}>
            <Activity aria-hidden="true" className="size-3" />
            <span className="capitalize">{systemStatus}</span>
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
