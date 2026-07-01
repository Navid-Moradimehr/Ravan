from __future__ import annotations

import math

from services.common.embeddings import EmbeddingClient, EmbeddingConfig


def test_fallback_embedding_is_deterministic_and_normalized():
    client = EmbeddingClient(
        EmbeddingConfig(
            provider="disabled",
            endpoint_url="",
            model_id="text-embedding-nomic-embed-text-v1.5",
            dimensions=64,
            local_only=True,
        )
    )

    vector_a = client.embed_text("motor vibration rising fast")
    vector_b = client.embed_text("motor vibration rising fast")
    vector_c = client.embed_text("pump temperature rising fast")

    assert len(vector_a) == 64
    assert vector_a == vector_b
    assert vector_a != vector_c
    assert math.isclose(sum(value * value for value in vector_a), 1.0, rel_tol=1e-6)
    assert client.backend_info().mode == "deterministic"

