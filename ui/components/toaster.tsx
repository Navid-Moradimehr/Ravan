"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToastVariant = "default" | "success" | "error" | "warning" | "info";

export type ToastInput = {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
};

type ToastItem = ToastInput & {
  id: string;
};

const variantStyles: Record<ToastVariant, { icon: typeof Info; className: string }> = {
  default: {
    icon: Info,
    className: "border-border-subtle bg-surface-1 text-text-primary",
  },
  success: {
    icon: CheckCircle2,
    className: "border-success/30 bg-success/10 text-text-primary",
  },
  error: {
    icon: XCircle,
    className: "border-error/30 bg-error/10 text-text-primary",
  },
  warning: {
    icon: AlertTriangle,
    className: "border-warning/30 bg-warning/10 text-text-primary",
  },
  info: {
    icon: Info,
    className: "border-info/30 bg-info/10 text-text-primary",
  },
};

const TOAST_EVENT = "stream-engine:toast";

export function showToast(input: ToastInput): string {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<ToastItem>(TOAST_EVENT, { detail: { ...input, id } }));
  }

  return id;
}

export function ToastHost() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const handleToast = (event: Event) => {
      const customEvent = event as CustomEvent<ToastItem>;
      const toast = customEvent.detail;
      if (!toast?.id) {
        return;
      }

      setToasts((current) => [...current, toast]);
    };

    window.addEventListener(TOAST_EVENT, handleToast as EventListener);
    return () => window.removeEventListener(TOAST_EVENT, handleToast as EventListener);
  }, []);

  useEffect(() => {
    if (!toasts.length) {
      return;
    }

    const timers = toasts.map((toast) =>
      window.setTimeout(() => {
        setToasts((current) => current.filter((item) => item.id !== toast.id));
      }, toast.duration ?? 5000),
    );

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [toasts]);

  const dismiss = (id: string) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  };

  const renderedToasts = useMemo(() => toasts, [toasts]);

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-3">
      {renderedToasts.map((item) => {
        const variant = item.variant ?? "default";
        const styles = variantStyles[variant];
        const Icon = styles.icon;

        return (
          <div
            key={item.id}
            role="status"
            aria-live={variant === "error" ? "assertive" : "polite"}
            className={cn(
              "pointer-events-auto rounded-xl border p-4 shadow-xl backdrop-blur",
              styles.className,
            )}
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-full bg-background/40 p-1.5">
                <Icon className="size-4" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-semibold leading-5">{item.title}</p>
                {item.description ? (
                  <p className="text-sm leading-5 text-text-secondary">{item.description}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                className="rounded-full p-1 text-text-secondary transition-colors hover:bg-background/50 hover:text-text-primary"
                aria-label="Dismiss notification"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
