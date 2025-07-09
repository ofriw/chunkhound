# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ChunkHound standalone executable (onedir mode).
This creates a directory distribution with the main executable and support files,
eliminating the single-file extraction overhead that causes 12+ second startup delays.
"""

import os
import sys
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH)
chunkhound_root = project_root / "chunkhound"

# Define all the packages that need to be included
packages = [
    'chunkhound'
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
    import tree_sitter_language_pack
    
    # Import all available tree-sitter language modules
    lang_modules = []
    for lang in ['c', 'cpp', 'go', 'rust', 'kotlin', 'groovy', 'java', 'csharp', 'typescript', 'javascript', 'bash']:
        try:
            module = __import__(f'tree_sitter_{lang}')
            lang_modules.append(module)
        except ImportError:
            pass

    # Find tree-sitter binary files
    ts_path = Path(tree_sitter.__file__).parent
    for so_file in ts_path.rglob('*.so'):
        tree_sitter_datas.append((str(so_file), 'tree_sitter'))
    for dylib_file in ts_path.rglob('*.dylib'):
        tree_sitter_datas.append((str(dylib_file), 'tree_sitter'))
    for dll_file in ts_path.rglob('*.dll'):
        tree_sitter_datas.append((str(dll_file), 'tree_sitter'))

    # Add language-specific binaries
    all_lang_modules = [tree_sitter_python, tree_sitter_markdown] + lang_modules
    for lang_module in all_lang_modules:
        lang_path = Path(lang_module.__file__).parent
        lang_name = lang_module.__name__.split("_")[-1]
        for so_file in lang_path.rglob('*.so'):
            tree_sitter_datas.append((str(so_file), f'tree_sitter_{lang_name}'))
        for dylib_file in lang_path.rglob('*.dylib'):
            tree_sitter_datas.append((str(dylib_file), f'tree_sitter_{lang_name}'))
        for dll_file in lang_path.rglob('*.dll'):
            tree_sitter_datas.append((str(dll_file), f'tree_sitter_{lang_name}'))

    # Add tree-sitter language pack binaries
    try:
        pack_path = Path(tree_sitter_language_pack.__file__).parent
        bindings_path = pack_path / 'bindings'
        if bindings_path.exists():
            for binding_file in bindings_path.glob('*.so'):
                tree_sitter_datas.append((str(binding_file), 'tree_sitter_language_pack/bindings'))
            for binding_file in bindings_path.glob('*.abi3.so'):
                tree_sitter_datas.append((str(binding_file), 'tree_sitter_language_pack/bindings'))
            for binding_file in bindings_path.glob('*.dylib'):
                tree_sitter_datas.append((str(binding_file), 'tree_sitter_language_pack/bindings'))
            for binding_file in bindings_path.glob('*.dll'):
                tree_sitter_datas.append((str(binding_file), 'tree_sitter_language_pack/bindings'))
    except NameError:
        pass

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

    # Core system modules are now within chunkhound package

    # Third-party hidden imports
    'tree_sitter',
    'tree_sitter.binding',
    'tree_sitter_python',
    'tree_sitter_markdown',
    'tree_sitter_language_pack',
    
    # All tree-sitter language modules
    'tree_sitter_c',
    'tree_sitter_cpp', 
    'tree_sitter_go',
    'tree_sitter_rust',
    'tree_sitter_kotlin',
    'tree_sitter_groovy',
    'tree_sitter_java',
    'tree_sitter_csharp',
    'tree_sitter_typescript',
    'tree_sitter_javascript',
    'tree_sitter_bash',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
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
    'tiktoken_ext',
    'tiktoken_ext.openai_public',

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

# Create the executable (onedir mode - no data files embedded)
exe = EXE(
    pyz,
    a.scripts,
    [],  # No binaries embedded (onedir mode)
    exclude_binaries=True,  # Exclude binaries from EXE (onedir mode)
    name='chunkhound',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX for faster startup
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Create the directory distribution (onedir mode)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # Disable UPX for faster startup
    upx_exclude=[],
    name='chunkhound',
)
