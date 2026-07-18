"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Maximize2, Minimize2, X } from "lucide-react";
import { Button } from "@/components/ui/button";

type Rect = { left: number; top: number; width: number; height: number };
type Phase = "opening" | "open" | "closing";

function rectOf(element: HTMLElement | null): Rect | null {
  if (!element) return null;
  const rect = element.getBoundingClientRect();
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

function targetRect(): Rect {
  const width = Math.min(Math.max(window.innerWidth - 32, 280), 1080);
  const height = Math.min(Math.max(window.innerHeight - 64, 240), 760);
  return {
    left: Math.round((window.innerWidth - width) / 2),
    top: Math.round((window.innerHeight - height) / 2),
    width,
    height,
  };
}

function rectStyle(rect: Rect): CSSProperties {
  return {
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
  };
}

export function ExpandableChart({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const originRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const [phase, setPhase] = useState<Phase | null>(null);
  const [originRect, setOriginRect] = useState<Rect | null>(null);
  const [dialogRect, setDialogRect] = useState<Rect | null>(null);

  useEffect(() => () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
  }, []);

  useEffect(() => {
    if (!phase) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
        "button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])",
      )).filter((element) => !element.hasAttribute("disabled"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [phase]);

  useEffect(() => {
    if (!phase) return;
    const focusTimer = window.setTimeout(() => dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [phase]);

  const open = () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const from = rectOf(originRef.current);
    if (!from) return;
    setOriginRect(from);
    setDialogRect(from);
    setPhase("opening");
    requestAnimationFrame(() => requestAnimationFrame(() => {
      setDialogRect(targetRect());
      setPhase("open");
    }));
  };

  const close = () => {
    if (!phase || !originRect) return;
    setDialogRect(rectOf(originRef.current) ?? originRect);
    setPhase("closing");
    closeTimerRef.current = window.setTimeout(() => {
      setPhase(null);
      setDialogRect(null);
      restoreFocusRef.current?.focus();
    }, 280);
  };

  return (
    <>
      <div ref={originRef} className={`relative min-w-0 ${className}`}>
        <div aria-hidden={Boolean(phase)} className={phase ? "invisible" : ""}>
          {children}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="absolute right-2 top-2 z-10 border border-border-subtle bg-surface-1/85 text-text-secondary shadow-sm backdrop-blur-sm hover:bg-surface-2 hover:text-text-primary"
          aria-label={`Maximize ${label}`}
          title={`Maximize ${label}`}
          onClick={open}
        >
          <Maximize2 aria-hidden="true" />
        </Button>
      </div>
      {phase && dialogRect ? (
        <div
          className="chart-expand-backdrop"
          data-phase={phase}
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) close();
          }}
        >
          <div
            ref={dialogRef}
            className="chart-expand-dialog"
            data-phase={phase}
            role="dialog"
            aria-modal="true"
            aria-label={`${label} expanded`}
            style={rectStyle(dialogRect)}
          >
            <div className="flex min-h-10 items-center justify-between gap-3 border-b border-border-subtle px-3 py-2">
              <div className="min-w-0 truncate text-sm font-semibold text-text-primary">{label}</div>
              <div className="flex shrink-0 items-center gap-1">
                <Button type="button" variant="ghost" size="icon-sm" aria-label={`Minimize ${label}`} title={`Minimize ${label}`} onClick={close}>
                  <Minimize2 aria-hidden="true" />
                </Button>
                <Button type="button" variant="ghost" size="icon-sm" aria-label={`Close ${label}`} title={`Close ${label}`} onClick={close}>
                  <X aria-hidden="true" />
                </Button>
              </div>
            </div>
            <div className="chart-expand-body">{children}</div>
          </div>
        </div>
      ) : null}
    </>
  );
}
