"use client";

import { useState, useCallback } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Calculator, Plus, Trash2, Save } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";

type KPIFormula = {
  kpi_id: string;
  name: string;
  description: string;
  input_tags: string[];
  expression: string;
  window_seconds: number;
  unit: string;
  warning_threshold: number | null;
  critical_threshold: number | null;
  enabled: boolean;
};

async function getKPIs(): Promise<KPIFormula[]> {
  return requestJson("/api/kpis");
}

async function createKPI(kpi: KPIFormula): Promise<{ ok: boolean }> {
  return requestJson("/api/kpis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(kpi),
  });
}

async function deleteKPI(kpi_id: string): Promise<{ ok: boolean }> {
  return requestJson(`/api/kpis/${encodeURIComponent(kpi_id)}`, { method: "DELETE" });
}

export function KPIBuilder() {
  const [form, setForm] = useState<KPIFormula>({
    kpi_id: "",
    name: "",
    description: "",
    input_tags: [""],
    expression: "",
    window_seconds: 60,
    unit: "",
    warning_threshold: null,
    critical_threshold: null,
    enabled: true,
  });

  const query = useQuery({ queryKey: ["kpis"], queryFn: getKPIs });
  const create = useMutation({
    mutationFn: createKPI,
    onSuccess: () => {
      query.refetch();
      showToast({
        title: "KPI saved",
        description: "The new KPI definition is available for evaluation.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "KPI save failed",
        description: formatErrorMessage(error, "The KPI could not be saved."),
        variant: "error",
      });
    },
  });
  const remove = useMutation({
    mutationFn: deleteKPI,
    onSuccess: () => {
      query.refetch();
      showToast({
        title: "KPI deleted",
        description: "The KPI definition was removed.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "KPI delete failed",
        description: formatErrorMessage(error, "The KPI could not be deleted."),
        variant: "error",
      });
    },
  });

  const addTag = useCallback(() => setForm((f) => ({ ...f, input_tags: [...f.input_tags, ""] })), []);
  const removeTag = useCallback((i: number) => setForm((f) => ({ ...f, input_tags: f.input_tags.filter((_, idx) => idx !== i) })), []);
  const setTag = useCallback((i: number, val: string) => setForm((f) => { const t = [...f.input_tags]; t[i] = val; return { ...f, input_tags: t }; }), []);

  const submit = useCallback(() => {
    const name = form.name.trim();
    const expression = form.expression.trim();
    const unit = form.unit.trim();
    const input_tags = form.input_tags.map((tag) => tag.trim()).filter(Boolean);
    if (!name || !expression || !input_tags.length || !Number.isFinite(form.window_seconds) || form.window_seconds <= 0) {
      showToast({
        title: "KPI definition incomplete",
        description: "Fill in the KPI name, expression, window, and at least one input tag before saving.",
        variant: "warning",
      });
      return;
    }
    const kpi = {
      ...form,
      kpi_id: form.kpi_id || `kpi-${Date.now()}`,
      name,
      expression,
      unit,
      input_tags,
      window_seconds: Math.max(1, Math.round(form.window_seconds)),
    };
    create.mutate(kpi);
  }, [form, create]);

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Calculator className="size-4 text-accent" />
          KPI Builder
        </CardTitle>
        <CardDescription className="text-text-secondary">Define calculated metrics from raw tags</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="grid gap-3">
          <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="KPI Name" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm" />
          <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Description" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm min-h-[60px]" />
          <div className="space-y-2">
            <label className="text-xs font-medium text-text-secondary">Input Tags</label>
            {form.input_tags.map((tag, i) => (
              <div key={i} className="flex gap-2">
                <input value={tag} onChange={(e) => setTag(i, e.target.value)} placeholder={`Tag ${i + 1}`} className="flex-1 rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm" />
                <Button variant="ghost" size="sm" onClick={() => removeTag(i)}><Trash2 className="size-4 text-error" /></Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addTag}><Plus className="size-4 mr-1" />Add Tag</Button>
          </div>
          <textarea value={form.expression} onChange={(e) => setForm((f) => ({ ...f, expression: e.target.value }))} placeholder="Expression (e.g., (temp + press) / 2)" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm font-mono min-h-[60px]" />
          <div className="grid grid-cols-3 gap-2">
            <input type="number" value={form.window_seconds} onChange={(e) => setForm((f) => ({ ...f, window_seconds: Number(e.target.value) }))} placeholder="Window (s)" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm" />
            <input value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} placeholder="Unit" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input type="number" value={form.warning_threshold ?? ""} onChange={(e) => setForm((f) => ({ ...f, warning_threshold: e.target.value ? Number(e.target.value) : null }))} placeholder="Warning Threshold" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm" />
            <input type="number" value={form.critical_threshold ?? ""} onChange={(e) => setForm((f) => ({ ...f, critical_threshold: e.target.value ? Number(e.target.value) : null }))} placeholder="Critical Threshold" className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm" />
          </div>
          <Button onClick={submit} disabled={create.isPending || !form.name.trim() || !form.expression.trim()} className="inline-flex items-center gap-2">
            <Save className="size-4" />{create.isPending ? "Saving..." : "Save KPI"}
          </Button>
        </div>

        <div className="space-y-2">
          <h4 className="text-sm font-medium text-text-secondary">Registered KPIs</h4>
          {query.isError ? (
            <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-text-primary">
              {formatErrorMessage(query.error, "KPI definitions could not be loaded.")}
            </p>
          ) : null}
          {query.data?.map((kpi) => (
            <div key={kpi.kpi_id} className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface-2 px-3 py-2">
              <div className="space-y-0.5">
                <div className="text-sm font-medium">{kpi.name}</div>
                <div className="text-xs text-text-secondary">{kpi.expression}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-[10px]">{kpi.unit}</Badge>
                <Button variant="ghost" size="sm" onClick={() => remove.mutate(kpi.kpi_id)}><Trash2 className="size-4 text-error" /></Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
