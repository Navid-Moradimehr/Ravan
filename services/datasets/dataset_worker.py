"""Optional durable worker for model-data bundle builds."""

from __future__ import annotations

import logging
import os
import time

from services.common.dataset_registry import claim_build_job, finish_build_job
from services.common.model_dataset import compile_trajectory_bundle

logger = logging.getLogger(__name__)


def main() -> None:
    worker_id = os.getenv("DATASET_WORKER_ID", "dataset-worker")
    poll_seconds = max(1, int(os.getenv("DATASET_WORKER_POLL_SECONDS", "5")))
    while True:
        job = claim_build_job(worker_id)
        if not job:
            time.sleep(poll_seconds)
            continue
        try:
            compile_trajectory_bundle(job["manifest_path"], job["output_dir"])
            finish_build_job(job["job_id"], "succeeded", output_dir=job["output_dir"])
        except Exception as exc:
            logger.exception("dataset build failed: %s", exc)
            finish_build_job(job["job_id"], "failed", error=str(exc))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
