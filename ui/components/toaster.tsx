"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "success" | "error" | "warning" | "info";

type ToastInput = {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
};

type ToastItem = ToastInput & {
  id: string;
};

type ToastContextValue = {
  toast: (input: ToastInput) => string;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

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

export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error("useToast must be used within a <ToastProvider />");
  }

  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    setMounted(true);
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

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback((input: ToastInput) => {
    const id = typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);

    setToasts((current) => [...current, { ...input, id }]);
    return id;
  }, []);

  const contextValue = useMemo(() => ({ toast, dismiss }), [dismiss, toast]);

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {mounted ? (
        <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-3">
          {toasts.map((item) => {
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
      ) : null}
    </ToastContext.Provider>
  );
}
