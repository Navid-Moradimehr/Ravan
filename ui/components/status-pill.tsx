import { cn } from "@/lib/utils";
import type { PipelineNode } from "@/lib/api";

const statusClassName: Record<PipelineNode["status"], string> = {
  active: "border-success/40 bg-success/10 text-success",
  starting: "border-info/40 bg-info/10 text-info",
  degraded: "border-warning/40 bg-warning/10 text-warning",
  offline: "border-error/40 bg-error/10 text-error",
};

export function StatusPill({ status }: { status: PipelineNode["status"] }) {
  return (
    <span className={cn("rounded-full border px-2.5 py-1 text-xs font-medium capitalize", statusClassName[status])}>
      {status}
    </span>
  );
}
