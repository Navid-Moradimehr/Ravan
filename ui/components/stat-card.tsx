import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type StatCardProps = {
  label: string;
  value: string | number;
  unit?: string;
  icon?: LucideIcon;
  tone?: "default" | "success" | "warning" | "error" | "info";
  hint?: string;
  className?: string;
  compact?: boolean;
};

const toneRing: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-text-secondary",
  success: "text-success",
  warning: "text-warning",
  error: "text-error",
  info: "text-info",
};

export function StatCard({ label, value, unit, icon: Icon, tone = "default", hint, className, compact = false }: StatCardProps) {
  return (
    <div className={cn("kpi-card p-4", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="label-overline">{label}</span>
        {Icon ? <Icon aria-hidden="true" className={cn("size-4", toneRing[tone])} /> : null}
      </div>
      <div className={cn("mt-3 flex items-baseline gap-1.5", compact && "flex-wrap")}>
        <span
          className={cn(
            "font-heading font-semibold tracking-tight text-text-primary text-tabular",
            compact ? "max-w-full break-words text-[1.05rem] leading-snug sm:text-[1.15rem]" : "text-[1.75rem] leading-none",
          )}
        >
          {value}
        </span>
        {unit ? <span className="text-sm font-medium text-text-muted">{unit}</span> : null}
      </div>
      {hint ? <p className="mt-2 text-xs leading-5 text-text-secondary">{hint}</p> : null}
    </div>
  );
}
