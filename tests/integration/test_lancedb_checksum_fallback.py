import asyncio
from pathlib import Path

import pytest


lancedb = pytest.importorskip("lancedb")


def test_lancedb_checksum_verify_graceful_fallback(tmp_path: Path, monkeypatch):
    from chunkhound.core.models.file import File
    from chunkhound.core.types.common import Language
    from chunkhound.providers.database.lancedb_provider import LanceDBProvider
    from chunkhound.services.indexing_coordinator import IndexingCoordinator

    db_path = tmp_path / "ldb"
    provider = LanceDBProvider(db_path, base_directory=tmp_path)
    provider.connect()

    # Create file and insert File record (LanceDB has no content_hash column)
    p = tmp_path / "a.txt"
    p.write_text("hello")
    st = p.stat()
    f = File(
        path=(p.relative_to(tmp_path)).as_posix(),
        mtime=float(st.st_mtime),
        language=Language.TEXT,
        size_bytes=int(st.st_size),
    )
    provider.insert_file(f)

    # Configure checksum verify; coordinator should gracefully treat as unsupported and skip unchanged without reprocessing
    class _Cfg:
        class _Indexing:
            cleanup = False
            force_reindex = False
            verify_checksum_when_mtime_equal = True
            checksum_sample_kb = 64
            min_dirs_for_parallel = 4
            max_discovery_workers = 4
            parallel_discovery = False

        indexing = _Indexing()

    coord = IndexingCoordinator(database_provider=provider, base_directory=tmp_path, config=_Cfg())

    called = []

    async def _fake(files, *args, **kwargs):
        # Accept positional args (config_file_size_threshold_kb, parse_task, on_batch)
        called.append(list(files))
        return []

    monkeypatch.setattr(coord, "_process_files_in_batches", _fake)

    res = asyncio.run(
        coord.process_directory(tmp_path, patterns=["**/*.txt"], exclude_patterns=[])
    )
    assert res.get("skipped_unchanged", 0) == 1
    # No parsing attempted
    assert called and len(called[0]) == 0
