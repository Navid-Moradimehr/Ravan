"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { Archive, Bot, Brain, ChevronRight, History, LoaderCircle, MessageCircle, Mic, Pencil, Plus, RotateCcw, Send, Square, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/help-tip";
import { formatErrorMessage, readResponseError, requestJson } from "@/lib/http";
import { AssistantMarkdown } from "@/components/assistant-markdown";

type AssistantMessage = { message_id: string; role: "user" | "assistant"; content: string; created_at: string; metadata?: Record<string, unknown> };
type AssistantThread = { thread_id: string; title: string; messages: AssistantMessage[]; archived?: boolean; updated_at?: string; created_at?: string };
type ActionPreview = { intent_id: string; action_name: string; target_resource: string; expires_at: string; preview: string; confirmation_token: string; details?: Record<string, unknown> };
type MemoryCandidate = { candidate_id: string; content: string; status: string; created_at: string };
type AssistantModel = { id: string; label?: string; configured?: boolean };
type Questionnaire = { question_id: string; status: string; questions: Array<{ key: string; question: string; type: string; options?: string[]; required?: boolean }>; answers: Record<string, string>; draft?: Record<string, string>; validation_errors?: string[] };

const AssistantDrawer = dynamic(() => Promise.resolve(AssistantDrawerInner), { ssr: false });

