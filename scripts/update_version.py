#!/usr/bin/env uv run python3
"""
Update ChunkHound version across all files.

Usage:
    python scripts/update_version.py 2.2.0
"""

import re
import sys
from pathlib import Path


def update_version_py(version):
    """Update version in chunkhound/version.py."""
    version_file = Path(__file__).parent.parent / "chunkhound" / "version.py"
    content = version_file.read_text()
    new_content = re.sub(
        r'__version__\s*=\s*["\'][^"\']+["\']', f'__version__ = "{version}"', content
    )
    version_file.write_text(new_content)
    print(f"✅ Updated version.py to {version}")


def update_pyproject_toml(version):
    """Update version in pyproject.toml."""
    pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject_file.read_text()
    new_content = re.sub(
        r'^version\s*=\s*["\'][^"\']+["\']',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE,
    )
    pyproject_file.write_text(new_content)
    print(f"✅ Updated pyproject.toml to {version}")


def validate_version(version):
    """Validate version format."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
    if not re.match(pattern, version):
        raise ValueError(
            f"Invalid version format: {version}. Expected: X.Y.Z or X.Y.Z-suffix"
        )


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <version>", file=sys.stderr)
        print(f"Example: {sys.argv[0]} 2.2.0", file=sys.stderr)
        sys.exit(1)

    version = sys.argv[1]

    try:
        validate_version(version)
        print(f"🔄 Updating ChunkHound to version {version}")

        update_version_py(version)
        update_pyproject_toml(version)

        print(f"\n✅ Successfully updated ChunkHound to version {version}")
        print("\n📋 Next steps:")
        print("1. Review the changes: git diff")
        print("2. Commit the changes: git commit -am 'Bump version to " + version + "'")
        print("3. Create a tag: git tag v" + version)
        print("4. Push changes: git push && git push --tags")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
