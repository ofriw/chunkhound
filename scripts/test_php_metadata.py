#!/usr/bin/env python3
"""Test PHP metadata extraction for individual language features."""

from pathlib import Path
from chunkhound.parsers.parser_factory import ParserFactory
from chunkhound.core.types.common import Language

def test_feature(name: str, php_code: str, expected_checks: dict):
    """Test a specific PHP feature and verify expected metadata."""
    print(f"\n=== Testing: {name} ===")

    factory = ParserFactory()
    parser = factory.create_parser(Language.PHP)
    chunks = parser.parse_content(php_code, Path("test.php"), file_id=1)

    if not chunks:
        print("❌ No chunks found!")
        return False

    # Get the first chunk (usually the one we care about)
    chunk = chunks[0]
    print(f"Symbol: {chunk.symbol}")
    print(f"Type: {chunk.chunk_type.value}")

    if chunk.metadata:
        print(f"Metadata: {chunk.metadata}")
    else:
        print("No metadata")
        return False

    # Check expected values
    all_pass = True
    for key, expected_value in expected_checks.items():
        actual_value = chunk.metadata.get(key)
        matches = actual_value == expected_value
        status = "✅" if matches else "❌"
        print(f"  {status} {key}: expected={expected_value}, actual={actual_value}")
        if not matches:
            all_pass = False

    return all_pass


# Test 1: Function with typed parameters and return type
test_feature(
    "Function with typed parameters and return type",
    """<?php
function getUser(int $id, ?string $name = null): ?User {
    return null;
}
""",
    {
        "kind": "function",
        "node_type": "function_definition",
        "return_type": "?User",
    }
)

# Test 2: Abstract class
test_feature(
    "Abstract class",
    """<?php
abstract class BaseService {
    private static $instance;
}
""",
    {
        "kind": "class",
        "is_abstract": True,
    }
)

# Test 3: Final class
test_feature(
    "Final class",
    """<?php
final class FinalService {
    public function test() {}
}
""",
    {
        "kind": "class",
        "is_final": True,
    }
)

# Test 4: Public method (visibility)
test_feature(
    "Public method",
    """<?php
class MyClass {
    public function publicMethod(): void {
        echo "test";
    }
}
""",
    {
        "kind": "class",  # Methods merge into class
    }
)

# Test 5: Interface
test_feature(
    "Interface",
    """<?php
interface ServiceInterface {
    public function execute(): mixed;
}
""",
    {
        "kind": "interface",
    }
)

# Test 6: Trait
test_feature(
    "Trait",
    """<?php
trait Loggable {
    private function log(string $message): void {
        echo $message;
    }
}
""",
    {
        "kind": "trait",
    }
)

print("\n" + "="*60)
print("Summary: Testing complete!")
print("="*60)
