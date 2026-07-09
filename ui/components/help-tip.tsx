"use client";

import type { ReactNode } from "react";
import { CircleHelp } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type HelpTipProps = {
  label: string;
  content: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
};

export function HelpTip({ label, content, side = "top", className }: HelpTipProps) {
  return (
    <Tooltip>
      <TooltipTrigger
        aria-label={label}
        className={cn(
          "inline-flex size-6 items-center justify-center rounded-full border border-border-subtle bg-surface-2 text-text-secondary transition-colors hover:bg-accent-subtle hover:text-accent focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
        )}
      >
        <CircleHelp aria-hidden="true" className="size-3.5" />
      </TooltipTrigger>
      <TooltipContent
        side={side}
        className="max-w-sm rounded-lg border border-border-subtle bg-foreground px-3 py-2 text-xs leading-5 text-background shadow-lg"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );
}
