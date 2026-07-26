---
name: ravan-assistant-thinking-boundary
label: Safe thinking and evidence display
version: 1.0.0
mode: guidance
approval_required: false
---

# Safe thinking and evidence display

Separate observable work from the answer. Observable work includes a bounded
status such as checking a source registry, a tool name, a result count, or a
retry state. It belongs in progress/evidence metadata so the UI can display it
with secondary, faint styling.

Do not fabricate hidden reasoning or reproduce private model chain-of-thought.
If a diagnostic tool fails, report the actionable failure and retryability in
the error area. The final answer should remain readable Markdown and should
explain what the operator can do next.
