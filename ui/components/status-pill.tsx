import { cn } from "@/lib/utils";
import type { PipelineNode } from "@/lib/api";

const statusClassName: Record<PipelineNode["status"], string> = {
  active: "border-success/30 bg-success/10 text-success",
  starting: "border-info/30 bg-info/10 text-info",
  degraded: "border-warning/30 bg-warning/10 text-warning",
  offline: "border-error/30 bg-error/10 text-error",
};

const statusDot: Record<PipelineNode["status"], string> = {
  active: "bg-success",
  starting: "bg-info",
  degraded: "bg-warning",
  offline: "bg-error",
};

export function StatusPill({ status }: { status: PipelineNode["status"] }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize", statusClassName[status])}>
      <span className={cn("size-1.5 rounded-full", statusDot[status])} aria-hidden="true" />
      {status}
    </span>
  );
}
