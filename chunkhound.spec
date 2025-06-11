# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ChunkHound standalone executable.
This creates a single-file executable that includes all dependencies.
"""

import os
import sys
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH)
chunkhound_root = project_root / "chunkhound"

# Define all the packages that need to be included
packages = [
    'chunkhound',
    'core',
    'interfaces', 
    'providers',
    'services',
    'registry'
]

# Collect all Python files from our packages
def collect_package_data(package_name):
    """Collect all data files from a package directory."""
    package_path = project_root / package_name
    datas = []
    if package_path.exists():
        for file_path in package_path.rglob('*'):
            if file_path.is_file() and not file_path.name.endswith('.pyc'):
                rel_path = file_path.relative_to(project_root)
                dest_dir = str(rel_path.parent)
                datas.append((str(file_path), dest_dir))
    return datas

# Collect data files from all packages
datas = []
for package in packages:
    datas.extend(collect_package_data(package))

# Add tree-sitter language binaries
tree_sitter_datas = []
try:
    import tree_sitter
    import tree_sitter_python
    import tree_sitter_markdown
    
    # Find tree-sitter binary files
    ts_path = Path(tree_sitter.__file__).parent
    for so_file in ts_path.rglob('*.so'):
        tree_sitter_datas.append((str(so_file), 'tree_sitter'))
    for dylib_file in ts_path.rglob('*.dylib'):
        tree_sitter_datas.append((str(dylib_file), 'tree_sitter'))
    for dll_file in ts_path.rglob('*.dll'):
        tree_sitter_datas.append((str(dll_file), 'tree_sitter'))
        
    # Add language-specific binaries
    for lang_module in [tree_sitter_python, tree_sitter_markdown]:
        lang_path = Path(lang_module.__file__).parent
        for so_file in lang_path.rglob('*.so'):
            tree_sitter_datas.append((str(so_file), f'tree_sitter_{lang_module.__name__.split("_")[-1]}'))
        for dylib_file in lang_path.rglob('*.dylib'):
            tree_sitter_datas.append((str(dylib_file), f'tree_sitter_{lang_module.__name__.split("_")[-1]}'))
        for dll_file in lang_path.rglob('*.dll'):
            tree_sitter_datas.append((str(dll_file), f'tree_sitter_{lang_module.__name__.split("_")[-1]}'))
            
except ImportError:
    print("Warning: Could not import tree-sitter modules")

datas.extend(tree_sitter_datas)

# Add DuckDB binaries
duckdb_datas = []
try:
    import duckdb
    duckdb_path = Path(duckdb.__file__).parent
    for so_file in duckdb_path.rglob('*.so'):
        duckdb_datas.append((str(so_file), 'duckdb'))
    for dylib_file in duckdb_path.rglob('*.dylib'):
        duckdb_datas.append((str(dylib_file), 'duckdb'))
    for dll_file in duckdb_path.rglob('*.dll'):
        duckdb_datas.append((str(dll_file), 'duckdb'))
except ImportError:
    print("Warning: Could not import duckdb")

datas.extend(duckdb_datas)

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Core chunkhound modules
    'chunkhound.api.cli.main',
    'chunkhound.api.cli.commands.run',
    'chunkhound.api.cli.commands.config', 
    'chunkhound.api.cli.parsers',
    'chunkhound.api.cli.parsers.run_parser',
    'chunkhound.api.cli.parsers.mcp_parser',
    'chunkhound.api.cli.parsers.config_parser',
    'chunkhound.api.cli.utils.validation',
    'chunkhound.mcp_entry',
    
    # Core system modules
    'core.models',
    'core.models.chunk',
    'core.models.file_metadata',
    'core.models.search',
    'interfaces.embedding',
    'interfaces.parser',
    'providers.embedding.openai_provider',
    'providers.embedding.tei_provider', 
    'providers.embedding.bge_in_icl_provider',
    'providers.parser.tree_sitter_provider',
    'services.embedding_service',
    'services.parsing_service',
    'services.indexing_service',
    'services.search_service',
    'registry.service_registry',
    
    # Third-party hidden imports
    'tree_sitter',
    'tree_sitter.binding',
    'tree_sitter_python',
    'tree_sitter_markdown',
    'tree_sitter_language_pack',
    'duckdb',
    'openai',
    'openai.types',
    'openai.resources',
    'aiohttp',
    'aiohttp.client',
    'aiohttp.connector',
    'pydantic',
    'pydantic.fields',
    'pydantic.validators', 
    'click',
    'loguru',
    'mcp',
    'mcp.server',
    'mcp.server.models',
    'mcp.server.fastmcp',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'psutil',
    'yaml',
    'tiktoken',
    'tiktoken.core',
    
    # System modules that might be needed
    'asyncio',
    'concurrent.futures',
    'multiprocessing',
    'sqlite3',
    'json',
    'pathlib',
    'subprocess',
    'tempfile',
    'shutil',
]

# Binaries that need to be included
binaries = []

# Analysis configuration
a = Analysis(
    ['cli_wrapper.py'],  # Entry point script
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        "gi": {
            "icons": ["Adwaita"],
            "themes": ["Adwaita"],
            "languages": ["en_US", "en"],
        },
    },
    runtime_hooks=[],
    excludes=[
        # Exclude large unused modules to reduce size
        'matplotlib',
        'numpy.distutils',
        'tcl',
        'tk',
        '_tkinter',
        'tkinter',
        'Tkinter',
        'jupyter',
        'notebook',
        'IPython',
        'sphinx',
        'pytest',
        'test',
        'tests',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
    optimize=0,
)

# Remove duplicate entries
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='chunkhound',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)