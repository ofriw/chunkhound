"""Language-specific tree-sitter mappings for ChunkHound parsers.

This package contains base classes and language-specific implementations
for mapping tree-sitter AST nodes to semantic chunks.
"""

from .base import BaseMapping
from .bash import BashMapping
from .c import CMapping
from .cpp import CppMapping
from .csharp import CSharpMapping
from .go import GoMapping
from .groovy import GroovyMapping
from .haskell import HaskellMapping
from .java import JavaMapping
from .javascript import JavaScriptMapping
from .json import JsonMapping
from .jsx import JSXMapping
from .kotlin import KotlinMapping
from .makefile import MakefileMapping
from .markdown import MarkdownMapping
from .matlab import MatlabMapping
from .objc import ObjCMapping
from .pdf import PDFMapping
from .python import PythonMapping
from .rust import RustMapping
from .text import TextMapping
from .toml import TomlMapping
from .tsx import TSXMapping
from .typescript import TypeScriptMapping
from .yaml import YamlMapping
from .zig import ZigMapping

__all__ = [
    "BaseMapping",
    "BashMapping",
    "CMapping",
    "CppMapping",
    "CSharpMapping",
    "GoMapping",
    "GroovyMapping",
    "HaskellMapping",
    "JavaMapping",
    "JavaScriptMapping",
    "JsonMapping",
    "JSXMapping",
    "KotlinMapping",
    "MakefileMapping",
    "MarkdownMapping",
    "MatlabMapping",
    "ObjCMapping",
    "PDFMapping",
    "PythonMapping",
    "RustMapping",
    "TextMapping",
    "TomlMapping",
    "TSXMapping",
    "TypeScriptMapping",
    "YamlMapping",
    "ZigMapping",
]
