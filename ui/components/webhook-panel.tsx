"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Webhook, Plus, Trash2, TestTube } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

async function getWebhooks() {
  const response = await fetch("/api/webhooks", { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed: ${response.status}`);
  return response.json();
}

async function addWebhook(config: any) {
  const response = await fetch("/api/webhooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error(`Failed: ${response.status}`);
  return response.json();
}

async function testWebhook(hookId: string) {
  const response = await fetch(`/api/webhooks/test/${hookId}`, { method: "POST" });
  if (!response.ok) throw new Error(`Failed: ${response.status}`);
  return response.json();
}

export function WebhookPanel() {
  const [url, setUrl] = useState("");
  const queryClient = useQueryClient();
  const webhooks = useQuery({ queryKey: ["webhooks"], queryFn: getWebhooks });
  const add = useMutation({
    mutationFn: addWebhook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      setUrl("");
    },
  });

  const hooks = webhooks.data?.webhooks ?? {};

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Webhook className="size-4 text-accent" />
          Webhooks
        </CardTitle>
        <CardDescription className="text-text-secondary">Outbound notifications for alarms and anomalies</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="flex items-center gap-2">
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/webhook"
            className="flex-1"
          />
          <Button onClick={() => add.mutate({ url, events: ["alarm", "anomaly"] })} disabled={!url || add.isPending}>
            <Plus className="size-4" />
            Add
          </Button>
        </div>

        <div className="space-y-2">
          {Object.entries(hooks).map(([id, config]: [string, any]) => (
            <div key={id} className="flex items-center justify-between rounded-lg border border-border-subtle p-3">
              <div className="space-y-1">
                <p className="font-mono text-xs text-text-primary truncate max-w-[200px]">{config.url}</p>
                <div className="flex gap-1">
                  {config.events?.map((e: string) => (
                    <Badge key={e} variant="outline" className="text-[10px]">{e}</Badge>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" onClick={() => testWebhook(id)}>
                  <TestTube className="size-4" />
                </Button>
                <Button variant="ghost" size="sm" className="text-error">
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </div>
          ))}
          {Object.keys(hooks).length === 0 && (
            <p className="text-sm text-text-secondary">No webhooks configured yet.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
