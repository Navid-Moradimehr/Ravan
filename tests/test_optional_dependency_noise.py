from __future__ import annotations

import importlib
import logging


def test_correlation_module_import_is_quiet(caplog):
    from services.analytics import correlation

    caplog.set_level(logging.WARNING)
    importlib.reload(correlation)
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_notifications_module_import_is_quiet(caplog):
    from services.api_service import notifications

    caplog.set_level(logging.WARNING)
    importlib.reload(notifications)
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
