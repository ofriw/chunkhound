import asyncio
import os
from pathlib import Path

import pytest


duckdb = pytest.importorskip("duckdb")


def test_duckdb_as_model_mtime_roundtrip(tmp_path: Path):
    from chunkhound.core.models.file import File
    from chunkhound.core.types.common import Language
    from chunkhound.providers.database.duckdb_provider import DuckDBProvider

    db_path = tmp_path / "db.duckdb"
    provider = DuckDBProvider(db_path, base_directory=tmp_path)
    provider.connect()

    # Create a file and insert as File model (simulating prior index)
    p = tmp_path / "file.txt"
    p.write_text("hello")
    st = p.stat()
    f = File(
        path=(p.relative_to(tmp_path)).as_posix(),
        mtime=float(st.st_mtime),
        language=Language.TEXT,
        size_bytes=int(st.st_size),
    )
    file_id = provider.insert_file(f)
    assert file_id > 0

    # Fetch back as model and verify epoch float mtime (not datetime)
    rec = provider.get_file_by_path(f.path, as_model=True)
    assert rec is not None
    assert isinstance(rec.mtime, float)
    assert abs(rec.mtime - float(st.st_mtime)) < 1e-3


def test_indexing_coordinator_skips_with_duckdb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Heavy but valuable end-to-end check when duckdb is available
    from chunkhound.core.models.file import File
    from chunkhound.core.types.common import Language
    from chunkhound.providers.database.duckdb_provider import DuckDBProvider
    from chunkhound.services.indexing_coordinator import IndexingCoordinator

    db_path = tmp_path / "db.duckdb"
    provider = DuckDBProvider(db_path, base_directory=tmp_path)
    provider.connect()

    # Create files and insert prior state
    files = []
    for i in range(2):
        p = tmp_path / f"f{i}.txt"
        p.write_text("hello")
        st = p.stat()
        f = File(
            path=(p.relative_to(tmp_path)).as_posix(),
            mtime=float(st.st_mtime),
            language=Language.TEXT,
            size_bytes=int(st.st_size),
        )
        provider.insert_file(f)
        files.append(p)

    coord = IndexingCoordinator(database_provider=provider, base_directory=tmp_path)

    # Avoid parsing: record what would be parsed
    called = []

    async def _fake(files, config_file_size_threshold_kb=20, parse_task=None, on_batch=None):
        called.append(list(files))
        return []

    monkeypatch.setattr(coord, "_process_files_in_batches", _fake)

    result = asyncio.run(
        coord.process_directory(
            tmp_path, patterns=["**/*.txt"], exclude_patterns=[], config_file_size_threshold_kb=20
        )
    )

    assert result["files_processed"] == 0
    assert result.get("skipped_unchanged", 0) == 2
    assert called and len(called[0]) == 0

