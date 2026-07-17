"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { BookOpen, ChevronDown, CircleHelp, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";

export function TopBar({ systemStatus = "online" }: { systemStatus?: "online" | "degraded" | "offline" }) {
  const pathname = usePathname();
  const router = useRouter();
  const [helpOpen, setHelpOpen] = useState(false);
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
          <div className="relative">
            <Button variant="ghost" size="sm" aria-label="Open help and guidance" aria-expanded={helpOpen} onClick={() => setHelpOpen((open) => !open)} className="gap-1.5 text-text-secondary hover:text-text-primary">
              <CircleHelp aria-hidden="true" className="size-4" />
              <span className="hidden sm:inline">Help & guidance</span>
              <ChevronDown aria-hidden="true" className={`size-3.5 transition-transform ${helpOpen ? "rotate-180" : ""}`} />
            </Button>
            {helpOpen ? <div role="dialog" aria-label="Platform help and guidance" className="absolute right-0 top-11 z-50 w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-border-subtle bg-surface-raised p-3 text-text-primary shadow-overlay">
              <div className="border-b border-border-subtle pb-3">
                <p className="text-sm font-semibold">Operate the platform</p>
                <p className="mt-1 text-xs leading-5 text-text-secondary">Start in Integrations to register a source, validate its protocol settings, test connectivity, and enable ingestion. Then verify Kafka delivery, metrics, historian writes, and optional AI output.</p>
              </div>
              <div className="space-y-1 pt-2">
                <button type="button" onClick={() => { setHelpOpen(false); router.push("/integrations#source-connections"); }} className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors hover:bg-accent-subtle"><BookOpen aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" /><span><span className="block font-medium">Source setup guide</span><span className="block text-xs leading-5 text-text-secondary">Connect OPC UA, MQTT, Modbus, REST, or HTTP sources.</span></span></button>
                <button type="button" onClick={() => { setHelpOpen(false); router.push("/pipeline"); }} className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors hover:bg-accent-subtle"><Radio aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" /><span><span className="block font-medium">Understand the event pipeline</span><span className="block text-xs leading-5 text-text-secondary">Trace ingestion, normalization, processing, DLQ, and sinks.</span></span></button>
                <button type="button" onClick={() => { setHelpOpen(false); router.push("/historian"); }} className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors hover:bg-accent-subtle"><BookOpen aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" /><span><span className="block font-medium">Historian and query guide</span><span className="block text-xs leading-5 text-text-secondary">Explore trends, alarms, SQL, replay, and custom panels.</span></span></button>
              </div>
            </div> : null}
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
