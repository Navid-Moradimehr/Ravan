"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { CircleHelp } from "lucide-react";
import { cn } from "@/lib/utils";

type HelpTipProps = {
  label: string;
  content: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
};

export function HelpTip({ label, content, side = "top", className }: HelpTipProps) {
  const [open, setOpen] = useState(false);
  const position = {
    top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
    bottom: "left-1/2 top-full mt-2 -translate-x-1/2",
    left: "right-full top-1/2 mr-2 -translate-y-1/2",
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
  }[side];

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen(true)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className={cn(
          "inline-flex size-6 items-center justify-center rounded-full border border-border-subtle bg-surface-2 text-text-secondary transition-colors hover:bg-accent-subtle hover:text-accent focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
        )}
      >
        <CircleHelp aria-hidden="true" className="size-3.5" />
      </button>
      {open ? (
        <span
          role="tooltip"
          className={cn(
            "pointer-events-auto absolute z-[70] w-max max-w-sm rounded-lg border border-border-subtle bg-foreground px-3 py-2 text-xs leading-5 text-background shadow-lg",
            position,
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
