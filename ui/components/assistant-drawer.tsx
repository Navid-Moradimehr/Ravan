"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Bot, ChevronRight, LoaderCircle, MessageCircle, Mic, Send, Square, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/help-tip";
import { formatErrorMessage, requestJson } from "@/lib/http";

type AssistantMessage = { message_id: string; role: "user" | "assistant"; content: string; created_at: string; metadata?: Record<string, unknown> };
type AssistantThread = { thread_id: string; title: string; messages: AssistantMessage[] };
type ActionPreview = { intent_id: string; action_name: string; target_resource: string; expires_at: string; preview: string; confirmation_token: string; details?: Record<string, unknown> };
type MemoryCandidate = { candidate_id: string; content: string; status: string; created_at: string };

const AssistantDrawer = dynamic(() => Promise.resolve(AssistantDrawerInner), { ssr: false });

function AssistantDrawerInner() {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState<AssistantThread | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);
  const [pendingAction, setPendingAction] = useState<ActionPreview | null>(null);
  const [memories, setMemories] = useState<MemoryCandidate[]>([]);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memoryBusy, setMemoryBusy] = useState(false);

  useEffect(() => {
    if (!open || thread) return;
    requestJson<AssistantThread[]>("/api/assistant/threads")
      .then(async (threads) => {
        if (threads[0]) return setThread(await requestJson<AssistantThread>(`/api/assistant/threads/${threads[0].thread_id}`));
        setThread(await requestJson<AssistantThread>("/api/assistant/threads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) }));
      })
      .catch((reason) => setError(formatErrorMessage(reason, "Assistant could not start")));
  }, [open, thread]);

  useEffect(() => {
    if (!open) return;
    requestJson<MemoryCandidate[]>("/api/assistant/memory/candidates")
      .then(setMemories)
      .catch((reason) => setError(formatErrorMessage(reason, "Memory review is unavailable")));
  }, [open]);

  async function send() {
    if (!thread || !draft.trim() || busy) return;
    setBusy(true);
    setError(null);
    const content = draft.trim();
    setDraft("");
    try {
      const response = await requestJson<{ assistant_message: AssistantMessage; action_preview?: ActionPreview | null; memory_candidate?: MemoryCandidate | null }>(`/api/assistant/threads/${thread.thread_id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, context: { route: window.location.pathname } }),
      });
      setThread((current) => current ? { ...current, messages: [...current.messages, { message_id: `local-${Date.now()}`, role: "user", content, created_at: new Date().toISOString() }, response.assistant_message] } : current);
      setPendingAction(response.action_preview || null);
      if (response.memory_candidate) setMemories((current) => [...current, response.memory_candidate as MemoryCandidate]);
    } catch (reason) {
      setError(formatErrorMessage(reason, "Assistant request failed"));
      setDraft(content);
    } finally {
      setBusy(false);
    }
  }

  function appendAssistantMessage(content: string) {
    setThread((current) => current ? { ...current, messages: [...current.messages, { message_id: `local-${Date.now()}`, role: "assistant", content, created_at: new Date().toISOString() }] } : current);
  }

  async function decideAction(decision: "confirm" | "reject") {
    if (!pendingAction || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await requestJson<{ result?: unknown; status?: string }>(`/api/assistant/actions/${pendingAction.intent_id}/${decision}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(decision === "confirm" ? { confirmation_token: pendingAction.confirmation_token } : {}),
      });
      const label = decision === "confirm" ? "The approved source operation completed." : "The source operation was rejected. No source configuration changed.";
      appendAssistantMessage(response.result ? `${label}\n\n${JSON.stringify(response.result, null, 2)}` : label);
      setPendingAction(null);
    } catch (reason) {
      setError(formatErrorMessage(reason, `Could not ${decision} source operation`));
    } finally {
      setBusy(false);
    }
  }

  async function decideMemory(candidate: MemoryCandidate, decision: "approve" | "reject") {
    setMemoryBusy(true);
    setError(null);
    try {
      const updated = await requestJson<MemoryCandidate>(`/api/assistant/memory/candidates/${candidate.candidate_id}/${decision}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      setMemories((current) => current.map((item) => item.candidate_id === updated.candidate_id ? updated : item));
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not update memory candidate"));
    } finally {
      setMemoryBusy(false);
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser does not provide microphone capture. You can still use text chat.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const nextRecorder = new MediaRecorder(stream);
      nextRecorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      nextRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        setRecorder(null);
        try {
          const audio = new Blob(chunks, { type: nextRecorder.mimeType || "audio/webm" });
          const response = await fetch("/api/assistant/voice/transcribe", { method: "POST", headers: { "Content-Type": audio.type }, body: audio });
          if (!response.ok) {
            const payload = await response.json().catch(() => null) as { detail?: string; error?: string } | null;
            throw new Error(payload?.detail || payload?.error || "Voice transcription failed");
          }
          const payload = await response.json() as { text?: string };
          setDraft((current) => `${current}${current ? " " : ""}${payload.text || ""}`);
          setError(null);
        } catch (reason) {
          setError(formatErrorMessage(reason, "Voice transcription is unavailable"));
        }
      };
      nextRecorder.start();
      setRecorder(nextRecorder);
      setRecording(true);
    } catch (reason) {
      setError(formatErrorMessage(reason, "Microphone permission was not granted"));
    }
  }

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full border border-accent/40 bg-surface-1 px-4 py-3 font-heading text-sm font-semibold text-text-primary shadow-[0_14px_44px_rgba(0,0,0,0.22)] transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" aria-label="Open Ravan Assistant">
        <Bot className="size-4 text-accent" aria-hidden="true" /> Ravan Assistant
      </button>
      {open ? <div className="fixed inset-0 z-50 bg-black/25 backdrop-blur-[2px]" onClick={() => setOpen(false)} aria-hidden="true" /> : null}
      {open ? <aside className="fixed inset-y-0 right-0 z-[51] flex w-full max-w-[min(30rem,100vw)] flex-col border-l border-border-subtle bg-surface-1 shadow-2xl" aria-label="Ravan Assistant">
        <header className="flex items-center justify-between border-b border-border-subtle px-4 py-4">
          <div className="flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-xl border border-accent/40 bg-accent-subtle text-accent"><Bot className="size-4" aria-hidden="true" /></span><div><h2 className="font-heading text-sm font-semibold text-text-primary">Ravan Assistant</h2><p className="text-xs text-text-secondary">Guided operations and diagnostics</p></div></div>
          <div className="flex items-center gap-1"><HelpTip label="Assistant boundary" content="The assistant can inspect Ravan and prepare approved platform changes. It does not control PLCs or actuators. Kafka UI, Grafana, and Prometheus remain guidance-only." side="left" /><Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close assistant"><X className="size-4" /></Button></div>
        </header>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {!thread || thread.messages.length === 0 ? <div className="rounded-xl border border-dashed border-border-subtle bg-surface-2 p-5"><p className="font-heading text-sm font-semibold text-text-primary">What do you need to do?</p><p className="mt-2 text-sm leading-6 text-text-secondary">Ask about a source connection, historian trend, alarm, dataset, report, pipeline state, or the external operator tools.</p><div className="mt-4 flex flex-wrap gap-2">{["Show my sources", "How do I connect an OPC UA PLC?", "Explain the current pipeline"].map((prompt) => <button key={prompt} type="button" onClick={() => setDraft(prompt)} className="rounded-full border border-border-subtle px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent/50 hover:text-accent">{prompt}</button>)}</div></div> : thread.messages.map((message) => <div key={message.message_id} className={message.role === "user" ? "ml-8 rounded-xl bg-accent-subtle p-3 text-sm text-text-primary" : "mr-4 rounded-xl border border-border-subtle bg-surface-2 p-3 text-sm leading-6 text-text-secondary"}><p className="whitespace-pre-wrap">{message.content}</p>{message.role === "assistant" && Array.isArray(message.metadata?.links) ? <div className="mt-3 space-y-1">{(message.metadata?.links as Array<{ href: string; label: string }>).map((link) => <a key={link.href} href={link.href} className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">{link.label}<ChevronRight className="size-3" /></a>)}</div> : null}</div>)}
          {pendingAction ? <div className="rounded-xl border border-warning/40 bg-warning/10 p-4"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-warning">Approval required</p><p className="mt-2 font-heading text-sm font-semibold text-text-primary">{pendingAction.preview}</p><p className="mt-2 text-xs leading-5 text-text-secondary">No change has been made. This preview expires at {new Date(pendingAction.expires_at).toLocaleTimeString()}.</p><div className="mt-3 flex gap-2"><Button size="sm" onClick={() => void decideAction("confirm")} disabled={busy}>Confirm change</Button><Button size="sm" variant="outline" onClick={() => void decideAction("reject")} disabled={busy}>Reject</Button></div></div> : null}
          <div className="rounded-xl border border-border-subtle bg-surface-2 p-3"><button type="button" onClick={() => setMemoryOpen((value) => !value)} className="flex w-full items-center justify-between text-left"><span><span className="block text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">Assistant memory</span><span className="mt-1 block text-xs text-text-secondary">Review preferences before they become active context.</span></span><ChevronRight className={`size-4 text-text-muted transition-transform ${memoryOpen ? "rotate-90" : ""}`} /></button>{memoryOpen ? <div className="mt-3 space-y-2">{memories.filter((candidate) => candidate.status === "pending").length === 0 ? <p className="text-xs text-text-muted">No pending memory candidates.</p> : memories.filter((candidate) => candidate.status === "pending").map((candidate) => <div key={candidate.candidate_id} className="rounded-lg border border-border-subtle bg-surface-1 p-3"><p className="text-xs leading-5 text-text-secondary">{candidate.content}</p><div className="mt-2 flex gap-2"><Button size="sm" onClick={() => void decideMemory(candidate, "approve")} disabled={memoryBusy}>Approve</Button><Button size="sm" variant="outline" onClick={() => void decideMemory(candidate, "reject")} disabled={memoryBusy}>Reject</Button></div></div>)}</div> : null}</div>
          {busy ? <div className="flex items-center gap-2 text-xs text-text-muted"><LoaderCircle className="size-3.5 animate-spin" />Checking Ravan context…</div> : null}
          {error ? <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-5 text-destructive">{error}</div> : null}
        </div>
        <div className="border-t border-border-subtle p-3"><div className="flex items-end gap-2 rounded-xl border border-border-subtle bg-surface-2 p-2"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} rows={2} placeholder="Ask Ravan…" className="min-h-12 flex-1 resize-none bg-transparent px-2 py-1 text-sm text-text-primary outline-none placeholder:text-text-muted" aria-label="Message Ravan Assistant" /><div className="flex gap-1"><Button variant="ghost" size="icon" onClick={recording ? () => recorder?.stop() : () => void startRecording()} aria-label={recording ? "Stop recording" : "Start push-to-talk recording"}>{recording ? <Square className="size-4 text-destructive" /> : <Mic className="size-4" />}</Button><Button size="icon" onClick={() => void send()} disabled={!draft.trim() || busy} aria-label="Send message"><Send className="size-4" /></Button></div></div><p className="mt-2 px-1 text-[0.68rem] leading-4 text-text-muted"><MessageCircle className="mr-1 inline size-3" />Enter sends. Shift+Enter adds a line. Voice is push-to-talk and does not retain audio.</p></div>
      </aside> : null}
    </>
  );
}

export { AssistantDrawer };
