"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Webhook, Plus, Trash2, TestTube } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";
import { HelpTip } from "@/components/help-tip";

async function getWebhooks(): Promise<{ webhooks?: Record<string, any> }> {
  return requestJson<{ webhooks?: Record<string, any> }>("/api/webhooks");
}

async function addWebhook(config: any) {
  return requestJson("/api/webhooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

async function testWebhook(hookId: string) {
  return requestJson(`/api/webhooks/test/${hookId}`, { method: "POST" });
}

async function deleteWebhook(hookId: string) {
  return requestJson(`/api/webhooks/${hookId}`, { method: "DELETE" });
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
      showToast({
        title: "Webhook added",
        description: "The destination is now enabled for alarm and anomaly events.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Webhook failed",
        description: formatErrorMessage(error, "The webhook could not be saved."),
        variant: "error",
      });
    },
  });
  const test = useMutation({
    mutationFn: testWebhook,
    onSuccess: (_, hookId) => {
      showToast({
        title: "Webhook test sent",
        description: `A test payload was delivered to ${hookId}.`,
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Webhook test failed",
        description: formatErrorMessage(error, "The test payload could not be delivered."),
        variant: "error",
      });
    },
  });
  const remove = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["webhooks"] }); showToast({ title: "Webhook removed", description: "The destination is no longer used by the alert delivery runtime.", variant: "success" }); },
    onError: (error) => showToast({ title: "Webhook removal failed", description: formatErrorMessage(error, "The webhook could not be removed."), variant: "error" }),
  });

  const hooks = webhooks.data?.webhooks ?? {};

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Webhook className="size-4 text-accent" />
          Webhooks
          <HelpTip
            label="Webhooks help"
            content="Add outbound HTTP endpoints here for alarms and anomaly events. The destination belongs to the deployment operator, not to the platform core."
          />
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

        {webhooks.isError ? (
          <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-text-primary">
            {formatErrorMessage(webhooks.error, "Webhook definitions could not be loaded.")}
          </p>
        ) : null}

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
                <Button variant="ghost" size="sm" onClick={() => test.mutate(id)} disabled={test.isPending}>
                  <TestTube className="size-4" />
                </Button>
                <Button variant="ghost" size="sm" className="text-error" onClick={() => remove.mutate(id)} disabled={remove.isPending}>
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
