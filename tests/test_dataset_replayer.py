from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from services.datasets.replayer import map_row_to_event, read_csv_rows


def test_read_csv_rows_reads_header_and_data() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=["asset_id", "tag", "value"])
        writer.writeheader()
        writer.writerow({"asset_id": "Pump-01", "tag": "Temperature", "value": "51.2"})
        writer.writerow({"asset_id": "Pump-02", "tag": "Vibration", "value": "8.8"})
        path = Path(f.name)

    rows = list(read_csv_rows(path))
    assert len(rows) == 2
    assert rows[0]["asset_id"] == "Pump-01"
    assert rows[1]["value"] == "8.8"
    path.unlink()


def test_map_row_to_event_applies_mapping() -> None:
    row = {"asset_id": "Pump-01", "tag": "Temperature", "value": "51.2"}
    mapping = {"asset_id": "asset_id", "tag": "tag", "value": "value"}
    event = map_row_to_event(row, mapping)
    assert event["asset_id"] == "Pump-01"
    assert event["tag"] == "Temperature"
    assert event["value"] == 51.2
    assert event["source_protocol"] == "dataset"


def test_map_row_to_event_handles_bad_numeric() -> None:
    row = {"asset_id": "Pump-01", "tag": "Temperature", "value": "n/a"}
    mapping = {"asset_id": "asset_id", "tag": "tag", "value": "value"}
    event = map_row_to_event(row, mapping)
    assert event["value"] == 0.0


def test_map_row_to_event_parses_metadata_fields() -> None:
    row = {
        "asset_id": "Pump-01",
        "tag": "Temperature",
        "value": "64.2",
        "schema_version": "2",
        "step": "7",
        "ts_source": "2026-06-27T08:00:00Z",
    }
    mapping = {
        "asset_id": "asset_id",
        "tag": "tag",
        "value": "value",
        "schema_version": "schema_version",
        "step": "step",
        "ts_source": "ts_source",
    }
    event = map_row_to_event(row, mapping)
    assert event["value"] == 64.2
    assert event["schema_version"] == 2
    assert event["step"] == 7
    assert event["ts_source"] == "2026-06-27T08:00:00Z"
