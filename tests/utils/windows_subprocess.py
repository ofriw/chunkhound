"""Windows-compatible subprocess utilities for tests."""

import asyncio
import platform
import os
from typing import Dict, Optional, Any


async def create_subprocess_exec_safe(
    *args: str,
    stdin: Optional[Any] = None,
    stdout: Optional[Any] = None,
    stderr: Optional[Any] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    **kwargs: Any
) -> asyncio.subprocess.Process:
    """Create subprocess with Windows-safe encoding settings.
    
    This function ensures proper UTF-8 encoding for subprocess communication
    on Windows, preventing Unicode encoding errors that break JSON-RPC protocols.
    """
    # Set up environment with UTF-8 encoding for Windows compatibility
    if env is None:
        env = os.environ.copy()
    else:
        env = env.copy()
    
    if platform.system() == "Windows":
        # Force UTF-8 encoding for subprocess I/O
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONLEGACYWINDOWSSTDIO"] = "1"
        # Disable Unicode console output that causes encoding issues
        env["PYTHONUTF8"] = "1"
    
    return await asyncio.create_subprocess_exec(
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=env,
        cwd=cwd,
        **kwargs
    )


def get_safe_subprocess_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Get environment variables with Windows-safe encoding settings."""
    if base_env is None:
        env = os.environ.copy()
    else:
        env = base_env.copy()
    
    if platform.system() == "Windows":
        # Force UTF-8 encoding for subprocess I/O
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONLEGACYWINDOWSSTDIO"] = "1"
        env["PYTHONUTF8"] = "1"
    
    return env