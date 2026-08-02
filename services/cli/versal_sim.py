"""CLI for deterministic Versal gateway simulation output."""
from __future__ import annotations

import argparse
import json

from services.edge_ingest.versal_simulator import build_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a deterministic Versal gateway run manifest")
    parser.add_argument("--source-id", default="versal-sim-1")
    parser.add_argument("--site-id", default="demo-site")
    parser.add_argument("--run-id", default="versal-sim-1")
    parser.add_argument("--simulator", choices=("gateway", "verilator", "vitis_sw_emu", "vitis_hw_emu", "hardware"), default="gateway")
    args = parser.parse_args()
    print(json.dumps(build_manifest(source_id=args.source_id, site_id=args.site_id, run_id=args.run_id, simulator=args.simulator).model_dump(mode="json"), sort_keys=True))


if __name__ == "__main__":
    main()
