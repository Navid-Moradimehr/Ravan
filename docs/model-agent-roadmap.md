# Model And Agent Roadmap

## Purpose

This roadmap defines how Local Stream Engine should evolve from:

- deterministic industrial streaming and analytics
- plus LLM-based summarization

into a production-grade model platform that also supports:

- retrieval
- embeddings
- specialized industrial ML
- future diagnostic agents
- future supervised action agents

The diagnostic agent and supervised action agent are **not** release features for the open-source platform. The platform should only ship the infrastructure that makes those integrations straightforward for users to add themselves.

## Design Rules

1. The industrial data plane must stay deterministic and usable without any LLM.
2. LLMs must consume processed facts, not raw protocol noise.
3. Specialized models should be used where they are better than LLMs.
4. Future agents must be read-only by default.
5. Action-taking agents must remain a later feature with explicit governance.

## Target Model Stack

### Layer 1: Deterministic Core

Purpose:

- safety, reliability, explainability

Scope:

- rules
- thresholds
- rolling statistics
- z-score / EWMA / ROC
- stuck-sensor and data-quality checks

Status:

- implemented and in active use

### Layer 2: Industrial ML

Purpose:

- anomaly detection
- fault classification
- forecasting
- predictive maintenance

Scope:

- PyOD-based anomaly detectors
- fault classifiers
- forecasting models
- optional ONNX-exportable runtime models later

Status:

- partially implemented

Already present:

- PyOD-capable anomaly detector foundation
- predictive maintenance model training foundation

Still needed:

- model registry and versioning
- training/evaluation pipeline
- promotion criteria
- per-site deployment contract
- offline scoring interfaces for batch validation

### Layer 3: Embeddings And Retrieval

Purpose:

- semantic search across historian records, alarms, reports, manuals, and notes

Scope:

- embedding model config
- chunking/indexing pipeline
- retrieval API
- context assembly for LLM prompts

Status:

- partially implemented as a service boundary

Already present:

- model registry entries for embeddings and retrieval roles
- prompt registry for structured model inputs
- read-only context package endpoint for historian, alarms, assets, reports, and scenarios

Still needed:

- embedding/indexing pipeline
- vector store or equivalent retrieval backend
- chunking strategy for manuals and historical notes
- retrieval evaluation harness

Release requirement:

- keep the boundary stable now
- ship the indexing and retrieval backend incrementally

### Layer 4: LLM Summarization

Purpose:

- operator-facing summaries
- explanation of abnormal batches
- shift/incident narratives

Scope:

- provider-neutral LLM gateway
- batching
- fallback summaries
- strict output shaping

Status:

- implemented and hardened

Already present:

- provider-neutral AI gateway
- OpenAI-compatible and open-weight backend support
- batching
- deterministic fallback
- metrics and benchmarks
- prompt/version registry
- structured response validation

Still needed:

- response schema enforcement beyond prompt discipline
- output validators and retry policy
- prompt/version registry
- retrieval-augmented context path

### Layer 5: Diagnostic Agent With Read-Only Tools

Purpose:

- guided troubleshooting over historian, alarms, metrics, assets, and reports

Scope:

- tool registry
- read-only historian queries
- alert inspection
- asset lookup
- metrics lookup
- report generation hooks

Status:

- infrastructure implemented, agent not shipped

Release requirement:

- build the infrastructure so users can integrate this themselves

Infrastructure that should exist before release:

- stable read-only APIs
- tool-facing schemas for historian/alarm/report queries
- prompt-safe structured outputs
- auditable request/response logging
- per-site model config

Already present:

- read-only tool catalog
- read-only context package assembly endpoint
- model role registry
- prompt registry for future diagnostic agent prompts

### Layer 6: Supervised Action Agents

Purpose:

- ticket creation
- maintenance workflow proposals
- integration with CMMS / external systems

Status:

- explicitly deferred

Release requirement:

- do not ship autonomous action behavior
- only expose extension points, event hooks, and outbound integration APIs

## What Is Already Properly Implemented

These are the model-related features that are meaningfully present now:

- provider-neutral AI gateway
- support for OpenAI-compatible and open-weight model servers
- local-only LLM endpoint restriction support
- deterministic LLM fallback
- AI gateway telemetry and latency metrics
- live LM Studio validation path
- model registry and role-based model config
- prompt/version registry
- structured output validation
- read-only tool schemas for future agents
- read-only context assembly endpoint
- site-profile-aware runtime rollout
- backup/restore and release-gate harness
- deterministic analytics and streaming core
- PyOD anomaly detector foundation
- report generation endpoints

## What Exists But Still Needs Hardening

- trainable anomaly model support
- predictive maintenance model foundation
- report generation
- multi-site rollout scaffolding
- CLI/runtime packaging
- security and user-management foundations

Why these are not "done":

- they exist technically
- but they still need production lifecycle, testing depth, or operational contracts

## What Still Needs To Be Implemented

### For LLM/Model Infrastructure

- embedding indexer and retrieval backend
- retrieval evaluation harness
- per-task model evaluation and promotion workflow
- vector store or equivalent semantic search backend
- per-site model capability matrix and deployment automation

### For Future Agent Infrastructure

- audited tool execution logs
- policy layer for allowed tools per site/user role
- sandbox boundary for future action integrations
- supervised action workflow governance

### For Industrial ML

- forecasting service boundary
- classifier training/evaluation pipeline
- feature store or feature-extraction contract
- per-model deployment metadata
- benchmark datasets and acceptance thresholds

## Release Plan

### Phase A: Open-Source Release Baseline

Must be in release:

- deterministic analytics
- provider-neutral LLM summarization
- fallback behavior
- site profiles
- release gate
- backup/restore drills
- live soak harness
- stable APIs for historian, reports, alarms, and metrics

Should not be in release as first-class product features:

- diagnostic agent
- supervised action agent

### Phase B: Agent-Ready Infrastructure

Add without shipping an agent product:

- retrieval/indexing interfaces
- embedding model config
- read-only tool schemas
- audit trail for model-assisted tool calls
- prompt/template registry

### Phase C: Optional User-Integrated Diagnostic Agents

Users can bring:

- their own model
- their own orchestration layer
- their own tool-calling runtime

The platform should provide:

- stable APIs
- typed responses
- site-local model configuration
- safe read-only integration points

## Industry-Standard Production Gaps

Beyond the model roadmap, these still need improvement for a strong industry-standard platform:

- signed installers and package distribution
- stronger CI/CD and release gates across Windows/Linux
- formal compatibility matrix
- recovery time objectives and restore time measurement
- per-site benchmark baselines
- schema evolution governance
- stronger secrets rotation and deployment docs
- stronger authn/authz implementation if multi-user deployments are expected
- alert noise reduction and operator workflow polish
- deeper historian throughput testing on target topologies
- formal SLOs and incident runbooks

## Recommended Next Implementation Order

1. Add a model registry and role-based model config.
2. Add embedding and retrieval service boundaries.
3. Add response validation and prompt/version registry for the AI gateway.
4. Add read-only tool schemas for future diagnostic agents.
5. Add forecasting and classifier lifecycle support.
6. Only later, add a diagnostic agent feature.
7. Only after that, consider supervised action agents.
