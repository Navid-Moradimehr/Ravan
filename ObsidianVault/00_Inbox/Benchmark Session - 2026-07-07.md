# Benchmark Session - 2026-07-07

## Results

- Production pipeline `python-fallback`: 42,041.10 events/sec, p99 0.0549 ms
- Production pipeline `flink-local`: 45,570.07 events/sec, p99 0.0452 ms
- Production pipeline `flink-production`: 49,472.16 events/sec, p99 0.0516 ms
- Site profile matrix `demo-site`: 87,300.50 events/sec, p99 0.0281 ms
- Site profile matrix `plant-a`: 84,941.94 events/sec, p99 0.0291 ms

## Comparison

- `python-fallback` is 9.61 percent above the saved 38,355.18 events/sec baseline, but its p99 is 42.23 percent higher than the prior 0.0386 ms repeatability note.
- `flink-local` is 11.10 percent below the latest recorded 51,261.99 events/sec local baseline, with p99 14.43 percent worse than the prior 0.0395 ms value.
- `flink-production` is 14.38 percent above the 43,251.30 events/sec baseline from the prior production-runtime note, and its p99 improved by 46.25 percent versus the older 0.0960 ms figure.
- `demo-site` is 3.98 percent below the 90,922.74 events/sec site-profile baseline, while p99 is 31.31 percent higher than the prior 0.0214 ms result.
- `plant-a` is 7.49 percent below the 91,818.77 events/sec site-profile baseline, while p99 is 31.67 percent higher than the prior 0.0221 ms result.

## Notes

- All benchmark runs used 10,000 events, 256 batch size, zero warmup, and repeat count 3.
- The site-profile matrix still passed on both manifest profiles.
- `flink-production` showed the widest spread across the three repeats, so the median is the right value to carry forward.
- `uv run` emitted a `bcrypt-5.0.0.dist-info` uninstall warning during the benchmark session, but the benchmark commands still completed successfully.
