from services.edge_ingest.connectors.modbus import _decode_registers, _register_count


def test_modbus_register_count_and_float_decoding():
    assert _register_count("float32") == 2
    assert abs(_decode_registers([0x3F80, 0x0000], "float32", "big", "big") - 1.0) < 1e-6


def test_modbus_boolean_and_signed_decoding():
    assert _decode_registers([1], "bool", "big", "big") is True
    assert _decode_registers([0xFFFF], "int16", "big", "big") == -1
