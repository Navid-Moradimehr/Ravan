"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BrainCircuit } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { AIReportJob } from "@/components/operational-briefing";
import { requestJson } from "@/lib/http";

export function LatestAIBriefing({ reportType, title = "Latest AI briefing" }: { reportType?: string; title?: string }) {
  const reports = useQuery({
    queryKey: ["latest-ai-briefing", reportType ?? "all"],
    queryFn: () => requestJson<AIReportJob[]>(`/api/ai/reports?status=completed&limit=1${reportType ? `&report_type=${encodeURIComponent(reportType)}` : ""}`),
    refetchInterval: 60000,
  });
  const job = reports.data?.[0];
  const briefing = job?.result?.briefing;
  return (
    <Card className="app-card overflow-hidden">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base"><BrainCircuit className="size-4 text-accent" />{title}</CardTitle>
        <CardDescription>Current advisory context from the operational reporting harness.</CardDescription>
      </CardHeader>
      <CardContent className="p-4">
        {briefing ? <div>
          <div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="capitalize">{briefing.situation_status}</Badge><span className="font-mono text-xs text-text-muted">{job.site_id}</span></div>
          <h3 className="mt-3 font-heading text-lg font-semibold leading-tight text-text-primary">{briefing.headline}</h3>
          <p className="mt-2 line-clamp-3 font-sans text-sm leading-6 text-text-secondary">{briefing.executive_summary}</p>
          <Link href={`/ai-reporting?report=${encodeURIComponent(job.job_id)}`} className="mt-4 inline-flex items-center gap-2 font-sans text-sm font-semibold text-accent">Open briefing<ArrowRight className="size-4" /></Link>
        </div> : <p className="font-sans text-sm leading-6 text-text-secondary">{reports.isLoading ? "Loading the latest briefing…" : "No completed briefing is available. The platform will not display mock AI output."}</p>}
      </CardContent>
    </Card>
  );
}
