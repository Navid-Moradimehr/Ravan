import { cn } from "@/lib/utils";
import type { PipelineNode } from "@/lib/api";

const statusClassName: Record<PipelineNode["status"], string> = {
  active: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  starting: "border-sky-500/40 bg-sky-500/10 text-sky-200",
  degraded: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  offline: "border-red-500/40 bg-red-500/10 text-red-200",
};

export function StatusPill({ status }: { status: PipelineNode["status"] }) {
  return (
    <span className={cn("rounded-full border px-2.5 py-1 text-xs font-medium capitalize", statusClassName[status])}>
      {status}
    </span>
  );
}
