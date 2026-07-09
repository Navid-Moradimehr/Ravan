"use client";

import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { Database, Play, Square, Table } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table as UITable, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatErrorMessage, requestJson } from "@/lib/http";
import { showToast } from "@/components/toaster";
import { HelpTip } from "@/components/help-tip";

// Self-Service BI: run ad-hoc SQL, save queries, export CSV
type QueryPayload = {
  sql: string;
  params?: any[];
  query_id: string;
};

async function runQuery(payload: QueryPayload) {
  return requestJson<any[]>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function cancelQuery(queryId: string) {
  return requestJson<{ query_id: string; status: string }>(`/api/query?query_id=${encodeURIComponent(queryId)}`, {
    method: "DELETE",
  });
}

function downloadCsv(rows: any[], filename: string) {
  if (!rows.length) return;
  const columns = Object.keys(rows[0]);
  const csv = [
    columns.join(","),
    ...rows.map((row) =>
      columns.map((col) => {
        const val = row[col];
        const str = typeof val === "object" ? JSON.stringify(val) : String(val ?? "");
        return str.includes(",") ? `"${str.replace(/"/g, '""')}"` : str;
      }).join(",")
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function SqlQueryPanel() {
  const [sql, setSql] = useState("SELECT * FROM industrial_events ORDER BY time DESC LIMIT 10");
  const [savedQueries, setSavedQueries] = useState<string[]>(["SELECT * FROM industrial_events ORDER BY time DESC LIMIT 10"]);
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null);
  const query = useMutation({ mutationFn: (payload: QueryPayload) => runQuery(payload) });
  const cancel = useMutation({ mutationFn: cancelQuery });

  const data = query.data ?? [];
  const columns = data.length ? Object.keys(data[0]) : [];
  const handleRunQuery = useCallback(async () => {
    if (!savedQueries.includes(sql)) {
      setSavedQueries((current) => [...current, sql]);
    }

    const queryId = typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
    setActiveQueryId(queryId);

    try {
      const rows = await query.mutateAsync({ sql, params: [], query_id: queryId });
      showToast({
        title: "Query completed",
        description: `${rows.length} rows returned from the historian.`,
        variant: "success",
      });
    } catch (error) {
      const message = formatErrorMessage(error, "Unable to execute SQL against the historian.");
      showToast({
        title: message.toLowerCase().includes("cancel") ? "Query cancelled" : "Query failed",
        description: message,
        variant: message.toLowerCase().includes("cancel") ? "info" : "error",
      });
    } finally {
      setActiveQueryId(null);
    }
  }, [query, savedQueries, sql]);

  const handleCancelQuery = useCallback(async () => {
    if (!activeQueryId) return;
    try {
      await cancel.mutateAsync(activeQueryId);
      showToast({
        title: "Cancel requested",
        description: "The historian statement was asked to stop on the server.",
        variant: "info",
      });
    } catch (error) {
      showToast({
        title: "Cancel failed",
        description: formatErrorMessage(error, "The running query could not be cancelled."),
        variant: "error",
      });
    }
  }, [activeQueryId, cancel]);

  return (
    <Card className="app-card">
      <CardHeader className="app-card-header">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <Database className="size-4 text-accent" />
              SQL Query
              <HelpTip
                label="SQL Query help"
                content={
                  <span>
                    Read-only historian SQL runs against the platform tables only. Use <span className="font-medium">WHERE</span> and{" "}
                    <span className="font-medium">LIMIT</span> for large datasets. Queries time out on the server, and the cancel button
                    stops the active database statement.
                  </span>
                }
              />
            </CardTitle>
            <CardDescription className="text-text-secondary">
              Run ad-hoc queries against the historian
            </CardDescription>
          </div>
          <Badge variant="outline" className="border-border-subtle bg-surface-2 text-text-secondary">
            Read-only
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {savedQueries.map((q, i) => (
              <button key={i} onClick={() => setSql(q)} className="text-xs rounded-md border border-border-subtle bg-surface-2 px-2 py-1 hover:bg-accent-subtle">
                {q.length > 40 ? q.slice(0, 40) + "..." : q}
              </button>
            ))}
          </div>
          <textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            className="w-full rounded-lg border border-border-subtle bg-surface-2 p-3 font-mono text-sm text-text-primary min-h-[80px]"
            placeholder="SELECT * FROM industrial_events LIMIT 10"
          />
          <p className="text-xs leading-5 text-text-secondary">
            This panel queries historian tables only. Use a time filter and LIMIT for broader scans. The server enforces a timeout
            and you can stop the active query with Cancel.
          </p>
          <div className="flex items-center gap-2">
            <Button onClick={handleRunQuery} disabled={query.isPending} className="inline-flex items-center gap-2">
              <Play className="size-4" />
              {query.isPending ? "Running..." : "Run Query"}
            </Button>
            <Button
              variant="outline"
              onClick={handleCancelQuery}
              disabled={!activeQueryId || !query.isPending || cancel.isPending}
              className="inline-flex items-center gap-2"
            >
              <Square className="size-4" />
              {cancel.isPending ? "Canceling..." : "Cancel"}
            </Button>
            {data.length > 0 && (
              <Button variant="outline" onClick={() => downloadCsv(data, `query_results_${Date.now()}.csv`)} className="inline-flex items-center gap-2">
                <Table className="size-4" />
                Export CSV
              </Button>
            )}
            {query.isError && <Badge variant="outline" className="border-error/30 bg-error/10 text-error">Error</Badge>}
          </div>
          {query.isError ? (
            <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-text-primary">
              {formatErrorMessage(query.error, "The query could not be completed.")}
            </p>
          ) : null}
          {query.isSuccess ? (
            <p className="text-xs text-text-secondary">
              Query output is read-only and is rendered below as rows and columns from the historian result set.
            </p>
          ) : null}
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
