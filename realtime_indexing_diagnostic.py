#!/usr/bin/env python3
"""
Real-time Indexing System Diagnostic Tool
=========================================

This diagnostic tool checks the status and health of the ChunkHound real-time indexing system.
It performs comprehensive checks on:
1. File watcher process status
2. Database connectivity and sync state
3. Environment configuration
4. File change detection capability

Usage: python realtime_indexing_diagnostic.py
"""

import os
import time
import psutil
import tempfile
from pathlib import Path
import subprocess
import sqlite3
import signal
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DiagnosticResult:
    test_name: str
    status: str  # PASS, FAIL, WARNING, ERROR
    message: str
    details: Optional[Dict[str, Any]] = None


class RealTimeIndexingDiagnostic:
    def __init__(self):
        self.results: List[DiagnosticResult] = []
        self.chunkhound_processes: List[Dict[str, Any]] = []
        self.test_dir = Path.cwd()
        self.db_path = self._find_database_path()

    def _find_database_path(self) -> Optional[Path]:
        """Find the ChunkHound database path."""
        # Check common locations
        possible_paths = [
            Path(".chunkhound.db"),
            Path(os.path.expanduser("~/.cache/chunkhound/chunks.duckdb")),
            Path(os.path.expanduser("~/.chunkhound/chunks.duckdb")),
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Check environment variable
        env_path = os.environ.get("CHUNKHOUND_DB_PATH")
        if env_path and Path(env_path).exists():
            return Path(env_path)

        return None

    def _add_result(self, test_name: str, status: str, message: str, details: Optional[Dict] = None):
        """Add a diagnostic result."""
        self.results.append(DiagnosticResult(test_name, status, message, details))

    def check_chunkhound_processes(self) -> DiagnosticResult:
        """Check for running ChunkHound processes."""
        try:
            chunkhound_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'status']):
                try:
                    if proc.info['name'] and 'chunkhound' in proc.info['name'].lower():
                        chunkhound_procs.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': ' '.join(proc.info['cmdline'] or []),
                            'status': proc.info['status'],
                            'running_time': time.time() - proc.info['create_time']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            self.chunkhound_processes = chunkhound_procs

            if not chunkhound_procs:
                self._add_result("Process Check", "FAIL",
                               "No ChunkHound processes found running")
                return self.results[-1]

            # Check for MCP server with file watching
            mcp_with_watch = [p for p in chunkhound_procs
                             if 'mcp' in p['cmdline'] and '--watch' in p['cmdline']]

            if mcp_with_watch:
                proc = mcp_with_watch[0]
                self._add_result("Process Check", "PASS",
                               f"ChunkHound MCP server with file watching found (PID: {proc['pid']})",
                               {"processes": chunkhound_procs})
            else:
                self._add_result("Process Check", "WARNING",
                               "ChunkHound processes found but no MCP server with --watch flag",
                               {"processes": chunkhound_procs})

            return self.results[-1]

        except Exception as e:
            self._add_result("Process Check", "ERROR", f"Failed to check processes: {e}")
            return self.results[-1]

    def check_environment_config(self) -> DiagnosticResult:
        """Check environment configuration for file watching."""
        try:
            config = {
                'CHUNKHOUND_WATCH_ENABLED': os.environ.get('CHUNKHOUND_WATCH_ENABLED', '1'),
                'CHUNKHOUND_WATCH_PATHS': os.environ.get('CHUNKHOUND_WATCH_PATHS', ''),
                'CHUNKHOUND_DB_PATH': os.environ.get('CHUNKHOUND_DB_PATH', ''),
                'OPENAI_API_KEY': 'SET' if os.environ.get('OPENAI_API_KEY') else 'NOT_SET'
            }

            issues = []

            # Check if watching is enabled
            if config['CHUNKHOUND_WATCH_ENABLED'].lower() not in ('1', 'true', 'yes', 'on'):
                issues.append("File watching is disabled via CHUNKHOUND_WATCH_ENABLED")

            # Check watch paths
            if not config['CHUNKHOUND_WATCH_PATHS']:
                config['CHUNKHOUND_WATCH_PATHS'] = f"DEFAULT: {Path.cwd()}"

            if issues:
                self._add_result("Environment Config", "WARNING",
                               f"Configuration issues found: {'; '.join(issues)}",
                               config)
            else:
                self._add_result("Environment Config", "PASS",
                               "Environment configuration looks good", config)

            return self.results[-1]

        except Exception as e:
            self._add_result("Environment Config", "ERROR", f"Failed to check environment: {e}")
            return self.results[-1]

    def check_database_status(self) -> DiagnosticResult:
        """Check database connectivity and basic stats."""
        try:
            if not self.db_path:
                self._add_result("Database Status", "FAIL",
                               "No ChunkHound database found")
                return self.results[-1]

            if not self.db_path.exists():
                self._add_result("Database Status", "FAIL",
                               f"Database file does not exist: {self.db_path}")
                return self.results[-1]

            # Get basic file info
            stat = self.db_path.stat()
            db_info = {
                'path': str(self.db_path),
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'last_modified': time.ctime(stat.st_mtime),
                'age_seconds': time.time() - stat.st_mtime
            }

            # Check if database has been recently updated (sign of active indexing)
            if db_info['age_seconds'] < 300:  # 5 minutes
                status = "PASS"
                message = f"Database recently updated ({int(db_info['age_seconds'])}s ago)"
            elif db_info['age_seconds'] < 3600:  # 1 hour
                status = "WARNING"
                message = f"Database last updated {int(db_info['age_seconds'] / 60)} minutes ago"
            else:
                status = "WARNING"
                message = f"Database last updated {time.ctime(stat.st_mtime)} - may be stale"

            self._add_result("Database Status", status, message, db_info)
            return self.results[-1]

        except Exception as e:
            self._add_result("Database Status", "ERROR", f"Failed to check database: {e}")
            return self.results[-1]

    def check_file_watcher_responsiveness(self) -> DiagnosticResult:
        """Test if file watcher detects new files by creating a test file."""
        try:
            if not self.chunkhound_processes:
                self._add_result("File Watcher Test", "FAIL",
                               "Cannot test - no ChunkHound processes running")
                return self.results[-1]

            # Create a unique test file
            test_content = f"# Real-time indexing test file\n# Created at {time.time()}\n\ndef test_function():\n    return 'test'"
            test_file = self.test_dir / f"diagnostic_test_{int(time.time())}.py"

            # Record initial database modification time
            initial_db_mtime = self.db_path.stat().st_mtime if self.db_path else 0

            # Create the test file
            test_file.write_text(test_content)
            print(f"📝 Created test file: {test_file}")

            # Wait for file watcher to potentially detect and process the file
            print("⏱ Waiting 10 seconds for file watcher to detect changes...")
            time.sleep(10)

            # Check if database was modified
            current_db_mtime = self.db_path.stat().st_mtime if self.db_path else 0
            db_updated = current_db_mtime > initial_db_mtime

            # Clean up test file
            if test_file.exists():
                test_file.unlink()
                print(f"🧹 Cleaned up test file: {test_file}")

            test_details = {
                'test_file': str(test_file),
                'initial_db_mtime': initial_db_mtime,
                'final_db_mtime': current_db_mtime,
                'db_updated': db_updated,
                'time_diff': current_db_mtime - initial_db_mtime
            }

            if db_updated:
                self._add_result("File Watcher Test", "PASS",
                               f"File watcher appears responsive - database updated after test file creation",
                               test_details)
            else:
                self._add_result("File Watcher Test", "FAIL",
                               "File watcher not responsive - database not updated after test file creation",
                               test_details)

            return self.results[-1]

        except Exception as e:
            self._add_result("File Watcher Test", "ERROR", f"Failed to test file watcher: {e}")
            return self.results[-1]

    def check_watchdog_availability(self) -> DiagnosticResult:
        """Check if watchdog library is available."""
        try:
            import watchdog
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            self._add_result("Watchdog Library", "PASS",
                           f"Watchdog library available (version: {watchdog.__version__})")

        except ImportError as e:
            self._add_result("Watchdog Library", "FAIL",
                           f"Watchdog library not available: {e}")
        except Exception as e:
            self._add_result("Watchdog Library", "ERROR",
                           f"Error checking watchdog: {e}")

        return self.results[-1]

    def run_all_diagnostics(self) -> List[DiagnosticResult]:
        """Run all diagnostic checks."""
        print("🔍 ChunkHound Real-time Indexing System Diagnostic")
        print("=" * 55)
        print(f"Test directory: {self.test_dir}")
        print(f"Database path: {self.db_path or 'NOT FOUND'}")
        print()

        try:
            # Run all diagnostic checks
            print("1. Checking ChunkHound processes...")
            self.check_chunkhound_processes()

            print("2. Checking environment configuration...")
            self.check_environment_config()

            print("3. Checking database status...")
            self.check_database_status()

            print("4. Checking watchdog library...")
            self.check_watchdog_availability()

            print("5. Testing file watcher responsiveness...")
            self.check_file_watcher_responsiveness()

        except KeyboardInterrupt:
            print("\n⚠ Diagnostic interrupted by user")
            self._add_result("Diagnostic Suite", "ERROR", "Interrupted by user")
        except Exception as e:
            print(f"\n❌ Diagnostic suite failed: {e}")
            self._add_result("Diagnostic Suite", "ERROR", f"Suite failed: {e}")

        return self.results

    def print_summary(self) -> str:
        """Print diagnostic summary and return overall status."""
        print("\n" + "=" * 55)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 55)

        status_counts = {"PASS": 0, "FAIL": 0, "WARNING": 0, "ERROR": 0}

        for result in self.results:
            status_icon = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️", "ERROR": "🔥"}
            icon = status_icon.get(result.status, "❓")

            print(f"{icon} {result.test_name}: {result.status}")
            print(f"   {result.message}")

            if result.details and result.status in ["FAIL", "ERROR", "WARNING"]:
                for key, value in result.details.items():
                    if isinstance(value, dict):
                        print(f"   {key}:")
                        for k, v in value.items():
                            print(f"     {k}: {v}")
                    else:
                        print(f"   {key}: {value}")
            print()

            status_counts[result.status] += 1

        print(f"Summary: {status_counts['PASS']} passed, {status_counts['FAIL']} failed, "
              f"{status_counts['WARNING']} warnings, {status_counts['ERROR']} errors")

        # Determine overall system status
        if status_counts['FAIL'] > 0 or status_counts['ERROR'] > 0:
            overall_status = "CRITICAL_ISSUES"
            print("🚨 CRITICAL ISSUES DETECTED - Real-time indexing may not be working")
        elif status_counts['WARNING'] > 0:
            overall_status = "WARNINGS"
            print("⚠️ WARNINGS DETECTED - Real-time indexing may have issues")
        else:
            overall_status = "HEALTHY"
            print("✅ SYSTEM APPEARS HEALTHY - Real-time indexing should be working")

        return overall_status

    def generate_hypothesis(self) -> str:
        """Generate hypothesis about real-time indexing issues based on diagnostic results."""
        print("\n" + "=" * 55)
        print("🔬 HYPOTHESIS GENERATION")
        print("=" * 55)

        issues = []

        # Check for process issues
        process_result = next((r for r in self.results if r.test_name == "Process Check"), None)
        if process_result and process_result.status in ["FAIL", "ERROR"]:
            issues.append("No ChunkHound MCP server with file watching is running")
        elif process_result and process_result.status == "WARNING":
            issues.append("ChunkHound process found but may not have file watching enabled")

        # Check for environment issues
        env_result = next((r for r in self.results if r.test_name == "Environment Config"), None)
        if env_result and env_result.status in ["FAIL", "WARNING"]:
            issues.append("Environment configuration issues detected")

        # Check for database issues
        db_result = next((r for r in self.results if r.test_name == "Database Status"), None)
        if db_result and db_result.status in ["FAIL", "ERROR"]:
            issues.append("Database connectivity or status issues")

        # Check for watchdog issues
        watchdog_result = next((r for r in self.results if r.test_name == "Watchdog Library"), None)
        if watchdog_result and watchdog_result.status in ["FAIL", "ERROR"]:
            issues.append("Missing or broken watchdog library dependency")

        # Check file watcher responsiveness
        watcher_result = next((r for r in self.results if r.test_name == "File Watcher Test"), None)
        if watcher_result and watcher_result.status in ["FAIL", "ERROR"]:
            issues.append("File watcher is not detecting or processing file changes")

        if not issues:
            hypothesis = "HYPOTHESIS: Real-time indexing system appears to be configured and running correctly. The reported issue may be:\n" \
                        "• Intermittent or timing-related\n" \
                        "• Related to specific file types or patterns\n" \
                        "• Due to database synchronization delays\n" \
                        "• A false positive - system may actually be working"
        else:
            hypothesis = f"HYPOTHESIS: Real-time indexing system has {len(issues)} identified issue(s):\n"
            for i, issue in enumerate(issues, 1):
                hypothesis += f"{i}. {issue}\n"

            hypothesis += "\nRECOMMENDED ACTIONS:\n"
            if "No ChunkHound MCP server" in issues[0] if issues else False:
                hypothesis += "• Start ChunkHound MCP server with --watch flag\n"
            if any("environment" in issue.lower() for issue in issues):
                hypothesis += "• Check and fix environment variable configuration\n"
            if any("database" in issue.lower() for issue in issues):
                hypothesis += "• Verify database connectivity and permissions\n"
            if any("watchdog" in issue.lower() for issue in issues):
                hypothesis += "• Install or repair watchdog library dependency\n"
            if any("file watcher" in issue.lower() for issue in issues):
                hypothesis += "• Investigate file watcher initialization and event processing\n"

        print(hypothesis)
        return hypothesis


def main():
    """Main diagnostic execution function."""
    diagnostic = RealTimeIndexingDiagnostic()

    try:
        # Run all diagnostics
        results = diagnostic.run_all_diagnostics()

        # Print summary
        overall_status = diagnostic.print_summary()

        # Generate hypothesis
        hypothesis = diagnostic.generate_hypothesis()

        # Return appropriate exit code
        return 0 if overall_status == "HEALTHY" else 1

    except Exception as e:
        print(f"❌ Diagnostic execution failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
