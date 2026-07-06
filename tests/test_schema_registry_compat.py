from __future__ import annotations

import pytest

from services.common.schema_registry import (
    BACKWARD,
    FORWARD,
    FULL,
    NONE,
    IncompatibleSchemaError,
    SchemaRegistry,
)


def _fields(*pairs):
    """Build a field list from (name, type, required) tuples."""
    return [
        {"name": name, "type": ftype, "required": req}
        for name, ftype, req in pairs
    ]


def test_backward_allows_adding_optional_field():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    sv = reg.register("s1", _fields(("a", "string", True), ("b", "string", False)))
    assert sv.version == 2
    assert reg.list_schemas()[0]["compatibility"] == BACKWARD


def test_backward_rejects_removing_required_field():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True), ("b", "string", True)), enforce=False)
    with pytest.raises(IncompatibleSchemaError):
        reg.register("s1", _fields(("a", "string", True)))


def test_backward_rejects_type_change():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    with pytest.raises(IncompatibleSchemaError):
        reg.register("s1", _fields(("a", "int", True)))


def test_backward_rejects_optional_becoming_required():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True), ("b", "string", False)), enforce=False)
    with pytest.raises(IncompatibleSchemaError):
        reg.register("s1", _fields(("a", "string", True), ("b", "string", True)))


def test_forward_rejects_adding_required_field():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    reg.set_compatibility("s1", FORWARD)
    with pytest.raises(IncompatibleSchemaError):
        reg.register("s1", _fields(("a", "string", True), ("c", "int", True)))


def test_forward_allows_adding_optional_field():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    reg.set_compatibility("s1", FORWARD)
    sv = reg.register("s1", _fields(("a", "string", True), ("c", "int", False)))
    assert sv.version == 2


def test_full_rejects_both_backward_and_forward_violations():
    reg = SchemaRegistry()
    reg.register(
        "s1",
        _fields(("a", "string", True), ("b", "string", True)),
        enforce=False,
    )
    reg.set_compatibility("s1", FULL)
    # Removing required field "b" (backward violation) AND adding required
    # field "c" (forward violation) -> both flagged under FULL.
    with pytest.raises(IncompatibleSchemaError):
        reg.register("s1", _fields(("a", "string", True), ("c", "int", True)))


def test_none_allows_anything():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    reg.set_compatibility("s1", NONE)
    sv = reg.register("s1", _fields(("z", "int", True)))
    assert sv.version == 2


def test_enforce_false_bypasses_compatibility():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    sv = reg.register("s1", _fields(("z", "int", True)), enforce=False)
    assert sv.version == 2


def test_set_compatibility_validates_mode():
    reg = SchemaRegistry()
    with pytest.raises(ValueError):
        reg.set_compatibility("s1", "sideways")


def test_register_per_call_compatibility_override():
    reg = SchemaRegistry()
    reg.register("s1", _fields(("a", "string", True)), enforce=False)
    # Override to NONE just for this registration.
    sv = reg.register(
        "s1",
        _fields(("z", "int", True)),
        compatibility=NONE,
    )
    assert sv.version == 2
    assert reg.get_compatibility("s1") == NONE


def test_list_schemas_includes_compatibility():
    reg = SchemaRegistry()
    reg.register("custom", _fields(("a", "string", True)), enforce=False)
    reg.set_compatibility("custom", FULL)
    schemas = reg.list_schemas()
    custom = next(s for s in schemas if s["schema_id"] == "custom")
    assert custom["compatibility"] == FULL
    assert custom["latest_version"] == 1


def test_default_schemas_bootstrap_without_enforcement():
    """The built-in industrial/processed/benchmark schemas register as v1."""
    reg = SchemaRegistry()
    assert reg.get("industrial_event").version == 1
    assert reg.get("processed_event").version == 1
    assert reg.get("benchmark_event").version == 1
    # A compatible v2 addition is accepted under the default BACKWARD mode.
    sv = reg.register(
        "industrial_event",
        _fields(
            ("event_id", "string", True),
            ("source_protocol", "string", True),
            ("asset_id", "string", True),
            ("tag", "string", True),
            ("value", "float", True),
            ("quality", "string", True),
            ("unit", "string", False),
            ("ts_source", "datetime", True),
            ("site", "string", False),
        ),
    )
    assert sv.version == 2
