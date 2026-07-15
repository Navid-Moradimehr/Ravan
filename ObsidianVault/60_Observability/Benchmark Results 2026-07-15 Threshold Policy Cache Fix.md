# Benchmark Results 2026-07-15 Threshold Policy Cache Fix

## Why This Exists

The keyed runtime was spending most of its time in threshold-policy resolution when no explicit policy existed for a signal. The empty-policy path did not retain a stable fallback cache entry before loader work, so the benchmark looked like a large regression even though the rolling-window math was already O(1).

## What Changed

- Cached fallback threshold policies are now reused before loader work.
- The explicit-policy loader now keeps a local snapshot instead of recomputing empty results on every event.
- Added regression coverage for the empty-policy cache path.

## Validation

| Check | Result |
|-------|--------|
| `tests/test_threshold_policy.py` | 8 passed |
| runtime contract smoke coverage | 4 passed |
| `tests/test_end_to_end_pipeline_benchmark.py` | passed |
| `benchmark production-pipeline --runtime-mode python-fallback --events 10000 --batch-size 256 --json` | 23,923.03 events/sec, p99 0.0953 ms |
| `benchmark session-repeatability --runtime-mode python-fallback --events 10000 --batch-size 256 --repeat-count 3 --json` | median 25,640.43 events/sec, median p99 0.1027 ms |

## Takeaway

This was a real runtime-path regression, not a benchmark-only issue. The platform now avoids repeated empty threshold-policy reloads and keeps the keyed enrichment contract stable for single-site and multi-site local runs.
