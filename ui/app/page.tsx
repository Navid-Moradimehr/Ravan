"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, DatabaseZap, Gauge, ServerCog } from "lucide-react";
import { getTelemetry } from "@/lib/api";
import { SignalMap } from "@/components/signal-map";
import { ThemeToggle } from "@/components/theme-toggle";

const kpis = [
  { label: "Ingest target", value: "100 msg/s", icon: Activity },
  { label: "Latency budget", value: "<100 ms", icon: Gauge },
  { label: "CDC source", value: "orders", icon: DatabaseZap },
  { label: "Runtime", value: "WSL2 local", icon: ServerCog },
];

export default function Home() {
  const telemetry = useQuery({
    queryKey: ["telemetry"],
    queryFn: getTelemetry,
    refetchInterval: 5000,
  });

  const pipeline = telemetry.data?.pipeline ?? [
    { name: "ingest", status: "starting" as const },
    { name: "process", status: "starting" as const },
    { name: "ai", status: "starting" as const },
    { name: "observe", status: "starting" as const },
  ];

  return (
    <main className="min-h-dvh bg-surface-0 px-4 py-5 text-primary sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="surface-card rounded-2xl p-5">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-mono text-sm uppercase text-accent">Local Stream Engine</p>
              <h1 className="mt-3 max-w-4xl text-balance text-4xl font-semibold text-primary md:text-6xl">
                Real-time streaming and BI control plane.
              </h1>
              <p className="mt-4 max-w-3xl text-pretty text-base leading-7 text-secondary">
                Monitor Redpanda ingestion, Flink processing, Debezium CDC, and AI explanations from one local cockpit.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <ThemeToggle />
              <a
                href="http://localhost:18080"
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-surface-2 px-4 text-sm font-medium text-primary transition-colors duration-150 hover:bg-surface-3"
              >
                Open Redpanda Console
              </a>
            </div>
          </div>
        </header>

        <section aria-label="Key platform indicators" className="grid gap-3 md:grid-cols-4">
          {kpis.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.label} className="surface-card rounded-2xl p-5">
                <Icon aria-hidden="true" className="size-5 text-accent" />
                <div className="mt-5 font-mono text-2xl tabular-nums text-primary">{item.value}</div>
                <div className="mt-1 text-sm text-secondary">{item.label}</div>
              </article>
            );
          })}
        </section>

        <SignalMap nodes={pipeline} />

        <section className="grid gap-5 lg:grid-cols-2">
          <article className="surface-card rounded-2xl p-5">
            <h2 className="text-balance text-lg font-semibold">AI Gateway</h2>
            <dl className="mt-5 space-y-4 text-sm">
              <div>
                <dt className="text-muted">Model</dt>
                <dd className="mt-1 font-mono text-primary">{telemetry.data?.llm.model ?? "openai/gpt-oss-20B"}</dd>
              </div>
              <div>
                <dt className="text-muted">Base URL</dt>
                <dd className="mt-1 break-words font-mono text-primary">
                  {telemetry.data?.llm.base_url ?? "http://172.17.0.1:1234/v1"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Last error</dt>
                <dd className="mt-1 text-primary">{telemetry.data?.llm.last_error ?? "None reported"}</dd>
              </div>
            </dl>
          </article>

          <article className="surface-card rounded-2xl p-5">
            <h2 className="text-balance text-lg font-semibold">Operator Links</h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {[
                ["Grafana", "http://localhost:13000"],
                ["Prometheus", "http://localhost:19090"],
                ["Flink UI", "http://localhost:18088"],
                ["AI Health", "http://localhost:8080/health"],
              ].map(([label, href]) => (
                <a
                  key={href}
                  href={href}
                  className="min-h-11 rounded-lg border border-border-subtle bg-surface-2 px-4 py-3 text-sm text-primary transition-colors duration-150 hover:bg-surface-3"
                >
                  {label}
                </a>
              ))}
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
