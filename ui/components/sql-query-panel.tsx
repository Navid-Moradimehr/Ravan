"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Database, Play, Table } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table as UITable, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

async function runQuery(sql: string, params: any[] = []) {
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, params }),
  });
  if (!response.ok) throw new Error(`Query failed: ${response.status}`);
  return response.json();
}

export function SqlQueryPanel() {
  const [sql, setSql] = useState("SELECT * FROM industrial_events ORDER BY time DESC LIMIT 10");
  const query = useMutation({ mutationFn: (sql: string) => runQuery(sql) });

  const data = query.data ?? [];
  const columns = data.length ? Object.keys(data[0]) : [];

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Database className="size-4 text-accent" />
          SQL Query
        </CardTitle>
        <CardDescription className="text-text-secondary">Run ad-hoc queries against the historian</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="space-y-2">
          <textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            className="w-full rounded-lg border border-border-subtle bg-surface-2 p-3 font-mono text-sm text-text-primary min-h-[80px]"
            placeholder="SELECT * FROM industrial_events LIMIT 10"
          />
          <div className="flex items-center gap-2">
            <Button onClick={() => query.mutate(sql)} disabled={query.isPending} className="inline-flex items-center gap-2">
              <Play className="size-4" />
              {query.isPending ? "Running..." : "Run Query"}
            </Button>
            {query.isError && <Badge variant="outline" className="border-error/30 bg-error/10 text-error">Error</Badge>}
          </div>
        </div>

        {data.length > 0 && (
          <div className="overflow-auto rounded-lg border border-border-subtle">
            <UITable>
              <TableHeader>
                <TableRow className="border-border-subtle hover:bg-transparent">
                  {columns.map((col) => (
                    <TableHead key={col} className="text-text-secondary text-xs">{col}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((row: any, i: number) => (
                  <TableRow key={i} className="border-border-subtle hover:bg-surface-2">
                    {columns.map((col) => (
                      <TableCell key={col} className="font-mono text-xs text-text-primary">
                        {typeof row[col] === "object" ? JSON.stringify(row[col]) : String(row[col] ?? "")}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </UITable>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
