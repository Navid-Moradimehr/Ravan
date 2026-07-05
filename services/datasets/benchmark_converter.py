from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from services.datasets.ai4i_adapter import map_ai4i_row, read_ai4i_rows
from services.edge_ingest.model import utc_now


BENCHMARK_FIELDS: tuple[str, ...] = (
    "event_id",
    "source_protocol",
    "source_id",
    "asset_id",
    "tag",
    "value",
    "quality",
    "unit",
    "site",
    "line",
    "ts_source",
    "schema_version",
    "fault_type",
    "scenario_id",
    "ground_truth_severity",
    "step",
)


@dataclass(frozen=True)
class ConvertResult:
    input_path: str
    output_path: str
    preset: str
    rows_read: int
    events_written: int


def _write_events(output_path: Path, events: Iterable[dict[str, Any]]) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(BENCHMARK_FIELDS))
        writer.writeheader()
        for event in events:
            row = {field: event.get(field, "") for field in BENCHMARK_FIELDS}
            writer.writerow(row)
            count += 1
    return count


def _ai4i_events(rows: list[dict[str, str]], *, site_id: str, line: str, source_prefix: str) -> Iterator[dict[str, Any]]:
    for row in rows:
        machine_id = row.get("Product ID") or f"M-{row.get('UDI', '0')}"
        events = map_ai4i_row(row, machine_id)
        for idx, event in enumerate(events):
            event["site"] = site_id
            event["line"] = line
            event["source_protocol"] = "dataset"
            event["source_id"] = f"{source_prefix}/{machine_id}"
            event["event_id"] = f"{source_prefix}-{machine_id}-{idx}"
            event["scenario_id"] = "ai4i"
            event["fault_type"] = "failure" if row.get("Machine failure", "0") == "1" else "normal"
            event["ground_truth_severity"] = "bad" if row.get("Machine failure", "0") == "1" else "normal"
            event["step"] = idx
            yield event


def _cmapss_events(rows: list[dict[str, str]], *, site_id: str, line: str, source_prefix: str) -> Iterator[dict[str, Any]]:
    sensor_cols = [key for key in rows[0].keys() if key.startswith("s")]
    for row_idx, row in enumerate(rows):
        unit = row.get("unit") or row.get("Unit") or f"unit-{row_idx + 1}"
        cycle = row.get("cycle") or row.get("Cycle") or str(row_idx + 1)
        settings = [row.get(f"setting{i}") or row.get(f"Setting{i}") for i in range(1, 4)]
        degraded = False
        for setting in settings:
            if setting is None:
                continue
            try:
                if float(setting) != 0.0:
                    degraded = True
                    break
            except ValueError:
                continue
        for step_idx, sensor_col in enumerate(sensor_cols, start=1):
            raw_value = row.get(sensor_col, "0")
            try:
                value = float(raw_value)
            except ValueError:
                value = 0.0
            event = {
                "event_id": f"{source_prefix}-{unit}-{cycle}-{sensor_col}",
                "source_protocol": "dataset",
                "source_id": f"{source_prefix}/{unit}",
                "asset_id": unit,
                "tag": sensor_col.upper(),
                "value": value,
                "quality": "good",
                "unit": "normalized",
                "site": site_id,
                "line": line,
                "ts_source": utc_now(),
                "schema_version": 1,
                "fault_type": "degradation" if degraded else "normal",
                "scenario_id": "cmapss",
                "ground_truth_severity": "normal",
                "step": step_idx,
            }
            yield event


def _read_cmapss_rows(input_path: Path) -> list[dict[str, str]]:
    fieldnames = ["unit", "cycle", "setting1", "setting2", "setting3"] + [f"s{i}" for i in range(1, 22)]

    def parse_lines(lines: Iterable[str]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < len(fieldnames):
                continue
            rows.append({fieldnames[idx]: parts[idx] for idx in range(len(fieldnames))})
        return rows

    if zipfile.is_zipfile(input_path):
        rows: list[dict[str, str]] = []
        with zipfile.ZipFile(input_path) as zf:
            for member in zf.namelist():
                lower = member.lower()
                if not lower.endswith((".txt", ".csv")):
                    continue
                if not Path(lower).name.startswith(("train_", "test_")):
                    continue
                with zf.open(member) as src:
                    text = io.TextIOWrapper(src, encoding="utf-8", errors="ignore")
                    rows.extend(parse_lines(text))
        return rows

    with open(input_path, "r", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    if csv_rows:
        return csv_rows

    with open(input_path, "r", encoding="utf-8") as f:
        return parse_lines(f)


def _generic_events(rows: list[dict[str, str]], *, site_id: str, line: str, source_prefix: str) -> Iterator[dict[str, Any]]:
    for row_idx, row in enumerate(rows):
        asset_id = row.get("asset_id") or row.get("asset") or row.get("machine_id") or f"asset-{row_idx + 1}"
        tag = row.get("tag") or row.get("signal") or row.get("name") or "value"
        value_raw = row.get("value") or row.get("reading") or row.get("measurement") or "0"
        try:
            value = float(value_raw)
        except ValueError:
            value = 0.0
        yield {
            "event_id": row.get("event_id") or f"{source_prefix}-{row_idx + 1}",
            "source_protocol": row.get("source_protocol") or "dataset",
            "source_id": row.get("source_id") or f"{source_prefix}/{asset_id}",
            "asset_id": asset_id,
            "tag": tag,
            "value": value,
            "quality": row.get("quality") or "good",
            "unit": row.get("unit") or "",
            "site": row.get("site") or site_id,
            "line": row.get("line") or line,
            "ts_source": row.get("ts_source") or row.get("timestamp") or utc_now(),
            "schema_version": int(row.get("schema_version") or 1),
            "fault_type": row.get("fault_type") or row.get("scenario") or "normal",
            "scenario_id": row.get("scenario_id") or "generic",
            "ground_truth_severity": row.get("ground_truth_severity") or "normal",
            "step": int(row.get("step") or row_idx),
        }


def convert_dataset(
    input_path: Path,
    output_path: Path,
    *,
    preset: str,
    site_id: str = "demo-site",
    line: str = "line-01",
    source_prefix: str = "dataset",
) -> ConvertResult:
    if preset == "ai4i":
        rows = read_ai4i_rows(input_path)
        events = list(_ai4i_events(rows, site_id=site_id, line=line, source_prefix=source_prefix))
        return ConvertResult(str(input_path), str(output_path), preset, len(rows), _write_events(output_path, events))
    if preset == "cmapss":
        rows = _read_cmapss_rows(input_path)
        events = list(_cmapss_events(rows, site_id=site_id, line=line, source_prefix=source_prefix))
        return ConvertResult(str(input_path), str(output_path), preset, len(rows), _write_events(output_path, events))
    if preset == "generic":
        with open(input_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        events = list(_generic_events(rows, site_id=site_id, line=line, source_prefix=source_prefix))
        return ConvertResult(str(input_path), str(output_path), preset, len(rows), _write_events(output_path, events))
    raise ValueError(f"unknown preset: {preset}")
