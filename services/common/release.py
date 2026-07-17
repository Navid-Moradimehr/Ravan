"""Single release identity shared by runtime services and release tooling."""

from __future__ import annotations

PRODUCT_NAME = "Ravan"
VERSION = "1.0.0-beta.1"
REPOSITORY_URL = "https://github.com/Navid-Moradimehr/Ravan"


def release_metadata() -> dict[str, str]:
    return {
        "product": PRODUCT_NAME,
        "version": VERSION,
        "repository_url": REPOSITORY_URL,
        "license": "Apache-2.0",
    }
