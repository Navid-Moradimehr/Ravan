# Ravan Assistant

Ravan Assistant is the guided operator layer for the platform. It opens from
the lower-right corner on every Ravan page and keeps the current page, site,
asset, tag, and time-range context available while the operator asks questions.
It can explain the platform, inspect bounded operational data, guide source
onboarding, and prepare configuration changes for confirmation.

The assistant is optional. Ravan continues to work without an LLM, speech
provider, or assistant store. When the model gateway is unavailable, the
assistant falls back to deterministic guidance for common source, pipeline,
historian, and help requests.

The drawer has three compact views: Chat for the current conversation, History
for creating, renaming, archiving, restoring, and switching conversations, and
Memory for reviewing pending operator-memory candidates. The message composer
is shown only in Chat so history and memory remain focused.

The Chat header shows the models exposed by the configured AI gateway. The
operator can select a model for subsequent turns; the selection is remembered
in this browser and the selected model ID is sent with each request. The
configured deployment model remains the fallback when discovery is unavailable.
Model selection changes inference routing only. It does not change the
provider endpoint, credentials, safety boundary, or deployment configuration.

Chat requests use a server-sent event stream when the provider supports it.
The drawer shows a bounded working indicator first, then appends response text
as tokens arrive, and finally reconciles the temporary display with the durable
stored message. Provider reasoning traces are not exposed as raw chain of
thought; Ravan shows safe progress status instead. If the stream times out or
returns no content, the assistant records a retryable error and uses
deterministic guidance unless the operator explicitly requested a strict
model-backed turn.

Each chat turn has a durable lifecycle record. Normal provider failures are
reported as degraded model calls while deterministic guidance keeps the
operator moving. If an operator explicitly retries a model-backed turn, Ravan
records the failed turn, exposes its structured error, and retries the
original request through `POST /api/v1/assistant/threads/{thread_id}/retry`.
Retryable failures include provider timeouts and temporary gateway errors;
source actions are never retried automatically.

Configuration actions use a ten-minute confirmation window. If the source,
scope, or values change, the operator must request a new preview. Approvals and
completed actions are written to the platform audit boundary.

## What it can do

The first assistant contract can read source registry state, historian alarms
and recent events, asset hierarchy, semantic relationships, lineage, report
templates, replay scenarios, and governance policy. It can link the operator to
the correct Ravan page and explain how Kafka UI, Grafana, and Prometheus are
used. Those external tools remain guidance-only and are not changed by the
assistant.

Source setup is guided through the same connection registry used by the
Integrations page. The assistant can collect protocol configuration, validate
required fields, explain credential references, and inspect the registered
sources. For an existing uniquely identified source, the commands `test
source <connection-id>`, `enable source <connection-id>`, `disable source
<connection-id>`, `retire source <connection-id>`, and `restore source
<connection-id>` create a ten-minute preview in the drawer. Nothing changes
until the operator clicks `Confirm change`. Ambiguous names are rejected and
the assistant asks for the exact connection ID. The deployment still owns
actual credentials, network reachability, certificates, retention, and
authorization.

To add or edit a source, use the Source connections editor on the Integrations
page. The assistant can guide that workflow, but it does not invent secrets or
silently create a protocol definition. After saving, use the source card's
Validate, Test, and Enable controls, or ask the assistant to prepare the
corresponding typed lifecycle action.

If you ask the assistant to connect or add a source, it opens a guided
questionnaire for protocol, source name, site ID, endpoint, and credential
reference. Answers are persisted with the thread for fifteen minutes and are
validated before Ravan returns a draft. The draft is not saved or enabled; use
the link to Source connections to add mappings and protocol-specific settings,
then Validate and Test it. This is the same missing-information pattern used
by mature agent interfaces, but the final industrial configuration remains a
typed, auditable platform operation.

The assistant can explain digital twins, world-model datasets, JEPA, Dreamer,
MuZero, XGBoost, Flink, Kafka, and historian operation. Ravan provides the
events, metadata, lineage, and dataset contracts; company-specific training,
feature design, model experiments, and actuator control remain user-owned.

If AI Reporting is enabled for the selected site scope, asking the assistant to
generate a scheduled or anomaly report creates a reviewable ten-minute preview.
The report is only queued after confirmation and then appears in the AI
Reporting job history and report detail views. Source creation and editing stay
in the typed Integrations editor because protocol-specific mappings, endpoint
details, and credential references must be complete before a safe preview can
be generated.

## Safety boundary

