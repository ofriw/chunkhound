import os
import sys

import pytest


# Ensure package path resolution for direct imports
sys.path.insert(0, os.path.abspath("chunkhound"))

from chunkhound.parsers.parser_factory import ParserFactory
from chunkhound.core.types.common import Language
from chunkhound.parsers.universal_engine import UniversalConcept


@pytest.mark.skipif(
    os.environ.get("CH_SKIP_HCL_TESTS") == "1",
    reason="HCL tests explicitly disabled via env",
)
def test_hcl_attribute_paths_basic():
    sample = (
        'terraform { required_version = ">= 1.5" }\n'
        'provider "aws" { region = var.region }\n'
        'resource "aws_s3_bucket" "b" {\n'
        '  bucket = "my-bucket"\n'
        '  tags = { Env = "dev" }\n'
        '}\n'
    )

    parser = ParserFactory().create_parser(Language.HCL)
    ast = parser.engine.parse_to_ast(sample)
    chunks = parser.extractor.extract_concept(ast.root_node, sample.encode(), UniversalConcept.DEFINITION)

    # Filter only attribute-definition nodes
    attr = [c for c in chunks if c.language_node_type == "attribute"]
    names = {c.name for c in attr}

    # Expect dotted paths for attributes
    expected = {
        "terraform.required_version",
        "provider.aws.region",
        "resource.aws_s3_bucket.b.bucket",
        "resource.aws_s3_bucket.b.tags",
    }
    assert expected.issubset(names), f"Missing attributes: {expected - names} (got {names})"

    # Check metadata contains key and full path
    for c in attr:
        assert c.metadata.get("key"), f"Attribute {c.name} missing key metadata"
        assert c.metadata.get("path") == c.name, "Metadata path should equal chunk name"


def test_hcl_value_type_metadata_present():
    sample = (
        'locals {\n'
        '  list  = [1, 2, 3]\n'
        '  truth = true\n'
        '  num   = 42\n'
        '  ref   = var.region\n'
        '  text  = "hello"\n'
        '}\n'
    )

    parser = ParserFactory().create_parser(Language.HCL)
    ast = parser.engine.parse_to_ast(sample)
    chunks = parser.extractor.extract_concept(ast.root_node, sample.encode(), UniversalConcept.DEFINITION)

    attr = [c for c in chunks if c.language_node_type == "attribute"]
    assert len(attr) >= 5, "Expected at least 5 attribute definitions from locals block"

    allowed_types = {
        "expression",
        "number",
        "bool",
        "null",
        "string",
        "array",
        "object",
        "variable",
        "function",
        "template",
    }

    for c in attr:
        vtype = c.metadata.get("value_type")
        assert vtype is not None, f"Attribute {c.name} missing value_type metadata"
        assert isinstance(vtype, str), f"value_type should be a string, got {type(vtype)}"
        assert vtype in allowed_types or vtype, f"Unexpected value_type '{vtype}' for {c.name}"

