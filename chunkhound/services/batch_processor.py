"""Batch file processor for parallel processing across CPU cores.

# FILE_CONTEXT: Worker function for ProcessPoolExecutor to parse files in parallel
# ROLE: Performs CPU-bound read→parse→chunk pipeline independently per batch
# CRITICAL: Must be picklable (top-level function, serializable arguments)
"""

import os
import multiprocessing
from multiprocessing.connection import Connection
from dataclasses import dataclass
from pathlib import Path

from chunkhound.core.types.common import FileId, Language
from chunkhound.parsers.parser_factory import create_parser_for_language


@dataclass
class ParsedFileResult:
    """Result from processing a single file in a batch."""

    file_path: Path
    chunks: list[dict]
    language: Language
    file_size: int
    file_mtime: float
    status: str
    error: str | None = None


def _parse_file_worker(file_path_str: str, language_value: str, conn: Connection) -> None:
    """Child-process worker to parse a single file and send results via pipe.

    Using a dedicated process lets us enforce a strict wall-clock timeout by
    terminating the child when exceeded, without risking stuck threads.
    """
    try:
        # Local imports to keep worker picklable and light
        from pathlib import Path as _Path
        from chunkhound.core.types.common import Language as _Language, FileId as _FileId
        from chunkhound.parsers.parser_factory import create_parser_for_language as _create

        language = _Language.from_string(language_value)
        parser = _create(language)
        if not parser:
            conn.send(("error", f"No parser available for {language}"))
            return

        chunks = parser.parse_file(_Path(file_path_str), _FileId(0))
        chunks_data = [chunk.to_dict() for chunk in chunks]
        conn.send(("ok", chunks_data))
    except Exception as e:  # pragma: no cover - safety net
        try:
            conn.send(("error", str(e)))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _parse_file_with_timeout(
    file_path: Path, language: Language, timeout_s: float
) -> tuple[str, list[dict] | str | None]:
    """Parse a file in a child process with a wall-clock timeout.

    Returns a tuple of (status, payload):
    - ("success", list_of_chunk_dicts)
    - ("error", error_message)
    - ("timeout", None)
    """
    # Use spawn context for safety (works on all platforms)
    # Use spawn for safety; within worker processes this is still safe
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    p = ctx.Process(
        target=_parse_file_worker,
        args=(str(file_path), language.value, child_conn),
        daemon=True,
    )
    p.start()
    # Close our reference to the child side in the parent
    try:
        child_conn.close()
    except Exception:
        pass

    try:
        if parent_conn.poll(timeout_s):
            status, payload = parent_conn.recv()
            # Ensure process exits
            p.join(timeout=0.5)
            if p.is_alive():
                p.terminate()
                p.join(timeout=0.5)
            if status == "ok":
                return ("success", payload)
            else:
                return ("error", payload)
        else:
            # Timeout - terminate the child process cleanly
            p.terminate()
            p.join(timeout=0.5)
            return ("timeout", None)
    finally:
        try:
            parent_conn.close()
        except Exception:
            pass


def process_file_batch(file_paths: list[Path], config_dict: dict) -> list[ParsedFileResult]:
    """Process a batch of files in a worker process.

    This function runs in a separate process via ProcessPoolExecutor.
    Performs the complete read→parse→chunk pipeline for all files in the batch.

    Args:
        file_paths: List of file paths to process in this batch
        config_dict: Serialized configuration dictionary for parser initialization

    Returns:
        List of ParsedFileResult objects with parsed chunks and metadata
    """
    results = []

    # Read timeout config once
    timeout_s = float(config_dict.get("per_file_timeout_seconds", 0.0) or 0.0)
    timeout_min_kb = int(config_dict.get("per_file_timeout_min_size_kb", 128) or 128)

    for file_path in file_paths:
        try:
            # Get file metadata
            file_stat = os.stat(file_path)

            # Detect language from file extension
            language = Language.from_file_extension(file_path)
            if language == Language.UNKNOWN:
                results.append(
                    ParsedFileResult(
                        file_path=file_path,
                        chunks=[],
                        language=language,
                        file_size=file_stat.st_size,
                        file_mtime=file_stat.st_mtime,
                        status="skipped",
                        error="Unknown file type",
                    )
                )
                continue

            # Skip large config/data files (config files are typically < 20KB)
            if language.is_structured_config_language:
                file_size_kb = file_stat.st_size / 1024
                threshold_kb = config_dict.get("config_file_size_threshold_kb", 20)
                if file_size_kb > threshold_kb:
                    results.append(
                        ParsedFileResult(
                            file_path=file_path,
                            chunks=[],
                            language=language,
                            file_size=file_stat.st_size,
                            file_mtime=file_stat.st_mtime,
                            status="skipped",
                            error="large_config_file",
                        )
                    )
                    continue

            # Parse file and generate chunks (with optional per-file timeout)
            if timeout_s > 0 and (file_stat.st_size / 1024) >= timeout_min_kb:
                status, payload = _parse_file_with_timeout(file_path, language, timeout_s)
                if status == "timeout":
                    # Notify immediately as it happens
                    try:
                        print(f"skipping {file_path} due to a timeout", flush=True)
                    except Exception:
                        pass
                    results.append(
                        ParsedFileResult(
                            file_path=file_path,
                            chunks=[],
                            language=language,
                            file_size=file_stat.st_size,
                            file_mtime=file_stat.st_mtime,
                            status="skipped",
                            error="timeout",
                        )
                    )
                    continue
                elif status == "error":
                    results.append(
                        ParsedFileResult(
                            file_path=file_path,
                            chunks=[],
                            language=language,
                            file_size=file_stat.st_size,
                            file_mtime=file_stat.st_mtime,
                            status="error",
                            error=str(payload),
                        )
                    )
                    continue
                else:
                    chunks_data = payload if isinstance(payload, list) else []
            else:
                # No timeout path (original behavior)
                parser = create_parser_for_language(language)
                if not parser:
                    results.append(
                        ParsedFileResult(
                            file_path=file_path,
                            chunks=[],
                            language=language,
                            file_size=file_stat.st_size,
                            file_mtime=file_stat.st_mtime,
                            status="error",
                            error=f"No parser available for {language}",
                        )
                    )
                    continue

                # Note: FileId(0) is placeholder - actual ID assigned during storage
                chunks = parser.parse_file(file_path, FileId(0))
                chunks_data = [chunk.to_dict() for chunk in chunks]

            results.append(
                ParsedFileResult(
                    file_path=file_path,
                    chunks=chunks_data,
                    language=language,
                    file_size=file_stat.st_size,
                    file_mtime=file_stat.st_mtime,
                    status="success",
                )
            )

        except Exception as e:
            # Capture errors but continue processing other files in batch
            results.append(
                ParsedFileResult(
                    file_path=file_path,
                    chunks=[],
                    language=Language.UNKNOWN,
                    file_size=0,
                    file_mtime=0.0,
                    status="error",
                    error=str(e),
                )
            )

    return results
