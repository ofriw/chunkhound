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

# Import Windows-safe subprocess utilities
from tests.utils.windows_subprocess import create_subprocess_exec_safe, get_safe_subprocess_env
from tests.utils.windows_compat import windows_safe_tempdir

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
            ["chunkhound", "search", "--help"],
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
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Find a free port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                free_port = s.getsockname()[1]
            
            proc = await create_subprocess_exec_safe(
                "uv",
                "run",
                "chunkhound",
                "mcp",
                temp_dir,  # Provide temp directory to avoid indexing entire CI workspace
                "--http",
                "--port",
                str(free_port),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=get_safe_subprocess_env({**os.environ, "CHUNKHOUND_MCP_MODE": "1"}),  # Suppress logs
            )

            try:
                # Give server 2 seconds to start or crash with timeout
                await asyncio.wait_for(asyncio.sleep(2), timeout=30.0)

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
                await asyncio.wait_for(proc.wait(), timeout=5.0)

            except asyncio.TimeoutError:
                # Server took too long or cleanup timed out
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass  # Process is dead, ignore

    @pytest.mark.asyncio
    async def test_mcp_http_server_respects_port_argument(self):
        """Test that MCP HTTP server starts on the specified port."""
        import socket
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            # Find a free port for testing
            def find_free_port():
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", 0))
                    return s.getsockname()[1]

            test_port = find_free_port()

            # Start server with specific port
            proc = await create_subprocess_exec_safe(
                "uv",
                "run",
                "chunkhound",
                "mcp",
                temp_dir,  # Provide temp directory to avoid indexing entire CI workspace
                "--http",
                "--host",
                "127.0.0.1",
                "--port",
                str(test_port),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=get_safe_subprocess_env({**os.environ, "CHUNKHOUND_MCP_MODE": "1"}),
            )

            try:
                # Wait for server startup with timeout
                await asyncio.wait_for(asyncio.sleep(3), timeout=30.0)

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

            except asyncio.TimeoutError:
                # Server took too long
                proc.kill()
                pytest.fail("MCP HTTP server startup timed out")
            finally:
                # Clean up
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

    @pytest.mark.asyncio
    async def test_mcp_stdio_server_help(self):
        """Test that MCP stdio server responds to help."""
        proc = await create_subprocess_exec_safe(
            "uv",
            "run",
            "chunkhound",
            "mcp",
            "--stdio",
            "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=get_safe_subprocess_env(),
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
        import json

        # Create a temporary directory to avoid indexing the current directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create minimal config file (required for Config() creation)
            config_path = temp_path / ".chunkhound.json"
            db_path = temp_path / ".chunkhound" / "test.db"
            db_path.parent.mkdir(exist_ok=True)
            
            config = {
                "database": {"path": str(db_path), "provider": "duckdb"},
                "indexing": {"include": ["*.py"]}
            }
            config_path.write_text(json.dumps(config))
            
            # Test that the server starts without crashing
            proc = await create_subprocess_exec_safe(
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
                cwd=temp_dir,  # Run from temp directory that has .chunkhound.json
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

    @pytest.mark.asyncio
    async def test_mcp_stdio_protocol_handshake(self):
        """Test MCP stdio server completes full protocol handshake with tool discovery."""
        import json
        
        with windows_safe_tempdir() as temp_path:
            
            # Create minimal test content (server will auto-index on startup)
            test_file = temp_path / "test.py"
            test_file.write_text("def hello(): return 'world'")
            
            # Create minimal config
            config_path = temp_path / ".chunkhound.json"
            db_path = temp_path / ".chunkhound" / "test.db"
            db_path.parent.mkdir(exist_ok=True)
            
            config = {
                "database": {"path": str(db_path), "provider": "duckdb"},
                "indexing": {"include": ["*.py"]}
            }
            
            # Add embedding config if API key available
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                config["embedding"] = {
                    "provider": "openai",
                    "model": "text-embedding-3-small"
                }
            
            config_path.write_text(json.dumps(config))
            
            # Start MCP server (it will auto-index on startup)
            mcp_env = get_safe_subprocess_env(os.environ)
            mcp_env["CHUNKHOUND_MCP_MODE"] = "1"
            
            proc = await create_subprocess_exec_safe(
                "uv", "run", "chunkhound", "mcp", str(temp_path),
                cwd=str(temp_path),
                env=mcp_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # 1. Send initialize request
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"}
                    }
                }
                
                proc.stdin.write((json.dumps(init_request) + "\n").encode())
                await proc.stdin.drain()
                
                # Read initialize response
                response_line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=10.0
                )
                init_response = json.loads(response_line.decode())
                
                # Verify response structure
                assert "result" in init_response, f"No result in response: {init_response}"
                assert "serverInfo" in init_response["result"], f"No serverInfo in result: {init_response['result']}"
                assert init_response["result"]["serverInfo"]["name"] == "ChunkHound Code Search"
                
                # 2. Send initialized notification
                proc.stdin.write((json.dumps({
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized"
                }) + "\n").encode())
                await proc.stdin.drain()
                
                # 3. Request tool list
                tools_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list"
                }
                
                proc.stdin.write((json.dumps(tools_request) + "\n").encode())
                await proc.stdin.drain()
                
                # Read tools response
                tools_line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=5.0
                )
                tools_response = json.loads(tools_line.decode())
                
                # Verify tools
                assert "result" in tools_response, f"No result in tools response: {tools_response}"
                tools = tools_response["result"].get("tools", [])
                tool_names = [t["name"] for t in tools]
                
                # Should have at least regex search (works without embeddings)
                assert "search_regex" in tool_names, f"search_regex not in tools: {tool_names}"
                assert "get_stats" in tool_names, f"get_stats not in tools: {tool_names}"
                assert "health_check" in tool_names, f"health_check not in tools: {tool_names}"
                
                # Semantic search only if embeddings available
                if api_key:
                    assert "search_semantic" in tool_names, f"search_semantic not in tools: {tool_names}"
                    
            except asyncio.TimeoutError:
                pytest.fail("MCP stdio protocol handshake timed out")
            finally:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()


