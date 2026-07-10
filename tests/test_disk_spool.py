from __future__ import annotations

from services.edge_ingest.disk_spool import DiskEventSpool


def test_disk_spool_round_trip_and_replace(tmp_path):
    spool = DiskEventSpool(tmp_path / "edge-buffer")
    spool.append("industrial.raw", b"key", b"value")
    records = spool.read_all()
    assert spool.decode(records[0]) == ("industrial.raw", b"key", b"value")
    spool.replace([])
    assert spool.read_all() == []
