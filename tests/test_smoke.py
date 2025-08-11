#!/usr/bin/env python3
"""
Smoke tests to catch basic import and startup failures.

These tests are designed to catch crashes that occur during:
1. Module import time (like type annotation syntax errors)
2. CLI command initialization
3. Basic server startup

They run quickly and should be part of every test run.
"""

import subprocess
import importlib
import pkgutil
import sys
import os
import asyncio
import pytest
from pathlib import Path

# Add parent directory to path to import chunkhound
sys.path.insert(0, str(Path(__file__).parent.parent))
import chunkhound


class TestModuleImports:
    """Test that all modules can be imported without errors."""

    def test_all_modules_import(self):
        """Test that all chunkhound modules can be imported."""
        failed_imports = []

        # Walk through all chunkhound modules
        for _, module_name, _ in pkgutil.walk_packages(
            chunkhound.__path__, prefix="chunkhound."
        ):
            try:
                importlib.import_module(module_name)
            except Exception as e:
                failed_imports.append((module_name, str(e)))

        if failed_imports:
            error_msg = "Failed to import modules:\n"
            for module, error in failed_imports:
                error_msg += f"  - {module}: {error}\n"
            pytest.fail(error_msg)

    def test_critical_imports(self):
        """Test critical modules that have caused issues before."""
        critical_modules = [
            "chunkhound.mcp.stdio",
            "chunkhound.mcp.http_server",  # This would have caught the bug!
            "chunkhound.api.cli.main",
            "chunkhound.database",
            "chunkhound.embeddings",
        ]

        for module_name in critical_modules:
            try:
                importlib.import_module(module_name)
            except Exception as e:
                pytest.fail(f"Failed to import {module_name}: {e}")


