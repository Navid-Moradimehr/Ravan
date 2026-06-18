"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, DatabaseZap, Gauge, ServerCog } from "lucide-react";
import { getTelemetry } from "@/lib/api";
import { SignalMap } from "@/components/signal-map";

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
    <main className="min-h-dvh bg-graphite-950 px-4 py-5 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="rounded-2xl border border-slate-800 bg-graphite-900 p-5 shadow-xl">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-mono text-sm uppercase text-sky-300">Local Stream Engine</p>
              <h1 className="mt-3 max-w-4xl text-balance text-4xl font-semibold text-white md:text-6xl">
                Real-time streaming and BI control plane.
              </h1>
              <p className="mt-4 max-w-3xl text-pretty text-base leading-7 text-slate-300">
                Monitor Redpanda ingestion, Flink processing, Debezium CDC, and AI explanations from one local cockpit.
              </p>
            </div>
            <a
              href="http://localhost:18080"
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-700 px-4 text-sm font-medium text-slate-100 hover:bg-slate-800"
            >
              Open Redpanda Console
            </a>
          </div>
        </header>

        <section aria-label="Key platform indicators" className="grid gap-3 md:grid-cols-4">
          {kpis.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.label} className="rounded-2xl border border-slate-800 bg-graphite-900 p-5">
                <Icon aria-hidden="true" className="size-5 text-sky-300" />
                <div className="mt-5 font-mono text-2xl tabular-nums text-white">{item.value}</div>
                <div className="mt-1 text-sm text-slate-400">{item.label}</div>
              </article>
            );
          })}
        </section>

        <SignalMap nodes={pipeline} />

        <section className="grid gap-5 lg:grid-cols-2">
          <article className="rounded-2xl border border-slate-800 bg-graphite-900 p-5">
            <h2 className="text-balance text-lg font-semibold">AI Gateway</h2>
            <dl className="mt-5 space-y-4 text-sm">
              <div>
                <dt className="text-slate-500">Model</dt>
                <dd className="mt-1 font-mono text-slate-100">{telemetry.data?.llm.model ?? "openai/gpt-oss-20B"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Base URL</dt>
                <dd className="mt-1 break-words font-mono text-slate-100">
                  {telemetry.data?.llm.base_url ?? "http://172.17.0.1:1234/v1"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Last error</dt>
                <dd className="mt-1 text-slate-100">{telemetry.data?.llm.last_error ?? "None reported"}</dd>
              </div>
            </dl>
          </article>

          <article className="rounded-2xl border border-slate-800 bg-graphite-900 p-5">
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
                  className="min-h-11 rounded-lg border border-slate-800 px-4 py-3 text-sm text-slate-100 hover:bg-slate-800"
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
