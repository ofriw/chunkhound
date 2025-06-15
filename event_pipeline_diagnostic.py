#!/usr/bin/env python3
"""
Event Pipeline Diagnostic - Minimal Investigation Script
========================================================

PURPOSE: Test the hypothesis that file events are detected but fail in processing pipeline
HYPOTHESIS: "Event processing pipeline failure between file detection and database writes"

INVESTIGATION STRATEGY:
1. Monitor MCP server process behavior during file operations
2. Test event queue processing with minimal file changes
3. Measure timing between file event and database write
4. Isolate failure point in the processing chain

USAGE: python event_pipeline_diagnostic.py
"""

import os
import sys
import time
import psutil
import sqlite3
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

class EventPipelineDiagnostic:
    def __init__(self):
        self.project_root = Path("/Users/ofri/Documents/GitHub/chunkhound")
        self.db_path = self.project_root / "chunkhound.db"
        self.test_file_prefix = "pipeline_test_"
        self.diagnostic_results = []

    def log(self, message, level="INFO"):
        """Log diagnostic message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        self.diagnostic_results.append(log_entry)

    def find_mcp_process(self):
        """Find running MCP server process"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['cmdline'] and any('mcp' in arg for arg in proc.info['cmdline']):
                    if any('--watch' in arg for arg in proc.info['cmdline']):
                        return proc
            return None
        except Exception as e:
            self.log(f"Error finding MCP process: {e}", "ERROR")
            return None

    def get_database_stats(self):
        """Get current database statistics"""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=1.0)
            cursor = conn.cursor()

            # Get total chunks
            cursor.execute("SELECT COUNT(*) FROM chunks")
            chunk_count = cursor.fetchone()[0]

            # Get recent chunks (last 60 seconds)
            cursor.execute("""
                SELECT COUNT(*) FROM chunks
                WHERE created_at > datetime('now', '-60 seconds')
            """)
            recent_chunks = cursor.fetchone()[0]

            conn.close()
            return {"total_chunks": chunk_count, "recent_chunks": recent_chunks}

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                return {"error": "database_locked", "message": "Database locked by MCP server"}
            else:
                return {"error": "database_error", "message": str(e)}
        except Exception as e:
            return {"error": "unknown_error", "message": str(e)}

    def monitor_process_activity(self, process, duration=3):
        """Monitor CPU and memory usage of MCP process"""
        measurements = []
        start_time = time.time()

        try:
            while time.time() - start_time < duration:
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                measurements.append({
                    "timestamp": time.time() - start_time,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_info.rss / 1024 / 1024
                })
                time.sleep(0.1)

        except Exception as e:
            self.log(f"Error monitoring process: {e}", "ERROR")

        return measurements

    def create_test_file(self, content="# Pipeline Test File\n\nThis is a test file for event pipeline diagnostic.\n"):
        """Create a test file in the watched directory"""
        timestamp = int(time.time() * 1000)
        test_file = self.project_root / f"{self.test_file_prefix}{timestamp}.md"

        try:
            with open(test_file, 'w') as f:
                f.write(content)
            self.log(f"Created test file: {test_file.name}")
            return test_file
        except Exception as e:
            self.log(f"Error creating test file: {e}", "ERROR")
            return None

    def cleanup_test_files(self):
        """Remove test files created during diagnostic"""
        try:
            for file_path in self.project_root.glob(f"{self.test_file_prefix}*"):
                file_path.unlink()
                self.log(f"Cleaned up test file: {file_path.name}")
        except Exception as e:
            self.log(f"Error during cleanup: {e}", "ERROR")

    def test_event_processing_pipeline(self):
        """Main diagnostic test for event processing pipeline"""
        self.log("=== EVENT PIPELINE DIAGNOSTIC START ===")

        # Step 1: Find MCP process
        mcp_process = self.find_mcp_process()
        if not mcp_process:
            self.log("CRITICAL: No MCP server process found with --watch flag", "ERROR")
            return False

        self.log(f"Found MCP process: PID {mcp_process.pid}")
        self.log(f"Command: {' '.join(mcp_process.cmdline())}")

        # Step 2: Get baseline database stats
        db_stats_before = self.get_database_stats()
        self.log(f"Database stats before: {db_stats_before}")

        # Step 3: Monitor process during file creation
        self.log("Creating test file and monitoring process activity...")

        # Start monitoring
        monitor_start = time.time()
        baseline_measurements = self.monitor_process_activity(mcp_process, 2)

        # Create test file
        test_file = self.create_test_file()
        if not test_file:
            return False

        # Monitor during file processing
        processing_measurements = self.monitor_process_activity(mcp_process, 5)

        # Step 4: Wait and check database
        self.log("Waiting 10 seconds for event processing...")
        time.sleep(10)

        db_stats_after = self.get_database_stats()
        self.log(f"Database stats after: {db_stats_after}")

        # Step 5: Analyze results
        self.analyze_pipeline_behavior(baseline_measurements, processing_measurements,
                                     db_stats_before, db_stats_after)

        # Step 6: Cleanup
        self.cleanup_test_files()

        self.log("=== EVENT PIPELINE DIAGNOSTIC COMPLETE ===")
        return True

    def analyze_pipeline_behavior(self, baseline, processing, db_before, db_after):
        """Analyze the diagnostic results to test hypothesis"""
        self.log("=== PIPELINE BEHAVIOR ANALYSIS ===")

        # Check for CPU activity spike
        baseline_avg_cpu = sum(m["cpu_percent"] for m in baseline) / len(baseline) if baseline else 0
        processing_avg_cpu = sum(m["cpu_percent"] for m in processing) / len(processing) if processing else 0

        cpu_spike = processing_avg_cpu > baseline_avg_cpu + 0.05
        self.log(f"CPU Activity - Baseline: {baseline_avg_cpu:.3f}%, Processing: {processing_avg_cpu:.3f}%")
        self.log(f"CPU Spike Detected: {'YES' if cpu_spike else 'NO'}")

        # Check database changes
        db_changed = False
        if "error" not in db_before and "error" not in db_after:
            chunk_diff = db_after["total_chunks"] - db_before["total_chunks"]
            recent_chunks = db_after.get("recent_chunks", 0)
            db_changed = chunk_diff > 0 or recent_chunks > 0
            self.log(f"Database Changes - Chunk diff: {chunk_diff}, Recent chunks: {recent_chunks}")
        else:
            self.log("Database locked - cannot verify changes (expected for active MCP server)")

        # Test hypothesis
        self.log("=== HYPOTHESIS TESTING ===")
        if cpu_spike and not db_changed:
            self.log("HYPOTHESIS CONFIRMED: Events detected but not processed to database", "CRITICAL")
            self.log("Evidence: CPU activity spike + No database changes = Pipeline failure")
        elif cpu_spike and db_changed:
            self.log("HYPOTHESIS DISPROVEN: Event processing pipeline working correctly", "SUCCESS")
        elif not cpu_spike:
            self.log("HYPOTHESIS INCONCLUSIVE: No detectable file event processing", "WARNING")
        else:
            self.log("HYPOTHESIS INCONCLUSIVE: Mixed signals in diagnostic data", "WARNING")

    def run_diagnostic(self):
        """Run the complete diagnostic sequence"""
        try:
            success = self.test_event_processing_pipeline()

            # Save results
            results_file = self.project_root / f"event_pipeline_diagnostic_{int(time.time())}.log"
            with open(results_file, 'w') as f:
                f.write('\n'.join(self.diagnostic_results))
            self.log(f"Diagnostic results saved to: {results_file.name}")

            return success

        except KeyboardInterrupt:
            self.log("Diagnostic interrupted by user", "WARNING")
            self.cleanup_test_files()
            return False
        except Exception as e:
            self.log(f"Diagnostic failed with error: {e}", "ERROR")
            self.cleanup_test_files()
            return False

if __name__ == "__main__":
    print("Event Pipeline Diagnostic - Testing Event Processing Hypothesis")
    print("================================================================")
    print()

    diagnostic = EventPipelineDiagnostic()
    success = diagnostic.run_diagnostic()

    print()
    print("================================================================")
    if success:
        print("✅ Diagnostic completed successfully")
        print("📋 Check log file for detailed results")
    else:
        print("❌ Diagnostic failed or was interrupted")
        print("🔍 Check error messages above for details")
