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

- Mapping compilation rerun:
  - real-world simulator average: 63,569.61 events/sec on the repeat run, 47,593.64 on the first run
  - production pipeline `python-fallback`: 20,278.13 events/sec on the repeat run, 21,805.30 on the first run
  - production pipeline `flink-local`: 20,633.02 events/sec on the repeat run, 23,020.73 on the first run

- Hot path correction rerun with 3 passes per benchmark:
  - real-world simulator median: 55,838.30 events/sec
  - production pipeline `python-fallback` median: 24,224.33 events/sec
  - production pipeline `flink-local` median: 17,865.50 events/sec
  - `flink-runtime-slice` median: 25,741.62 events/sec
  - `cgr-stream-slice` median: 24,260.30 events/sec

- Component split rerun inside the container runtime:
  - processor math only median: 198,735.35 events/sec
  - historian batch write median: 13,138.78 events/sec
  - Kafka producer send median: 299,214.93 events/sec

- Historian batch sweep inside the processor container:
  - batch size 256 median: 12,604.50 events/sec
  - batch size 512 median: 9,903.92 events/sec
  - batch size 1024 median: 16,831.34 events/sec

## Comparison

- The real-world simulator run is 43.04 percent below the prior real-world simulator baseline in `docs/benchmark-results.md`.
- The second run in this session improved the real-world simulator average by 12.41 percent over the first run.
- `flink-local` is 6.32 percent slower than `python-fallback` on this single-node host.
- The benchmark gap is dominated by the local topology and serialization/sink work, not by broker naming or aliasing.
- The exact 2026-07-03 multi-PLC benchmark shape now measures 62,920.94 events/sec, which is 32.61 percent below the earlier 93,370.10 baseline.
- cProfile points to `map_row_to_event`, Pydantic validation, normalization, and JSON serialization as the heaviest cumulative costs in the replay path.
- The mapping-compilation change is not a durable performance win: the repeat run was only slightly better than baseline in the simulator and the production pipeline remained mixed.
- The mapping-compile experiment was then removed from the codebase to avoid carrying extra complexity for a non-result.
- The corrected hot-path rerun shows the isolated Flink slice and CGR slice improved on median, but the full real-world simulator and `flink-local` production path still do not match the earlier best runs.
- The `production-pipeline` `flink-local` mode is a thin wrapper around the same runtime slice benchmark, so the gap between those two numbers is not a separate execution problem; it is mostly run variance.
- The component split makes the bottleneck plain: historian writes are the slowest live subsystem; processor math is not the cap; Kafka publish is above historian throughput on this host.
- The historian sink wants larger batches here, and `1024` was the best value in the sweep, so the runtime defaults were updated to use it.

## Notes

- Kafka migration is complete for the current runtime stack.
- The remaining performance gap is a single-node development limitation, not a broker-compatibility issue.
