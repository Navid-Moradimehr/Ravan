from __future__ import annotations

import json
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("world_model_soak", Path("scripts/world-model-soak.py"))
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_world_model_soak_artifact_checksum_upload_contract():
    class Client:
        def __init__(self):
            self.put = None

        def head_bucket(self, **_kwargs):
            return {}

        def put_object(self, **kwargs):
            self.put = kwargs

    client = Client()
    digest = _module._upload_artifact(client, "lakehouse", "test.bin", b"world-model")
    assert len(digest) == 64
    assert client.put["Bucket"] == "lakehouse"
