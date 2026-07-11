from pathlib import Path


def test_raw_archive_module_is_importable():
    import services.processor.raw_lakehouse_archive as archive

    assert archive.__doc__


def test_compose_keeps_raw_archive_opt_in():
    compose = Path("docker/docker-compose.yml").read_text(encoding="utf-8")
    section = compose.split("  raw-lakehouse-archive:", 1)[1]
    assert "raw-archive" in section
    assert "industrial.raw" in section
