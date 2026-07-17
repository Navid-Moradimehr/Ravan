"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CircleHelp, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";

export function TopBar({ systemStatus = "online" }: { systemStatus?: "online" | "degraded" | "offline" }) {
  const pathname = usePathname();
  const currentView = pathname === "/" ? "Operations overview" : pathname.slice(1).split("/")[0].replaceAll("-", " ");

  return (
    <header className="sticky top-0 z-30 border-b border-border-subtle bg-surface-0/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1560px] items-center justify-between gap-4 px-4">
        <Link href="/" className="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline-none">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-accent/40 bg-accent-subtle text-accent">
            <Radio aria-hidden="true" className="size-4" />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-heading text-sm font-semibold tracking-tight text-text-primary">Stream Engine</span>
            <span className="hidden text-xs text-text-muted sm:block">Industrial data control plane</span>
          </span>
        </Link>

        <div className="hidden min-w-0 items-center gap-2 md:flex">
          <span className="label-overline">Current view</span>
          <span className="max-w-48 truncate text-sm capitalize text-text-secondary">{currentView}</span>
        </div>

        <div className="flex items-center gap-2.5">
          <Link href="/help-guidance" aria-label="Open help and guidance" className="action-secondary inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition-colors">
            <CircleHelp aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">Help & guidance</span>
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
