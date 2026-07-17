import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type SectionHeaderProps = {
  title: string;
  description?: string;
  icon?: LucideIcon;
  eyebrow?: string;
  actions?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
};

export function SectionHeader({ title, description, icon: Icon, eyebrow, actions, className, children }: SectionHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-x-4 gap-y-3", className)}>
      <div className="min-w-0 space-y-1">
        {eyebrow ? <p className="label-overline">{eyebrow}</p> : null}
        <div className="flex items-start gap-2.5">
          {Icon ? (
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2 text-accent">
              <Icon aria-hidden="true" className="size-4" />
            </span>
          ) : null}
          <div className="flex min-w-0 items-start gap-2">
            <h2 className="font-heading text-lg font-semibold tracking-tight text-text-primary">{title}</h2>
            {children ? <div className="pt-0.5">{children}</div> : null}
          </div>
        </div>
        {description ? (
          <p className="max-w-2xl text-pretty text-sm leading-5 text-text-secondary">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
