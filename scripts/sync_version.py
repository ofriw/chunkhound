#!/usr/bin/env uv run python3
"""
Synchronize version between version.py and pyproject.toml.

This script ensures that the version defined in chunkhound/version.py
is also updated in pyproject.toml to maintain consistency.
"""

import re
import sys
from pathlib import Path


def get_version_from_version_py():
    """Extract version from chunkhound/version.py."""
    version_file = Path(__file__).parent.parent / "chunkhound" / "version.py"
    content = version_file.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not find __version__ in version.py")
    return match.group(1)


def update_pyproject_toml(version):
    """Update version in pyproject.toml."""
    pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject_file.read_text()

    # Replace version in [project] section
    new_content = re.sub(
        r'^version\s*=\s*["\'][^"\']+["\']',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE,
    )

    if new_content == content:
        print(f"pyproject.toml already has version {version}")
        return False

    pyproject_file.write_text(new_content)
    print(f"Updated pyproject.toml to version {version}")
    return True


def main():
    """Main function."""
    try:
        version = get_version_from_version_py()
        print(f"Found version {version} in version.py")

        if update_pyproject_toml(version):
            print("✅ Version sync complete!")
        else:
            print("ℹ️  No changes needed.")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
