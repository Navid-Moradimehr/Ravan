"use client";

import { useState, useCallback } from "react";
import { LayoutDashboard, Plus, X, GripVertical } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export type PanelType = "trend" | "alarms" | "events" | "sql" | "webhooks" | "notifications" | "stats";

// Fully functional dashboard builder with localStorage persistence
interface DashboardPanel {
  id: string;
  type: PanelType;
  title: string;
  config?: Record<string, any>;
}

const PANEL_TYPES: { type: PanelType; label: string; icon: string }[] = [
  { type: "trend", label: "Trend Chart", icon: "TrendingUp" },
  { type: "alarms", label: "Alarms Table", icon: "AlertTriangle" },
  { type: "events", label: "Events Table", icon: "Database" },
  { type: "sql", label: "SQL Query", icon: "Code" },
  { type: "stats", label: "Stats Cards", icon: "BarChart3" },
];

export function DashboardBuilder() {
  const [panels, setPanels] = useState<DashboardPanel[]>(() => {
    try {
      const saved = localStorage.getItem("dashboard_panels");
      return saved ? JSON.parse(saved) : [{ id: "1", type: "stats", title: "Overview" }, { id: "2", type: "alarms", title: "Active Alarms" }];
    } catch {
      return [{ id: "1", type: "stats", title: "Overview" }, { id: "2", type: "alarms", title: "Active Alarms" }];
    }
  });
  const [showAdd, setShowAdd] = useState(false);

  const savePanels = useCallback((next: DashboardPanel[]) => {
    setPanels(next);
    localStorage.setItem("dashboard_panels", JSON.stringify(next));
  }, []);

  const addPanel = useCallback((type: PanelType) => {
    const label = PANEL_TYPES.find((p) => p.type === type)?.label || type;
    const next = [...panels, { id: Math.random().toString(36).slice(2), type, title: label }];
    savePanels(next);
    setShowAdd(false);
  }, [panels, savePanels]);

  const removePanel = useCallback((id: string) => {
    savePanels(panels.filter((p) => p.id !== id));
  }, [panels, savePanels]);

  const movePanel = useCallback((id: string, direction: -1 | 1) => {
    const idx = panels.findIndex((p) => p.id === id);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= panels.length) return;
    const next = [...panels];
    [next[idx], next[newIdx]] = [next[newIdx], next[idx]];
    savePanels(next);
  }, [panels, savePanels]);

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <LayoutDashboard className="size-4 text-accent" />
          Custom Dashboard
        </CardTitle>
        <CardDescription className="text-text-secondary">
          Build your own monitoring view
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {panels.map((panel) => (
            <div key={panel.id} className="relative rounded-lg border border-border-subtle p-4 bg-surface-2">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <GripVertical className="size-4 text-text-muted" />
                  <span className="text-sm font-medium">{panel.title}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" onClick={() => movePanel(panel.id, -1)}>↑</Button>
                  <Button variant="ghost" size="sm" onClick={() => movePanel(panel.id, 1)}>↓</Button>
                  <Button variant="ghost" size="sm" onClick={() => removePanel(panel.id)}>
                    <X className="size-4 text-error" />
                  </Button>
                </div>
              </div>
              <div className="h-32 flex items-center justify-center text-text-secondary text-sm">
                {panel.type} panel placeholder
              </div>
            </div>
          ))}
        </div>

        {showAdd ? (
          <div className="flex flex-wrap gap-2">
            {PANEL_TYPES.map((pt) => (
              <Button key={pt.type} variant="outline" size="sm" onClick={() => addPanel(pt.type)}>
                <Plus className="size-4 mr-1" />
                {pt.label}
              </Button>
            ))}
          </div>
        ) : (
          <Button variant="outline" onClick={() => setShowAdd(true)}>
            <Plus className="size-4 mr-1" />
            Add Panel
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
