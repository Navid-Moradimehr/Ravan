# Postponed Features Matrix

This note mirrors the release-facing postponed-features report.

## Summary

The postponed items are intentionally deferred because they add workflow, orchestration, or enterprise deployment complexity before the core platform contracts are fully mature.

See the source report in `docs/postponed-features.md` for the detailed matrix and revisit triggers.

## AI and Action Governance

The platform should not ship autonomous action agents yet.

What is already worth keeping in the core:

- read-only diagnostic tool contracts
- explicit supervised-action request contracts
- audit logging for agent tool usage and action requests
- governance snapshot visibility over diagnostic and action policies

What should remain user-owned for now:

- actual action approval workflows
- action execution backends
- policy engines
- company-specific action semantics

The right middle ground is to keep tightening the contract and audit boundaries, not to ship autonomous action behavior.

