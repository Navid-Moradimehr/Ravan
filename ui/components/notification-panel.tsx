"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Plus, Mail, Slack, MessageSquare, Trash2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

async function getNotifications() {
  const response = await fetch("/api/notifications", { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed: ${response.status}`);
  return response.json();
}

async function addNotification(config: any) {
  const response = await fetch("/api/notifications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error(`Failed: ${response.status}`);
  return response.json();
}

export function NotificationPanel() {
  const [email, setEmail] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [slackUrl, setSlackUrl] = useState("");
  const queryClient = useQueryClient();
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: getNotifications });
  const add = useMutation({
    mutationFn: addNotification,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      setEmail("");
      setWebhookUrl("");
      setSlackUrl("");
    },
  });

  const notifs = notifications.data?.notifications ?? {};

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Bell className="size-4 text-accent" />
          Notifications
        </CardTitle>
        <CardDescription className="text-text-secondary">Alert destinations for alarms and anomalies</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <Tabs defaultValue="email">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="email"><Mail className="size-4 mr-1" />Email</TabsTrigger>
            <TabsTrigger value="webhook"><MessageSquare className="size-4 mr-1" />Webhook</TabsTrigger>
            <TabsTrigger value="slack"><Slack className="size-4 mr-1" />Slack</TabsTrigger>
          </TabsList>
          <TabsContent value="email" className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ops@example.com"
                type="email"
              />
              <Button onClick={() => add.mutate({ email, events: ["alarm", "anomaly"] })} disabled={!email}>
                <Plus className="size-4" />
              </Button>
            </div>
          </TabsContent>
          <TabsContent value="webhook" className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://hooks.example.com/alerts"
              />
              <Button onClick={() => add.mutate({ webhook_url: webhookUrl, events: ["alarm", "anomaly"] })} disabled={!webhookUrl}>
                <Plus className="size-4" />
              </Button>
            </div>
          </TabsContent>
          <TabsContent value="slack" className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={slackUrl}
                onChange={(e) => setSlackUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
              />
              <Button onClick={() => add.mutate({ slack_webhook: slackUrl, events: ["alarm", "anomaly"] })} disabled={!slackUrl}>
                <Plus className="size-4" />
              </Button>
            </div>
          </TabsContent>
        </Tabs>

        <div className="space-y-2">
          {Object.entries(notifs).map(([id, config]: [string, any]) => (
            <div key={id} className="flex items-center justify-between rounded-lg border border-border-subtle p-3">
              <div className="space-y-1">
                <p className="font-mono text-xs text-text-primary">
                  {config.email || config.webhook_url || config.slack_webhook}
                </p>
                <div className="flex gap-1">
                  {config.events?.map((e: string) => (
                    <Badge key={e} variant="outline" className="text-[10px]">{e}</Badge>
                  ))}
                </div>
              </div>
              <Button variant="ghost" size="sm" className="text-error">
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          {Object.keys(notifs).length === 0 && (
            <p className="text-sm text-text-secondary">No notification channels configured.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
