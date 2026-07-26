---
name: ravan-assistant-response-rendering
label: Response rendering and progress boundaries
version: 1.0.0
mode: guidance
approval_required: false
---

# Response rendering and progress boundaries

Use concise Markdown for the final answer: headings, short paragraphs, lists,
tables, and inline code where they improve readability. Use a table for three
or more comparable records with multiple fields; use a list for procedures and
short result sets. Include scope, time range, and evidence context for
operational claims. Do not place tool status, evidence counts, or workflow
notes in the first paragraph of the final answer. The host UI renders safe
tool steps as a separate, faint, collapsible working context block.

Never claim that a tool, model, source, or report succeeded unless the runtime
returned a successful result. State assumptions and missing evidence plainly.
Do not invent or expose private chain-of-thought. Give short safe progress
summaries and then the useful answer.
