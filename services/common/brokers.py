from __future__ import annotations

import os


def resolve_kafka_brokers(default: str = "localhost:19092") -> str:
    brokers = os.getenv("KAFKA_BROKERS")
    if brokers:
        return brokers
    return default
