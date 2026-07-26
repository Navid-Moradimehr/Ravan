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

## What it can do

The first assistant contract can read source registry state, historian alarms
and recent events, asset hierarchy, semantic relationships, lineage, report
templates, replay scenarios, and governance policy. It can link the operator to
the correct Ravan page and explain how Kafka UI, Grafana, and Prometheus are
used. Those external tools remain guidance-only and are not changed by the
assistant.

Source setup is guided through the same connection registry used by the
Integrations page. The assistant can collect protocol configuration, validate
required fields, explain credential references, preview supported sources, and
prepare an activation preview. The deployment still owns actual credentials,
network reachability, certificates, retention, and authorization.

The assistant can explain digital twins, world-model datasets, JEPA, Dreamer,
MuZero, XGBoost, Flink, Kafka, and historian operation. Ravan provides the
events, metadata, lineage, and dataset contracts; company-specific training,
feature design, model experiments, and actuator control remain user-owned.

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
approves it. Candidates retain their source thread for audit. Secrets, raw
telemetry, and raw audio are never assistant memory.

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
assistant operation.

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