The assistant never controls PLCs, robots, actuators, safety interlocks, or
closed-loop plant actions. Every future platform configuration action must be a
typed server-side action with missing-field validation, an exact preview,
short-lived confirmation, audit logging, and an explicit result. A model cannot
call arbitrary URLs or execute arbitrary code.

Kafka UI, Grafana, and Prometheus are operator tools outside Ravan's control
plane. The assistant gives step-by-step instructions and opens their links;
operators continue to make changes there manually.

## Memory

Threads are durable per operator. Messages that look like an explicit memory
request, such as `Remember that ...`, create a reviewable memory candidate. A
candidate is not active assistant memory until an operator or administrator
approves it. Open the `Assistant memory` section in the drawer to inspect,
approve, or reject pending candidates. Candidates retain their source thread
for audit. Secrets, raw
telemetry, and raw audio are never assistant memory.

The chat UI follows the same separation used by mature assistant interfaces:
the final answer is rendered as safe Markdown, while bounded tool/evidence
status is shown in a faint **Working context** block above it. This is not raw
model chain-of-thought. It is an auditable summary such as the diagnostic tool
that ran and its result count. The rendering and boundary guidance lives in
`config/assistant-skills/assistant-response-rendering.md` and
`config/assistant-skills/assistant-thinking-boundary.md`.

Conversation continuity is thread-scoped. Each model turn receives a bounded
window of the thread's prior user and assistant messages, plus approved
cross-session memory when relevant. Long conversations are intentionally
trimmed to protect model context limits. Pending source questionnaires are
stored as structured message metadata and are resumed when the operator asks
to answer the earlier questions.

When submitted source details fail validation, the specific errors appear
inside the Source setup panel directly below **Prepare source draft**. Correcting
any field clears the stale error list before the next submission. The chat
composer grows as multiline text is entered up to twice its default height;
longer drafts scroll inside the composer, and sending resets it.

In **History**, the pencil action opens an inline rename editor with Save and
Cancel. Archive is reversible through Restore. Archived conversations also
have **Delete permanently**, which requires an in-app confirmation dialog and removes
the archived thread and its assistant records; active conversations cannot be
permanently deleted through this control.

Use **New chat** in the Chat header to start a separate conversation. After the
first message, Ravan immediately names an untitled thread from a normalized
excerpt of that message. It can then refine the title through the configured AI
gateway in the background, without delaying the answer; if the gateway is
unavailable, the excerpt remains the title. Titles are limited to a short
operator-friendly label and can still be edited manually from History.

Approved memory is supplied as bounded context to future chat requests. It is
not used for plant control, is not a replacement for historian data, and is not
sent to the model until an operator has approved the candidate.

Approved memory can also be queried through the bounded `/api/v1/assistant/memory/search`
endpoint. The default implementation is lexical and file-backed; a future
deployment may replace it with a vector adapter without changing the chat
contract. No vector database is required for the single-node release.

Ravan also loads declarative Markdown skill packs from `config/assistant-skills`.
The baseline source-onboarding and operator-guidance skills are read-only
instructions. They cannot execute code, bypass confirmation, or access secret
values. Deployments can point `RAVAN_ASSISTANT_SKILLS_PATH` at a reviewed skill
directory for company-specific guidance.

Every model-backed turn records which skills were selected. Every diagnostic
tool call also has a durable running, succeeded, or failed record with a stable
error code and retryability. The assistant does not silently turn a failed
diagnostic into a successful claim.

The current single-node implementation uses an atomic file-backed store at
`.datastream/assistant-store.json`. This is deliberately compatible with
Docker Compose and air-gapped installs. A PostgreSQL-backed adapter can be
introduced later without changing the API contracts.

## Voice

Voice capture is push-to-talk. Raw audio is not retained. A deployment must
configure a local speech-to-text adapter through `RAVAN_STT_URL` before voice
transcription becomes active. Without that adapter, the microphone control
reports a clear configuration message and text chat remains available.

The intended local adapter contract is compatible with faster-whisper or an
OpenAI-compatible speech service. TTS is optional and does not affect text
assistant operation. Configure `RAVAN_TTS_URL` to enable the optional
`/api/v1/assistant/voice/synthesize` proxy; the returned audio is streamed to
the caller and is not retained by Ravan.

## User-owned configuration

Users remain responsible for:

- Authentication and authorization integration.
- Credential stores, certificates, and network access.
- LLM, STT, and TTS provider selection and capacity.
- Company-specific skills, prompts, ontologies, and retrieval policy.
- Model training, feature stores, experiment tracking, and deployment.
- Kafka UI, Grafana, Prometheus, and external gateway configuration.

Use the assistant as a guided interface over Ravan's contracts, not as a
replacement for plant safety systems or deployment governance.
