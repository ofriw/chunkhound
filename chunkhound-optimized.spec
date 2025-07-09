# -*- mode: python ; coding: utf-8 -*-
"""
Optimized PyInstaller spec file for ChunkHound with focus on startup performance.
This version eliminates unnecessary data collection and optimizes for fast startup.
"""

import os
import sys
import platform
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH)

# Minimal hidden imports - only what's absolutely necessary
hiddenimports = [
    # Core chunkhound modules that are definitely needed
    'chunkhound.api.cli.main',
    'chunkhound.api.cli.commands.run',
    'chunkhound.api.cli.commands.config',
    'chunkhound.api.cli.commands.mcp',
    'chunkhound.mcp_entry',

    # Core chunkhound modules for MCP server (PyInstaller import fallback fix)
    'chunkhound.database',
    'chunkhound.embeddings',
    'chunkhound.signal_coordinator',
    'chunkhound.file_watcher',
    'chunkhound.core.config',
    'core.types.common',
    'registry',  # Fixed: should be 'registry', not 'chunkhound.registry'
    
    # Refactored parser system
    'chunkhound.parser',
    'chunkhound.tree_cache',

    # Core system modules are now within chunkhound package
    
    # All parser modules are now within chunkhound package

    # Essential third-party modules
    'duckdb',
    'tree_sitter',
    'tree_sitter_python',
    'tree_sitter_markdown',
    
    # Tree-sitter language pack for all languages
    'tree_sitter_language_pack',
    'tree_sitter_language_pack.bindings',
    'openai',
    'pydantic',
    'click',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    'loguru',
    'mcp',
    'mcp.server',
    'mcp.server.fastmcp',
    
    # Required for MCP file monitoring
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
]

# Minimal data files - only essential binaries
datas = [
    # Include mcp_launcher.py for MCP server functionality
    (str(project_root / 'mcp_launcher.py'), '.'),
]

# Add only essential DuckDB binaries
try:
    import duckdb
    duckdb_path = Path(duckdb.__file__).parent
    for lib_file in duckdb_path.glob('*.so'):
        datas.append((str(lib_file), 'duckdb'))
    for lib_file in duckdb_path.glob('*.dylib'):
        datas.append((str(lib_file), 'duckdb'))
    for lib_file in duckdb_path.glob('*.dll'):
        datas.append((str(lib_file), 'duckdb'))
except ImportError:
    pass

# Add tree-sitter language pack binaries
try:
    import tree_sitter
    import tree_sitter_language_pack

    # Core tree-sitter library
    ts_path = Path(tree_sitter.__file__).parent
    for lib_file in ts_path.glob('*.so'):
        datas.append((str(lib_file), 'tree_sitter'))
    for lib_file in ts_path.glob('*.dylib'):
        datas.append((str(lib_file), 'tree_sitter'))
    for lib_file in ts_path.glob('*.dll'):
        datas.append((str(lib_file), 'tree_sitter'))

    # Language pack bindings - includes all supported languages
    lang_pack_path = Path(tree_sitter_language_pack.__file__).parent
    bindings_path = lang_pack_path / 'bindings'
    if bindings_path.exists():
        for lib_file in bindings_path.glob('*.so'):
            datas.append((str(lib_file), 'tree_sitter_language_pack/bindings'))
        for lib_file in bindings_path.glob('*.dylib'):
            datas.append((str(lib_file), 'tree_sitter_language_pack/bindings'))
        for lib_file in bindings_path.glob('*.dll'):
            datas.append((str(lib_file), 'tree_sitter_language_pack/bindings'))
        # Also include the __init__.py file for the bindings module
        bindings_init = bindings_path / '__init__.py'
        if bindings_init.exists():
            datas.append((str(bindings_init), 'tree_sitter_language_pack/bindings'))
except ImportError:
    pass

# Add tiktoken_ext data files (encoding data)
tiktoken_ext_datas = []
try:
    import tiktoken_ext
    for ext_path in tiktoken_ext.__path__:
        ext_path = Path(ext_path)
        if ext_path.exists():
            for file_path in ext_path.rglob('*'):
                if file_path.is_file() and not file_path.name.endswith('.pyc'):
                    rel_path = file_path.relative_to(ext_path)
                    dest_dir = f"tiktoken_ext/{rel_path.parent}" if rel_path.parent != Path('.') else "tiktoken_ext"
                    tiktoken_ext_datas.append((str(file_path), dest_dir))
except ImportError:
    print("Warning: Could not import tiktoken_ext")

# Add tiktoken cached encoding data files
try:
    import tempfile
    import os
    cache_dir = os.path.join(tempfile.gettempdir(), "data-gym-cache")
    if os.path.exists(cache_dir):
        for cache_file in os.listdir(cache_dir):
            cache_path = os.path.join(cache_dir, cache_file)
            if os.path.isfile(cache_path):
                tiktoken_ext_datas.append((cache_path, "data-gym-cache"))
except Exception as e:
    print(f"Warning: Could not add tiktoken cache files: {e}")

datas.extend(tiktoken_ext_datas)

# Platform-specific settings
is_windows = platform.system() == 'Windows'
should_strip = not is_windows  # Disable stripping on Windows to prevent DLL loading issues

# Aggressive exclusions to reduce size and startup time
excludes = [
    # Remove large unused packages
    'matplotlib',
    'numpy',
    'scipy',
    'pandas',
    'tensorflow',
    'torch',
    'jupyter',
    'notebook',
    'IPython',
    'sphinx',
    'pytest',
    'test',
    'tests',
    'unittest',
    'doctest',
    'pdb',
    'profile',
    'pstats',
    'cProfile',

    # Remove GUI frameworks
    'tkinter',
    'Tkinter',
    '_tkinter',
    'tcl',
    'tk',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'wx',

    # Remove development tools
    'setuptools',
    'pip',
    'wheel',
    'distutils',
    'packaging',

    # Remove optional features we don't need
    'http.server',
    'urllib3.contrib',
    'requests_oauthlib',
    'oauthlib',

    # Remove unused stdlib modules
    'turtle',
    'audiodev',
    'curses',
    'dbm',
    'ensurepip',
    'venv',
    'wsgiref',
    'xmlrpc',
]

# Optimized Analysis configuration
a = Analysis(
    ['cli_wrapper.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
    optimize=2,  # Enable maximum bytecode optimization
)

# Optimize PYZ with compression
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create optimized executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chunkhound-optimized',
    debug=False,
    bootloader_ignore_signals=False,
    strip=should_strip,  # Disable stripping on Windows to prevent DLL loading issues
    upx=False,   # Keep UPX disabled for now
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Create optimized directory distribution
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=should_strip,  # Disable stripping on Windows to prevent DLL loading issues from all binaries
    upx=False,   # Keep UPX disabled for startup performance
    upx_exclude=[],
    name='chunkhound-optimized',
)
