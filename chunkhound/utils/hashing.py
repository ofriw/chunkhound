import hashlib
from pathlib import Path


def sample_file_hash(path: Path, sample_kb: int = 64) -> str:
    """Compute a fast checksum using a sample from the start and end of the file.

    Args:
        path: File path
        sample_kb: Kilobytes to read from start and end. If 0, hash full file.

    Returns:
        Hex digest string (sha256)
    """
    h = hashlib.sha256()
    size = path.stat().st_size
    if sample_kb <= 0 or size <= sample_kb * 2048:  # small file -> full hash
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    n = sample_kb * 1024
    with path.open('rb') as f:
        head = f.read(n)
        h.update(head)
        if size > n:
            # Seek near end and read last n bytes
            try:
                f.seek(max(0, size - n))
            except OSError:
                pass
            tail = f.read(n)
            h.update(tail)
    # Include file size to reduce collision chance for same-sampled content
    h.update(str(size).encode('utf-8'))
    return h.hexdigest()

