"use client";

import { useEffect } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { Toaster, toast } from "sonner";

export type ToastVariant = "default" | "success" | "error" | "warning" | "info";
export type ToastInput = { title: string; description?: string; variant?: ToastVariant; duration?: number };
type ToastItem = ToastInput & { id: string };
const TOAST_EVENT = "stream-engine:toast";

const icons = { default: Info, success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info };

export function showToast(input: ToastInput): string {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent<ToastItem>(TOAST_EVENT, { detail: { ...input, id } }));
  return id;
}

export function ToastHost() {
  useEffect(() => {
    const handleToast = (event: Event) => {
      const item = (event as CustomEvent<ToastItem>).detail;
      if (!item?.id) return;
      const Icon = icons[item.variant ?? "default"];
      toast.custom(() => (
        <div className="flex w-[min(24rem,calc(100vw-2rem))] items-start gap-3 rounded-xl border border-border-subtle bg-surface-raised p-4 text-text-primary shadow-xl">
          <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="min-w-0 flex-1"><p className="text-sm font-semibold leading-5">{item.title}</p>{item.description ? <p className="mt-1 text-sm leading-5 text-text-secondary">{item.description}</p> : null}</div>
        </div>
      ), { id: item.id, duration: item.duration ?? 5000 });
    };
    window.addEventListener(TOAST_EVENT, handleToast as EventListener);
    return () => window.removeEventListener(TOAST_EVENT, handleToast as EventListener);
  }, []);
  return <Toaster position="top-right" closeButton richColors toastOptions={{ className: "!border-border-subtle !bg-surface-raised !text-text-primary" }} />;
}
