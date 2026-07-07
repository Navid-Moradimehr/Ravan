# Postponed Features Matrix

This matrix records the major features that are intentionally postponed for the first open-source release.

## 1. Work-order system

What it does:
- tracks maintenance and production tasks
- assigns owners
- manages statuses and closures

Why postponed:
- it shifts the platform toward MES-like workflow ownership
- the current release only needs alerting, reports, and read-only operational memory

Revisit when:
- users need repeatable maintenance execution across multiple sites
- the platform must coordinate tasks between operators and external systems

## 2. Approval workflow engine

What it does:
- gates changes behind human approval
- supports approvals, rejections, and escalation

Why postponed:
- it is useful, but it adds orchestration overhead before the governance model is fully stable
- the current platform already exposes approval-gated contracts for future integrations

Revisit when:
- supervised action agents become real user requirements
- change-control and exception handling need a persisted workflow layer

## 3. Incident-command subsystem

What it does:
- coordinates incident response and escalation
- captures incident timelines and command actions

Why postponed:
- the platform already has alerts and acknowledgments
- incident command is highly site-specific and needs company-specific process ownership

Revisit when:
- users need a formal incident response process across many facilities

## 4. Maintenance plans

What it does:
- schedules preventive work
- links assets to recurring maintenance activities

Why postponed:
- it depends on work orders and approvals
- maintenance planning is a user-owned operational process, not a platform primitive

Revisit when:
- multiple production sites need shared maintenance orchestration

## 5. Recipe execution state

What it does:
- tracks batch or recipe phases
- models execution progress for manufacturing lines

Why postponed:
- it is strongly manufacturing-specific
- it belongs in domain packs or user-owned process logic, not the universal core

Revisit when:
- a specific industry pack needs shared execution semantics

## 6. Full data catalog

What it does:
- indexes datasets, owners, tags, and lineage across the platform
- supports enterprise discovery and stewardship

Why postponed:
- the current dataset registry is enough for release, benchmark, and restart-safe metadata
- a full catalog is overkill until multiple teams need discovery workflows

Revisit when:
- data discovery and stewardship become a cross-team requirement

## 7. Workflow engine

What it does:
- manages durable orchestration, retries, timers, and human steps

Why postponed:
- it is powerful, but it adds a lot of moving parts
- the platform does not yet need a general orchestration engine in the core

Revisit when:
- several platform subsystems need durable cross-step orchestration

## 8. Policy engine

What it does:
- centralizes decisions for access, approvals, and conditional behavior

Why postponed:
- current release only needs explicit contracts and audit hooks
- policy engines are best added when real policy complexity appears

Revisit when:
- multiple teams need shared authorization or tool-governance logic

## 9. Feature store

What it does:
- versions reusable ML features
- supports training/serving consistency

Why postponed:
- no current evidence of multiple production models sharing features yet
- it is easy to build too early and hard to keep aligned with real model usage

Revisit when:
- at least two production models need the same versioned feature sets

## 10. Graph database backend

What it does:
- stores and traverses relationship-heavy semantic data
- speeds up complex graph traversal queries

Why postponed:
- the current semantic graph and relational backing are enough for the current scope
- graph databases are useful only once traversal becomes a measured bottleneck

Revisit when:
- relationship queries become frequent and slow in the current store

## 11. Digital twin runtime

What it does:
- simulates assets, flows, and state transitions
- supports bidirectional state projection

Why postponed:
- the current semantic layer should remain the source of truth
- runtime simulation is a separate product surface if introduced too early

Revisit when:
- users need live simulation or multiple projection runtimes

## 12. Autonomous action agents

What it does:
- takes actions on behalf of operators or systems

Why postponed:
- action governance is still intentionally conservative
- the platform should ship read-only diagnostic infrastructure first

Revisit when:
- approval workflows, auditing, and exception handling are mature

## 13. Enterprise IAM integration

What it does:
- connects to SSO, directory services, and enterprise identity providers

Why postponed:
- the open-source base should remain easy to self-host first
- identity integration is site-specific and often deployment-specific

Revisit when:
- enterprise deployments need centralized identity and SSO

## 14. Multi-site federation controls

What it does:
- manages cross-site replication, policy, and topology governance

Why postponed:
- the single-node and single-site path must stay simple first
- federation requires stronger operational and governance maturity

Revisit when:
- users begin operating multiple plants or business units with shared controls

## 15. Cluster deployment automation

What it does:
- automates platform rollout across Kubernetes clusters and sites

Why postponed:
- packaging and operator experience should follow stable core contracts
- cluster automation is more valuable after the release story is stable

Revisit when:
- the platform is ready for repeatable enterprise-scale cluster rollouts

## 16. Service mesh

What it does:
- adds mTLS, traffic policy, and service-level routing controls

Why postponed:
- it is overkill for the current single-node and early multi-node deployment model

Revisit when:
- multi-service traffic policy and mTLS become operational requirements

## 17. Multi-region replication

What it does:
- replicates platform state across regions
- enables high-availability failover across geographies

Why postponed:
- this is an enterprise availability problem, not a first-release need
- it introduces complexity far beyond the current release scope

Revisit when:
- business continuity requirements demand regional failover

## 18. Spark runtime

What it does:
- large-scale batch analytics and ML processing

Why postponed:
- the core platform is not intended to ship a heavy batch engine by default
- Spark is better as a user-side or optional integration choice

Revisit when:
- users need large batch jobs that exceed the core runtime path

## 19. Expanded CDC integrations

What it does:
- streams database changes from more upstream systems

Why postponed:
- the Debezium recipe already covers the practical first path
- broader CDC support should follow actual source demand

Revisit when:
- users need several CDC-backed upstreams beyond the current recipe

