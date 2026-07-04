from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from services.common.semantic_core import OntologyPack, SemanticEntity, SemanticRelationship
from services.common.semantic_store import SemanticLineageRecord, get_semantic_store


@dataclass(frozen=True)
class SemanticStoreWriteBenchmarkResult:
    store_path: str
    iterations: int
    warmup_iterations: int
    elapsed_seconds: float
    writes_per_second: float
    entity_count: int
    relationship_count: int
    lineage_count: int


def run_benchmark(
    store_path: Path,
    *,
    iterations: int = 1_000,
    warmup_iterations: int = 100,
) -> SemanticStoreWriteBenchmarkResult:
    store = get_semantic_store(store_path)

    for idx in range(max(0, warmup_iterations)):
        store.upsert_entity(
            SemanticEntity(
                entity_id=f"warmup/{idx}",
                entity_type="asset",
                name=f"Warmup {idx}",
                labels=("asset",),
                metadata={"site_id": "demo-site"},
            )
        )

    started = time.perf_counter()
    for idx in range(max(1, iterations)):
        entity_id = f"bench/site-01/asset-{idx}"
        relationship_id = f"bench/site-01/asset-{idx}->contains->bench/site-01/tag-{idx}"
        store.upsert_entity(
            SemanticEntity(
                entity_id=entity_id,
                entity_type="asset",
                name=f"Asset {idx}",
                labels=("asset",),
                metadata={"site_id": "demo-site", "iteration": idx},
            )
        )
        store.upsert_relationship(
            SemanticRelationship(
                relationship_id=relationship_id,
                source_id="bench/site-01",
                target_id=entity_id,
                relationship_type="contains",
                metadata={"site_id": "demo-site"},
            )
        )
        store.record_lineage(
            SemanticLineageRecord(
                lineage_id=f"lineage-{idx}",
                kind="semantic_write",
                source_id=entity_id,
                entity_id=entity_id,
                relationship_id=relationship_id,
                site_id="demo-site",
                occurred_at="2026-07-04T00:00:00Z",
                metadata={"iteration": idx},
            )
        )
    elapsed = max(time.perf_counter() - started, 1e-9)
    writes = max(1, iterations) * 3
    snapshot = store.snapshot()
    return SemanticStoreWriteBenchmarkResult(
        store_path=str(store_path),
        iterations=iterations,
        warmup_iterations=warmup_iterations,
        elapsed_seconds=elapsed,
        writes_per_second=writes / elapsed,
        entity_count=len(snapshot["graph"]["entities"]),
        relationship_count=len(snapshot["graph"]["relationships"]),
        lineage_count=len(snapshot["lineage"]),
    )


def format_result(result: SemanticStoreWriteBenchmarkResult) -> str:
    return "\n".join(
        [
            f"store_path={result.store_path}",
            f"iterations={result.iterations}",
            f"warmup_iterations={result.warmup_iterations}",
            f"elapsed_seconds={result.elapsed_seconds}",
            f"writes_per_second={result.writes_per_second}",
            f"entity_count={result.entity_count}",
            f"relationship_count={result.relationship_count}",
            f"lineage_count={result.lineage_count}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark semantic store write throughput.")
    parser.add_argument("--store", type=Path, default=Path("data/semantic/semantic-store.json"))
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--warmup-iterations", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(args.store, iterations=args.iterations, warmup_iterations=args.warmup_iterations)
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
