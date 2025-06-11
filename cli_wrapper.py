#!/usr/bin/env python3
"""Standalone CLI wrapper for ChunkHound to fix relative import issues in compiled binary."""

import sys
import os
from pathlib import Path

# Add the chunkhound package to sys.path to enable proper imports
# This is necessary for the compiled binary to find the chunkhound modules
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Import and run the main CLI function
try:
    from chunkhound.api.cli.main import main
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Error importing ChunkHound CLI: {e}", file=sys.stderr)
    print("Make sure ChunkHound is properly installed.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)