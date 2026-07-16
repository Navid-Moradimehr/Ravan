# Model Dataset Manifest v3

## Status

Implemented on 2026-07-16 as a backward-compatible compiler path. Manifest
v1 and v2 remain supported; v3 is the recommended contract for new multi-site
JEPA, Dreamer, MuZero, and offline-control evidence bundles.

## Why

The prior v2 channel key used `entity::tag` and could merge the same asset/tag
from different sites. V3 uses `site_id::entity_id::tag`, requires explicit
episode identity, and prevents row-level train/test leakage by assigning whole
episodes to one split.

## Outputs

V3 emits the existing deterministic bundle files plus `transitions.parquet`.
Transitions reference current/next observations, optional action and outcome
IDs, reward/terminal fields, site, episode, and split. `quality-report.json`
records missing-value masks, split counts, and unlinked operational records.

## Ownership

The platform owns identity validation, alignment, deterministic partitioning,
manifest hashing, and quality gates. Users own episode truth, action meaning,
reward/objective design, source exports, model training, GPUs, and storage
credentials.

## Validation

Focused verification passed: `pytest -q tests/test_model_dataset.py
tests/test_model_dataset_benchmark.py` -> `5 passed`. Soak integration is the
next phase and is not represented by this unit-test result.

[[Deterministic Model Dataset Builder]]
[[Multi-Site World Model Rollout]]