class TestParserLoading:
    """Test that all parsers can be loaded and created."""

    def test_all_parsers_load(self):
        """Test that all supported language parsers can be created and initialized."""
        from chunkhound.core.types.common import FileId, Language
        from chunkhound.parsers.parser_factory import get_parser_factory
        from chunkhound.parsers.universal_engine import SetupError

        # Minimal valid code samples for smoke testing
        language_samples = {
            Language.PYTHON: "def hello(): pass",
            Language.JAVA: "class Test { }",
            Language.CSHARP: "class Test { }",
            Language.TYPESCRIPT: "const x = 1;",
            Language.JAVASCRIPT: "const x = 1;",
            Language.TSX: "const x = <div>hello</div>;",
            Language.JSX: "const x = <div>hello</div>;",
            Language.GROOVY: "def hello() { }",
            Language.KOTLIN: "fun hello() { }",
            Language.GO: "package main\nfunc main() { }",
            Language.RUST: "fn main() { }",
            Language.BASH: "echo hello",
            Language.MAKEFILE: "all:\n\techo hello",
            Language.C: "int main() { return 0; }",
            Language.CPP: "int main() { return 0; }",
            Language.MATLAB: "function result = hello()\nresult = 1;\nend",
            Language.MARKDOWN: "# Hello\nWorld",
            Language.JSON: '{"hello": "world"}',
            Language.YAML: "hello: world",
            Language.TOML: "hello = 'world'",
            Language.TEXT: "hello world",
            Language.PDF: "hello world",
        }

        factory = get_parser_factory()
        failed_parsers = []
        setup_errors = []

        # Test all languages except UNKNOWN (not a real parser)
        for language in Language:
            if language == Language.UNKNOWN:
                continue

            try:
                parser = factory.create_parser(language)
                assert parser is not None, f"Parser for {language.value} was None"

                # Actually test parsing to trigger tree-sitter Language initialization
                sample_code = language_samples.get(language, "")
                if sample_code:
                    chunks = parser.parse_content(sample_code, f"test.{language.value}", FileId(1))
                    assert isinstance(chunks, list), f"Parser for {language.value} didn't return a list"

            except SetupError as e:
                # SetupError indicates critical issues like version incompatibility
                setup_errors.append((language.value, str(e)))
            except Exception as e:
                failed_parsers.append((language.value, str(e)))

        # SetupErrors should cause immediate test failure (critical issues)
        if setup_errors:
            error_msg = "CRITICAL: Parser setup failures (version incompatibility or missing dependencies):\n"
            for language, error in setup_errors:
                error_msg += f"  - {language}: {error}\n"
            pytest.fail(error_msg)

        # Other failures are also important but less critical
        if failed_parsers:
            error_msg = "Failed to initialize parsers:\n"
            for language, error in failed_parsers:
                error_msg += f"  - {language}: {error}\n"
            pytest.fail(error_msg)


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