function AssistantDrawerInner() {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState<AssistantThread | null>(null);
  const [threads, setThreads] = useState<AssistantThread[]>([]);
  const [threadsLoaded, setThreadsLoaded] = useState(false);
  const [assistantView, setAssistantView] = useState<"chat" | "history" | "memory">("chat");
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);
  const [pendingAction, setPendingAction] = useState<ActionPreview | null>(null);
  const [memories, setMemories] = useState<MemoryCandidate[]>([]);
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});
  const [questionnaireErrors, setQuestionnaireErrors] = useState<string[]>([]);
  const [models, setModels] = useState<AssistantModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [pendingDelete, setPendingDelete] = useState<AssistantThread | null>(null);
  const draftTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  function resizeDraftTextarea() {
    const textarea = draftTextareaRef.current;
    if (!textarea) return;
    const maxHeight = 96;
    textarea.style.height = "auto";
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 48), maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }

  useEffect(() => {
    resizeDraftTextarea();
  }, [draft]);

  async function loadThread(threadId: string) {
    const loaded = await requestJson<AssistantThread>(`/api/assistant/threads/${threadId}`);
    setThread(loaded);
    window.localStorage.setItem("ravan.assistant.thread", threadId);
    const pending = [...loaded.messages].reverse().find((message) => (message.metadata?.questionnaire as Questionnaire | undefined)?.status === "pending")?.metadata?.questionnaire as Questionnaire | undefined;
    setQuestionnaire(pending || null);
    setQuestionAnswers(pending?.answers || {});
    setQuestionnaireErrors(pending?.validation_errors || []);
  }

  async function refreshThreads(selectId?: string) {
    const listed = await requestJson<AssistantThread[]>("/api/assistant/threads?include_archived=true");
    setThreads(listed);
    const active = listed.filter((item) => !item.archived);
    const storedId = window.localStorage.getItem("ravan.assistant.thread");
    const nextId = selectId || (storedId && active.some((item) => item.thread_id === storedId) ? storedId : active[0]?.thread_id);
    if (nextId) await loadThread(nextId);
    else {
      const created = await requestJson<AssistantThread>("/api/assistant/threads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      setThreads([created]);
      setThread(created);
      window.localStorage.setItem("ravan.assistant.thread", created.thread_id);
    }
  }

  useEffect(() => {
    if (!open || threadsLoaded) return;
    setThreadsLoaded(true);
    refreshThreads().catch((reason) => setError(formatErrorMessage(reason, "Assistant could not start")));
  }, [open, threadsLoaded]);

  useEffect(() => {
    if (!open) return;
    requestJson<MemoryCandidate[]>("/api/assistant/memory/candidates")
      .then(setMemories)
      .catch((reason) => setError(formatErrorMessage(reason, "Memory review is unavailable")));
    requestJson<{ models: AssistantModel[]; configured_model?: string }>("/api/assistant/models")
      .then((catalog) => {
        const available = Array.isArray(catalog.models) ? catalog.models : [];
        setModels(available);
        const stored = window.localStorage.getItem("ravan.assistant.model");
        const next = stored && available.some((model) => model.id === stored)
          ? stored
          : catalog.configured_model || available[0]?.id || "";
        setSelectedModel(next);
        if (next) window.localStorage.setItem("ravan.assistant.model", next);
      })
      .catch((reason) => setError(formatErrorMessage(reason, "AI model discovery is unavailable; the configured model will be used")));
  }, [open]);

  async function createNewThread() {
    if (busy) return;
    setError(null);
    try {
      const created = await requestJson<AssistantThread>("/api/assistant/threads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "New conversation" }) });
      setThreads((current) => [created, ...current]);
      setThread(created);
      setQuestionnaire(null);
      setQuestionAnswers({});
      setQuestionnaireErrors([]);
      window.localStorage.setItem("ravan.assistant.thread", created.thread_id);
      setAssistantView("chat");
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not create a new conversation"));
    }
  }

  async function selectThread(item: AssistantThread) {
    if (busy) return;
    setError(null);
    try {
      if (item.archived) {
        await requestJson(`/api/assistant/threads/${item.thread_id}/restore`, { method: "POST" });
      }
      await refreshThreads(item.thread_id);
      setAssistantView("chat");
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not open this conversation"));
    }
  }

  async function archiveThread(item: AssistantThread) {
    if (busy) return;
    setError(null);
    try {
      await requestJson(`/api/assistant/threads/${item.thread_id}`, { method: "DELETE" });
      const remaining = threads.filter((candidate) => candidate.thread_id !== item.thread_id && !candidate.archived);
      setThreads((current) => current.map((candidate) => candidate.thread_id === item.thread_id ? { ...candidate, archived: true } : candidate));
      if (thread?.thread_id === item.thread_id) {
        if (remaining[0]) await loadThread(remaining[0].thread_id);
        else await createNewThread();
      }
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not archive this conversation"));
    }
  }

  async function permanentlyDeleteThread(item: AssistantThread) {
    if (busy || !item.archived) return;
    setError(null);
    try {
      await requestJson(`/api/assistant/threads/${item.thread_id}/permanent`, { method: "DELETE" });
      setThreads((current) => current.filter((candidate) => candidate.thread_id !== item.thread_id));
      setPendingDelete(null);
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not permanently delete this conversation"));
    }
  }

  async function renameThread(item: AssistantThread) {
    const title = titleDraft.trim();
    if (!title || busy) return;
    try {
      const updated = await requestJson<AssistantThread>(`/api/assistant/threads/${item.thread_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
      setThreads((current) => current.map((candidate) => candidate.thread_id === item.thread_id ? { ...candidate, ...updated } : candidate));
      if (thread?.thread_id === item.thread_id) setThread((current) => current ? { ...current, ...updated } : current);
      setEditingThreadId(null);
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not rename this conversation"));
    }
  }

  async function send() {
    if (!thread || !draft.trim() || busy) return;
    setBusy(true);
    setError(null);
    const content = draft.trim();
    setDraft("");
    try {
      const response = await fetch(`/api/assistant/threads/${thread.thread_id}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, context: { route: window.location.pathname, ...(selectedModel ? { model_id: selectedModel } : {}) } }),
      });
      if (!response.ok) throw await readResponseError(response);
      if (!response.body) throw new Error("Assistant stream did not return a readable body");
      const temporaryUser: AssistantMessage = { message_id: `local-user-${Date.now()}`, role: "user", content, created_at: new Date().toISOString() };
      const temporaryAssistant: AssistantMessage = { message_id: `local-assistant-${Date.now()}`, role: "assistant", content: "", created_at: new Date().toISOString(), metadata: { streaming: true } };
      setThread((current) => current ? { ...current, messages: [...current.messages, temporaryUser, temporaryAssistant] } : current);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed: { user_message: AssistantMessage; assistant_message: AssistantMessage; action_preview?: ActionPreview | null; memory_candidate?: MemoryCandidate | null; questionnaire?: Questionnaire | null; thread_title?: string | null } | null = null;
      const applyEvent = (raw: string) => {
        const lines = raw.split("\n");
        const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
        const data = lines.find((line) => line.startsWith("data:"))?.slice(5).trim();
        if (!data) return;
        const payload = JSON.parse(data) as Record<string, unknown>;
        if (eventName === "token" && typeof payload.text === "string") {
          setThread((current) => current ? { ...current, messages: current.messages.map((message) => message.message_id === temporaryAssistant.message_id ? { ...message, content: message.content + payload.text } : message) } : current);
        } else if (eventName === "complete") {
          completed = payload as typeof completed;
        } else if (eventName === "error") {
          throw new Error(String(payload.message || "Assistant stream failed"));
        }
      };
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const records = buffer.split("\n\n");
        buffer = records.pop() || "";
        records.forEach(applyEvent);
        if (done) break;
      }
      if (buffer.trim()) applyEvent(buffer);
      if (!completed) throw new Error("Assistant stream ended before saving the response");
      const finalResponse = completed as { user_message: AssistantMessage; assistant_message: AssistantMessage; action_preview?: ActionPreview | null; memory_candidate?: MemoryCandidate | null; questionnaire?: Questionnaire | null; thread_title?: string | null };
      setThread((current) => current ? { ...current, messages: [...current.messages.filter((message) => message.message_id !== temporaryUser.message_id && message.message_id !== temporaryAssistant.message_id), finalResponse.user_message, finalResponse.assistant_message], updated_at: finalResponse.assistant_message.created_at } : current);
      setThreads((current) => current.map((item) => item.thread_id === thread.thread_id ? { ...item, title: finalResponse.thread_title || item.title, updated_at: finalResponse.assistant_message.created_at } : item));
      if (finalResponse.thread_title) setThread((current) => current ? { ...current, title: finalResponse.thread_title || current.title } : current);
      setPendingAction(finalResponse.action_preview || null);
      if (finalResponse.questionnaire) { setQuestionnaire(finalResponse.questionnaire); setQuestionAnswers(finalResponse.questionnaire.answers || {}); }
      if (finalResponse.memory_candidate) setMemories((current) => [...current, finalResponse.memory_candidate as MemoryCandidate]);
    } catch (reason) {
      setError(formatErrorMessage(reason, "Assistant request failed"));
      setDraft(content);
    } finally {
      setBusy(false);
    }
  }

  async function answerQuestion() {
    if (!thread || !questionnaire || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await requestJson<{ assistant_message: AssistantMessage; questionnaire: Questionnaire; source_draft?: Record<string, string>; validation_errors?: string[] }>(`/api/assistant/threads/${thread.thread_id}/questions/${questionnaire.question_id}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: questionAnswers }),
      });
      setThread((current) => current ? { ...current, messages: [...current.messages, response.assistant_message] } : current);
      setQuestionnaire(response.questionnaire.status === "pending" ? response.questionnaire : null);
      setQuestionAnswers(response.questionnaire.answers || {});
      setQuestionnaireErrors(response.validation_errors || []);
    } catch (reason) {
      setError(formatErrorMessage(reason, "Could not submit source details"));
    } finally {
      setBusy(false);
    }
  }

  async function retryTurn(message: AssistantMessage) {
    const turnId = typeof message.metadata?.turn_id === "string" ? message.metadata.turn_id : "";
    if (!thread || !turnId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await requestJson<{ user_message: AssistantMessage; assistant_message: AssistantMessage }>(`/api/assistant/threads/${thread.thread_id}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ turn_id: turnId, model_id: selectedModel || undefined }),
      });
      setThread((current) => current ? { ...current, messages: [...current.messages, response.user_message, response.assistant_message] } : current);
    } catch (reason) {
      setError(formatErrorMessage(reason, "The assistant turn could not be retried"));
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
          <div className="flex min-w-0 items-center gap-3"><span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-accent/40 bg-accent-subtle text-accent"><Bot className="size-4" aria-hidden="true" /></span><div className="min-w-0"><h2 className="font-heading text-sm font-semibold text-text-primary">Ravan Assistant</h2><div className="mt-1 flex items-center gap-2"><label htmlFor="assistant-model" className="text-[0.68rem] text-text-muted">Model</label><select id="assistant-model" aria-label="Assistant model" value={selectedModel} onChange={(event) => { setSelectedModel(event.target.value); window.localStorage.setItem("ravan.assistant.model", event.target.value); }} className="max-w-[13rem] truncate rounded-md border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[0.68rem] text-text-secondary outline-none focus:border-accent/60" disabled={!selectedModel && models.length === 0}><option value="">Configured model</option>{models.map((model) => <option key={model.id} value={model.id}>{model.label || model.id}</option>)}</select></div></div></div>
          <div className="flex items-center gap-1"><Button size="sm" variant="outline" onClick={() => void createNewThread()} disabled={busy}><Plus className="mr-1.5 size-3.5" />New chat</Button><HelpTip label="Assistant boundary" content="The assistant can inspect Ravan and prepare approved platform changes. It does not control PLCs or actuators. Kafka UI, Grafana, and Prometheus remain guidance-only." side="left" /><Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close assistant"><X className="size-4" /></Button></div>
        </header>
        <nav aria-label="Assistant sections" className="flex gap-1 border-b border-border-subtle bg-surface-2/60 px-3 py-2">
          {([["chat", "Chat", MessageCircle], ["history", "History", History], ["memory", "Memory", Brain]] as const).map(([view, label, Icon]) => <button key={view} type="button" onClick={() => setAssistantView(view)} className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${assistantView === view ? "bg-accent-subtle text-accent" : "text-text-secondary hover:bg-surface-1 hover:text-text-primary"}`} aria-current={assistantView === view ? "page" : undefined}><Icon className="size-3.5" aria-hidden="true" />{label}</button>)}
        </nav>
        {assistantView !== "chat" ? <style>{`aside[aria-label="Ravan Assistant"] > div.border-t { display: none; }`}</style> : null}
          {assistantView === "history" ? <div className="flex-1 space-y-3 overflow-y-auto p-4"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-text-primary">Chat history</p><p className="text-xs text-text-secondary">Resume or organize saved conversations.</p></div><Button size="sm" variant="outline" onClick={() => void createNewThread()} disabled={busy}><Plus className="mr-1.5 size-3.5" />New chat</Button></div><div className="space-y-1">{threads.filter((item) => !item.archived).map((item) => <div key={item.thread_id} className={`group rounded-lg border px-2 py-2 ${thread?.thread_id === item.thread_id ? "border-accent/40 bg-accent-subtle/50" : "border-transparent hover:border-border-subtle hover:bg-surface-1"}`}>{editingThreadId === item.thread_id ? <div className="flex items-center gap-1"><input autoFocus value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void renameThread(item); if (event.key === "Escape") { setEditingThreadId(null); setTitleDraft(""); } }} className="min-w-0 flex-1 rounded border border-border-subtle bg-surface-1 px-2 py-1 text-xs text-text-primary" aria-label="Conversation title" /><Button size="icon" variant="ghost" onClick={() => void renameThread(item)} aria-label="Save conversation title"><Pencil className="size-3" /></Button><Button size="icon" variant="ghost" onClick={() => { setEditingThreadId(null); setTitleDraft(""); }} aria-label="Cancel conversation title edit"><X className="size-3" /></Button></div> : <div className="flex items-center gap-1"><button type="button" onClick={() => void selectThread(item)} className="min-w-0 flex-1 truncate text-left text-xs font-medium text-text-primary">{item.title || "New conversation"}<span className="mt-0.5 block text-[0.65rem] font-normal text-text-muted">{item.messages?.length || 0} messages</span></button><Button size="icon" variant="ghost" onClick={() => { setEditingThreadId(item.thread_id); setTitleDraft(item.title); }} aria-label={`Rename ${item.title}`}><Pencil className="size-3" /></Button><Button size="icon" variant="ghost" onClick={() => void archiveThread(item)} aria-label={`Archive ${item.title}`}><Archive className="size-3" /></Button></div>}</div>)}{threads.filter((item) => item.archived).length > 0 ? <div className="border-t border-border-subtle pt-3"><p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-text-muted">Archived</p>{threads.filter((item) => item.archived).map((item) => <div key={item.thread_id} className="flex items-center gap-1 rounded-lg px-2 py-2 hover:bg-surface-1"><button type="button" onClick={() => void selectThread(item)} className="min-w-0 flex-1 truncate text-left text-xs text-text-secondary">{item.title || "Archived conversation"}<span className="mt-0.5 block text-[0.65rem] text-text-muted">Restore to continue</span></button><Button size="icon" variant="ghost" onClick={() => void selectThread(item)} aria-label={`Restore ${item.title}`}><RotateCcw className="size-3" /></Button><Button size="icon" variant="ghost" onClick={() => setPendingDelete(item)} aria-label={`Delete ${item.title} permanently`}><Trash2 className="size-3 text-destructive" /></Button></div>)}</div> : null}{threads.length === 0 ? <p className="text-xs text-text-muted">No saved conversations yet.</p> : null}</div></div> : null}
        {assistantView === "memory" ? <div className="flex-1 space-y-3 overflow-y-auto p-4"><div><p className="text-sm font-semibold text-text-primary">Assistant memory</p><p className="text-xs text-text-secondary">Approve preferences before they become active context.</p></div>{memories.filter((candidate) => candidate.status === "pending").length === 0 ? <p className="rounded-lg border border-dashed border-border-subtle p-3 text-xs text-text-muted">No pending memory candidates.</p> : memories.filter((candidate) => candidate.status === "pending").map((candidate) => <div key={candidate.candidate_id} className="rounded-lg border border-border-subtle bg-surface-2 p-3"><p className="text-xs leading-5 text-text-secondary">{candidate.content}</p><div className="mt-2 flex gap-2"><Button size="sm" onClick={() => void decideMemory(candidate, "approve")} disabled={memoryBusy}>Approve</Button><Button size="sm" variant="outline" onClick={() => void decideMemory(candidate, "reject")} disabled={memoryBusy}>Reject</Button></div></div>)}</div> : null}
        <div className={`flex-1 space-y-3 overflow-y-auto p-4 ${assistantView !== "chat" ? "hidden" : ""}`}>
          {!thread || thread.messages.length === 0 ? <div className="rounded-xl border border-dashed border-border-subtle bg-surface-2 p-5"><p className="font-heading text-sm font-semibold text-text-primary">What do you need to do?</p><p className="mt-2 text-sm leading-6 text-text-secondary">Ask about a source connection, historian trend, alarm, dataset, report, pipeline state, or the external operator tools.</p><div className="mt-4 flex flex-wrap gap-2">{["Show my sources", "How do I connect an OPC UA PLC?", "Explain the current pipeline"].map((prompt) => <button key={prompt} type="button" onClick={() => setDraft(prompt)} className="rounded-full border border-border-subtle px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent/50 hover:text-accent">{prompt}</button>)}</div></div> : thread.messages.map((message) => <div key={message.message_id} className={message.role === "user" ? "ml-8 rounded-xl bg-accent-subtle p-3 text-sm text-text-primary" : "mr-4 rounded-xl border border-border-subtle bg-surface-2 p-3 text-sm leading-6 text-text-secondary"}>{message.role === "assistant" && Array.isArray(message.metadata?.progress) ? <div className="mb-3 flex items-start gap-2 border-b border-border-subtle/70 pb-2 text-xs italic text-text-muted"><span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-accent/60" aria-hidden="true" /> <div><span className="font-semibold not-italic text-text-secondary">Working context</span>{(message.metadata.progress as string[]).map((entry) => <p key={entry} className="mt-0.5">{entry}</p>)}</div></div> : null}{message.role === "assistant" ? <AssistantMarkdown content={message.content} /> : <p className="whitespace-pre-wrap">{message.content}</p>}{message.role === "assistant" && Array.isArray(message.metadata?.links) ? <div className="mt-3 space-y-1">{(message.metadata?.links as Array<{ href: string; label: string }>).map((link) => <a key={link.href} href={link.href} className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">{link.label}<ChevronRight className="size-3" /></a>)}</div> : null}{message.role === "assistant" && message.metadata?.status === "failed" && message.metadata?.error ? <div className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive"><p>{String((message.metadata.error as { message?: string }).message || "The assistant turn failed.")}</p><Button className="mt-2" size="sm" variant="outline" onClick={() => void retryTurn(message)} disabled={busy}>Retry turn</Button></div> : null}</div>)}
          {pendingAction ? <div className="rounded-xl border border-warning/40 bg-warning/10 p-4"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-warning">Approval required</p><p className="mt-2 font-heading text-sm font-semibold text-text-primary">{pendingAction.preview}</p><p className="mt-2 text-xs leading-5 text-text-secondary">No change has been made. This preview expires at {new Date(pendingAction.expires_at).toLocaleTimeString()}.</p><div className="mt-3 flex gap-2"><Button size="sm" onClick={() => void decideAction("confirm")} disabled={busy}>Confirm change</Button><Button size="sm" variant="outline" onClick={() => void decideAction("reject")} disabled={busy}>Reject</Button></div></div> : null}
          {questionnaire ? <div className="rounded-xl border border-accent/30 bg-accent-subtle/40 p-4"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">Source setup</p><p className="mt-2 text-xs leading-5 text-text-secondary">Answer the missing fields. Ravan will prepare a draft, but will not save credentials or activate ingestion.</p><div className="mt-3 space-y-3">{questionnaire.questions.map((question) => <label key={question.key} className="block"><span className="mb-1 block text-xs font-medium text-text-primary">{question.question}{question.required ? " *" : ""}</span>{question.type === "choice" ? <select value={questionAnswers[question.key] || ""} onChange={(event) => { setQuestionAnswers((current) => ({ ...current, [question.key]: event.target.value })); setQuestionnaireErrors([]); }} className="w-full rounded-lg border border-border-subtle bg-surface-1 px-2 py-2 text-xs text-text-primary"><option value="">Select an option</option>{question.options?.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input value={questionAnswers[question.key] || ""} onChange={(event) => { setQuestionAnswers((current) => ({ ...current, [question.key]: event.target.value })); setQuestionnaireErrors([]); }} className="w-full rounded-lg border border-border-subtle bg-surface-1 px-2 py-2 text-xs text-text-primary" />}</label>)}</div><Button className="mt-4 w-full" size="sm" onClick={() => void answerQuestion()} disabled={busy}>{busy ? "Validating source details…" : "Prepare source draft"}</Button>{questionnaireErrors.length > 0 ? <div role="alert" className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-5 text-destructive"><p className="font-semibold">Source details need correction</p><ul className="mt-1 list-disc space-y-1 pl-4">{questionnaireErrors.map((message) => <li key={message}>{message}</li>)}</ul></div> : null}</div> : null}
          {busy ? <div className="flex items-start gap-2 rounded-lg border border-border-subtle/70 bg-surface-2/60 px-3 py-2 text-xs text-text-muted"><LoaderCircle className="mt-0.5 size-3.5 shrink-0 animate-spin text-accent" /><div><p className="font-semibold text-text-secondary">Working context</p><p className="mt-0.5">Inspecting the request and streaming the answer. Private model reasoning is not exposed.</p></div></div> : null}
          {error ? <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-5 text-destructive">{error}</div> : null}
        </div>
        {pendingDelete ? <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/30 p-5 backdrop-blur-[2px]"><div role="dialog" aria-modal="true" aria-labelledby="delete-chat-title" className="w-full max-w-sm rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-2xl"><p id="delete-chat-title" className="font-heading text-sm font-semibold text-text-primary">Delete archived chat?</p><p className="mt-2 text-sm leading-6 text-text-secondary"><strong className="text-text-primary">{pendingDelete.title || "Archived conversation"}</strong> and all its messages will be permanently removed.</p><div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setPendingDelete(null)}>Cancel</Button><Button variant="destructive" onClick={() => void permanentlyDeleteThread(pendingDelete)} disabled={busy}>Delete permanently</Button></div></div></div> : null}
        <div className="border-t border-border-subtle p-3"><div className="flex items-end gap-2 rounded-xl border border-border-subtle bg-surface-2 p-2"><textarea ref={draftTextareaRef} value={draft} onChange={(event) => { setDraft(event.target.value); resizeDraftTextarea(); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} rows={2} placeholder="Ask Ravan…" className="min-h-12 max-h-24 flex-1 resize-none overflow-y-hidden bg-transparent px-2 py-1 text-sm text-text-primary outline-none placeholder:text-text-muted" aria-label="Message Ravan Assistant" /><div className="flex gap-1"><Button variant="ghost" size="icon" onClick={recording ? () => recorder?.stop() : () => void startRecording()} aria-label={recording ? "Stop recording" : "Start push-to-talk recording"}>{recording ? <Square className="size-4 text-destructive" /> : <Mic className="size-4" />}</Button><Button size="icon" onClick={() => void send()} disabled={!draft.trim() || busy} aria-label="Send message"><Send className="size-4" /></Button></div></div><p className="mt-2 px-1 text-[0.68rem] leading-4 text-text-muted"><MessageCircle className="mr-1 inline size-3" />Enter sends. Shift+Enter adds a line. Voice is push-to-talk and does not retain audio.</p></div>
      </aside> : null}
    </>
  );
}

export { AssistantDrawer };
