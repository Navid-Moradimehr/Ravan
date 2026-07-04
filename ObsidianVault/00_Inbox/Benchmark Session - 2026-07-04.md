# Benchmark Session - 2026-07-04

## Results

- Real-world simulator average: 53,182.36 events/sec, p99 0.0384 ms
- Production pipeline `python-fallback`: 19,064.00 events/sec, p99 0.0876 ms
- Production pipeline `flink-local`: 17,859.78 events/sec, p99 0.1007 ms
- CGR gap report:
  - `real_world_average`: 56,059.45 events/sec
  - `site_profile_average`: 52,581.54 events/sec
  - `cgr_stream_slice`: 21,403.10 events/sec
  - `flink_runtime_slice`: 22,538.39 events/sec

## Comparison

- The real-world simulator run is 43.04 percent below the prior real-world simulator baseline in `docs/benchmark-results.md`.
- The second run in this session improved the real-world simulator average by 12.41 percent over the first run.
- `flink-local` is 6.32 percent slower than `python-fallback` on this single-node host.
- The benchmark gap is dominated by the local topology and serialization/sink work, not by broker naming or aliasing.
- The exact 2026-07-03 multi-PLC benchmark shape now measures 62,920.94 events/sec, which is 32.61 percent below the earlier 93,370.10 baseline.
- cProfile points to `map_row_to_event`, Pydantic validation, normalization, and JSON serialization as the heaviest cumulative costs in the replay path.

## Notes

- Kafka migration is complete for the current runtime stack.
- The remaining performance gap is a single-node development limitation, not a broker-compatibility issue.