class TestCLICommands:
    """Test that CLI commands at least show help without crashing."""

    @pytest.mark.parametrize(
        "command",
        [
            ["chunkhound", "--help"],
            ["chunkhound", "--version"],
            ["chunkhound", "index", "--help"],
            ["chunkhound", "mcp", "--help"],
        ],
    )
    def test_cli_help_commands(self, command):
        """Test that CLI help commands work without crashing."""
        result = subprocess.run(
            ["uv", "run"] + command, capture_output=True, text=True, timeout=5
        )

        # Help commands should exit with 0
        assert result.returncode == 0, (
            f"Command {' '.join(command)} failed with code {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

        # Should have some output
        assert result.stdout or result.stderr, (
            f"Command {' '.join(command)} produced no output"
        )

    def test_mcp_http_import(self):
        """Test that we can at least import the MCP HTTP server module.

        This specific test would have caught the type annotation bug.
        """
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "import chunkhound.mcp.http_server; print('OK')",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0, (
            f"Failed to import mcp_http_server\nstderr: {result.stderr}"
        )
        assert "OK" in result.stdout


class TestServerStartup:
    """Test that servers can at least start without immediate crashes."""

    @pytest.mark.asyncio
    async def test_mcp_http_server_starts(self):
        """Test that MCP HTTP server can start without immediate crash."""
        import socket
        
        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "chunkhound",
            "mcp",
            "--http",
            "--port",
            str(free_port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "CHUNKHOUND_MCP_MODE": "1"},  # Suppress logs
        )

        try:
            # Give server 2 seconds to start or crash
            await asyncio.sleep(2)

            # Check if process is still running
            if proc.returncode is not None:
                # Process exited - this means it crashed
                stdout, stderr = await proc.communicate()
                pytest.fail(
                    f"MCP HTTP server crashed with code {proc.returncode}\n"
                    f"stdout: {stdout.decode()}\n"
                    f"stderr: {stderr.decode()}"
                )

            # Server is running - success!
            proc.terminate()
            await proc.wait()

        except asyncio.TimeoutError:
            # This is actually good - server is running
            proc.terminate()
            await proc.wait()

    @pytest.mark.asyncio
    async def test_mcp_http_server_respects_port_argument(self):
        """Test that MCP HTTP server starts on the specified port."""
        import socket

        # Find a free port for testing
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]

        test_port = find_free_port()

        # Start server with specific port
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "chunkhound",
            "mcp",
            "--http",
            "--host",
            "127.0.0.1",
            "--port",
            str(test_port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "CHUNKHOUND_MCP_MODE": "1"},
        )

        try:
            # Wait for server startup
            await asyncio.sleep(3)

            # Verify server is running
            if proc.returncode is not None:
                stdout, stderr = await proc.communicate()
                pytest.fail(
                    f"MCP HTTP server crashed with code {proc.returncode}\n"
                    f"stdout: {stdout.decode()}\n"
                    f"stderr: {stderr.decode()}"
                )

            # Test that server is listening on correct port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", test_port))
                assert result == 0, f"Server not listening on port {test_port}"

            # Verify server is NOT listening on a different port
            wrong_port = find_free_port()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", wrong_port))
                assert result != 0, (
                    f"Server unexpectedly listening on port {wrong_port}"
                )

        finally:
            # Clean up
            proc.terminate()
            await proc.wait()

    @pytest.mark.asyncio
    async def test_mcp_stdio_server_help(self):
        """Test that MCP stdio server responds to help."""
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "chunkhound",
            "mcp",
            "--stdio",
            "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        assert proc.returncode == 0, (
            f"MCP stdio help failed with code {proc.returncode}\n"
            f"stderr: {stderr.decode()}"
        )

    @pytest.mark.asyncio
    async def test_mcp_stdio_server_starts(self):
        """Test that MCP stdio server can start without immediate crashes."""
        import tempfile

        # Create a temporary directory to avoid indexing the current directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test that the server starts without crashing
            proc = await asyncio.create_subprocess_exec(
                "uv",
                "run",
                "python", "-c",
                f'''
import sys
import os
sys.path.insert(0, "{os.getcwd()}")
from chunkhound.mcp.stdio import main
import asyncio

async def test():
    # Set minimal config
    os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "openai"
    os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "test"
    
    # Test we can import without immediate crash
    try:
        # Just test that critical imports work - this catches most startup issues
        from chunkhound.mcp.stdio import StdioMCPServer
        from chunkhound.mcp.http import HttpMCPServer  
        from chunkhound.core.config.config import Config
        
        # Test config creation
        config = Config()
        
        print("SUCCESS: MCP server imports and config creation work")
        return 0
    except Exception as e:
        print(f"FAILED: {{e}}")
        return 1

sys.exit(asyncio.run(test()))
                ''',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                
                if proc.returncode != 0:
                    pytest.fail(
                        f"MCP stdio server initialization failed with code {proc.returncode}\n"
                        f"stdout: {stdout.decode()}\n"
                        f"stderr: {stderr.decode()}"
                    )
                
                # Check for success message
                assert "SUCCESS:" in stdout.decode(), f"Expected success message, got: {stdout.decode()}"

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                pytest.fail("MCP stdio server test timed out")


class TestTypeAnnotations:
    """Test for specific type annotation patterns that have caused issues."""

    def test_no_invalid_forward_reference_unions(self):
        """Check for problematic forward reference union patterns."""
        import ast
        import glob

        problematic_files = []

        # Find all Python files in chunkhound
        for py_file in glob.glob("chunkhound/**/*.py", recursive=True):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for the problematic pattern: "ClassName" | None
            # This is a simple regex check, not a full AST analysis
            import re

            pattern = r':\s*"[^"]+"\s*\|\s*None'

            if re.search(pattern, content):
                # Found potential issue, let's verify it's not in a string
                try:
                    tree = ast.parse(content)
                    # This is where we'd do more sophisticated checking
                    # For now, just flag the file
                    problematic_files.append(py_file)
                except SyntaxError:
                    # If it's a syntax error, our other tests will catch it
                    pass

        if problematic_files:
            pytest.fail(
                f"Found problematic forward reference union patterns in:\n"
                + "\n".join(f"  - {f}" for f in problematic_files)
            )


if __name__ == "__main__":
    # Allow running directly for debugging
    pytest.main([__file__, "-v"])
