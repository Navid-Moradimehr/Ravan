from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    """Stub psycopg2 so the historian client imports without the native DLL."""
    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("OperationalError", (Exception,), {})
    psycopg_fake.InterfaceError = type("InterfaceError", (Exception,), {})
    psycopg_fake.Error = type("Error", (Exception,), {})
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda obj: obj
    extras_fake.RealDictCursor = type("RealDictCursor", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type(
        "ThreadedConnectionPool", (), {"__init__": lambda *a, **k: None}
    )
    psycopg_fake.extras = extras_fake
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)


def test_defaults_are_production_grade(monkeypatch):
    """Defaults favour exactly-once checkpoints with RocksDB + incremental."""
    from services.processor import iot_anomaly_job as flink_mod

    for var in (
        "FLINK_CHECKPOINT_INTERVAL_MS",
        "FLINK_CHECKPOINT_MODE",
        "FLINK_STATE_BACKEND",
        "FLINK_INCREMENTAL_CHECKPOINTS",
        "FLINK_CHECKPOINT_EXTERNALIZED_CLEANUP",
        "FLINK_CHECKPOINT_UNALIGNED",
    ):
        monkeypatch.delenv(var, raising=False)

    s = flink_mod.checkpoint_settings()
    assert s.interval_ms == 10000
    assert s.mode == "exactly_once"
    assert s.state_backend == "rocksdb"
    assert s.incremental_checkpoints is True
    assert s.externalized_cleanup == "retain"
    assert s.unaligned is False
    assert s.timeout_ms == 600000
    assert s.min_pause_ms == 500
    assert s.max_concurrent == 1


def test_mode_override(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_CHECKPOINT_MODE", "at_least_once")
    s = flink_mod.checkpoint_settings()
    assert s.mode == "at_least_once"


def test_invalid_mode_falls_back_to_exactly_once(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_CHECKPOINT_MODE", "maybe_once")
    s = flink_mod.checkpoint_settings()
    assert s.mode == "exactly_once"


def test_hashmap_backend_disables_incremental_by_default(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_STATE_BACKEND", "hashmap")
    for v in ("FLINK_INCREMENTAL_CHECKPOINTS",):
        monkeypatch.delenv(v, raising=False)
    s = flink_mod.checkpoint_settings()
    assert s.state_backend == "hashmap"
    assert s.incremental_checkpoints is False


def test_rocksdb_incremental_can_be_disabled(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_STATE_BACKEND", "rocksdb")
    monkeypatch.setenv("FLINK_INCREMENTAL_CHECKPOINTS", "false")
    s = flink_mod.checkpoint_settings()
    assert s.incremental_checkpoints is False


def test_invalid_backend_falls_back_to_rocksdb(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_STATE_BACKEND", "memory")
    s = flink_mod.checkpoint_settings()
    assert s.state_backend == "rocksdb"


def test_externalized_cleanup_override(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_CHECKPOINT_EXTERNALIZED_CLEANUP", "delete")
    s = flink_mod.checkpoint_settings()
    assert s.externalized_cleanup == "delete"


def test_unaligned_override(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_CHECKPOINT_UNALIGNED", "true")
    s = flink_mod.checkpoint_settings()
    assert s.unaligned is True


def test_configure_checkpoints_noop_when_interval_zero(monkeypatch):
    """A zero interval disables checkpointing (env explicit opt-out)."""
    from services.processor import iot_anomaly_job as flink_mod

    monkeypatch.setenv("FLINK_CHECKPOINT_INTERVAL_MS", "0")

    calls: list[str] = []

    class FakeCfg:
        def set_checkpoint_timeout(self, v): calls.append("timeout")
        def set_min_pause_between_checkpoints(self, v): calls.append("pause")
        def set_max_concurrent_checkpoints(self, v): calls.append("max")
        def enable_unaligned_checkpoints(self, v): calls.append("unaligned")
        def enable_externalized_checkpoints(self, v): calls.append("ext")

    class FakeEnv:
        def enable_checkpointing(self, *a, **k): calls.append("enabled")
        def get_checkpoint_config(self): return FakeCfg()

    # configure_checkpoints returns early when interval <= 0 without touching env.
    flink_mod.configure_checkpoints(FakeEnv(), flink_mod.checkpoint_settings())
    assert calls == []


def test_configure_checkpoints_applies_exactly_once_settings(monkeypatch):
    """When PyFlink is available the env is configured with the settings."""
    from services.processor import iot_anomaly_job as flink_mod

    # Pretend PyFlink is available by stubbing the modules configure_checkpoints imports.
    chk_mode_mod = types.ModuleType("pyflink.datastream")
    chk_mode_mod.CheckpointConfig = type(
        "CheckpointConfig",
        (),
        {
            "ExternalizedCheckpointCleanup": type(
                "ExternalizedCheckpointCleanup",
                (),
                {"RETAIN_ON_CANCELLATION": "retain", "DELETE_ON_CANCELLATION": "delete"},
            ),
        },
    )
    common_mod = types.ModuleType("pyflink.common")
    common_mod.CheckpointingMode = type(
        "CheckpointingMode", (), {"EXACTLY_ONCE": "eo", "AT_LEAST_ONCE": "alo"}
    )
    rocksdb_mod = types.ModuleType("pyflink.datastream")
    # reuse the existing stub attributes if already present
    if not hasattr(rocksdb_mod, "CheckpointConfig"):
        rocksdb_mod.CheckpointConfig = chk_mode_mod.CheckpointConfig
    rocksdb_mod.RocksDBStateBackend = type("RocksDBStateBackend", (), {"__init__": lambda self: None})

    monkeypatch.setitem(sys.modules, "pyflink.datastream", rocksdb_mod)
    monkeypatch.setitem(sys.modules, "pyflink.common", common_mod)

    monkeypatch.setattr(flink_mod, "PYFLINK_AVAILABLE", True)

    calls: dict[str, object] = {}

    class FakeCfg:
        def set_checkpoint_timeout(self, v): calls["timeout"] = v
        def set_min_pause_between_checkpoints(self, v): calls["pause"] = v
        def set_max_concurrent_checkpoints(self, v): calls["max"] = v
        def enable_unaligned_checkpoints(self, v): calls["unaligned"] = v
        def enable_externalized_checkpoints(self, v): calls["ext"] = v

    class FakeEnv:
        def enable_checkpointing(self, interval, mode):
            calls["enabled"] = (interval, mode)
        def get_checkpoint_config(self):
            return FakeCfg()
        def set_state_backend(self, backend):
            calls["backend"] = type(backend).__name__
        enable_incremental_checkpointing = False

    settings = flink_mod.CheckpointSettings(
        interval_ms=5000,
        mode="exactly_once",
        timeout_ms=120000,
        min_pause_ms=1000,
        max_concurrent=1,
        externalized_cleanup="retain",
        unaligned=False,
        state_backend="rocksdb",
        incremental_checkpoints=True,
    )
    flink_mod.configure_checkpoints(FakeEnv(), settings)
    assert calls["enabled"] == (5000, "eo")
    assert calls["timeout"] == 120000
    assert calls["pause"] == 1000
    assert calls["max"] == 1
    assert calls["unaligned"] is False
    assert calls["ext"] == "retain"
    assert calls["backend"] == "RocksDBStateBackend"
