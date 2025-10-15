"""Cross-reference analysis for Vue Single File Components.

This module provides cross-reference tracking between Vue template sections
and script sections, linking template variable references to script symbol
definitions.

## Features
- Symbol table construction from script section
- Variable, function, prop, and composable extraction
- Reactive symbol detection (ref, reactive, computed)
- Template reference matching
- Cross-reference metadata addition to chunks

## Usage
```python
from chunkhound.parsers.vue_cross_ref import build_symbol_table, add_cross_references

# Build symbol table from script chunks
symbol_table = build_symbol_table(script_chunks)

# Add cross-reference metadata to template chunks
add_cross_references(template_chunks, symbol_table)
```
"""

import re
from dataclasses import dataclass, field, replace
from typing import Any

from chunkhound.core.models.chunk import Chunk


@dataclass
class VueSymbol:
    """Represents a symbol defined in Vue script section."""

    name: str
    type: str  # 'variable', 'function', 'prop', 'composable', 'constant', 'computed'
    chunk_symbol: str  # The chunk.symbol where it's defined
    start_line: int
    end_line: int
    is_reactive: bool = False  # ref(), reactive(), computed()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VueSymbolTable:
    """Symbol table for Vue SFC."""

    variables: dict[str, VueSymbol] = field(default_factory=dict)  # name -> symbol
    functions: dict[str, VueSymbol] = field(default_factory=dict)
    props: dict[str, VueSymbol] = field(default_factory=dict)
    composables: dict[str, VueSymbol] = field(default_factory=dict)

    def add_symbol(self, symbol: VueSymbol) -> None:
        """Add a symbol to the appropriate table."""
        if symbol.type == "function":
            self.functions[symbol.name] = symbol
        elif symbol.type == "prop":
            self.props[symbol.name] = symbol
        elif symbol.type == "composable":
            self.composables[symbol.name] = symbol
        else:
            # variable, constant, computed
            self.variables[symbol.name] = symbol

    def find_symbol(self, name: str) -> VueSymbol | None:
        """Find a symbol by name in any table."""
        # Check in order: variables, functions, props, composables
        if name in self.variables:
            return self.variables[name]
        if name in self.functions:
            return self.functions[name]
        if name in self.props:
            return self.props[name]
        if name in self.composables:
            return self.composables[name]
        return None

    def get_all_symbols(self) -> dict[str, VueSymbol]:
        """Get all symbols as a single dictionary."""
        result = {}
        result.update(self.variables)
        result.update(self.functions)
        result.update(self.props)
        result.update(self.composables)
        return result


# Regex patterns for symbol extraction
CONST_VAR_PATTERN = re.compile(
    r"(?:^|\n)\s*(const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=", re.MULTILINE
)

FUNCTION_DECL_PATTERN = re.compile(
    r"(?:^|\n)\s*function\s+([a-zA-Z_$][\w$]*)\s*\(", re.MULTILINE
)

ARROW_FUNCTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>",
    re.MULTILINE,
)

REACTIVE_PATTERNS = {
    "ref": re.compile(r"\bref\s*\("),
    "reactive": re.compile(r"\breactive\s*\("),
    "computed": re.compile(r"\bcomputed\s*\("),
}

DEFINE_PROPS_PATTERN = re.compile(
    r"defineProps\s*(?:<[^>]+>)?\s*\(", re.MULTILINE | re.DOTALL
)

COMPOSABLE_PATTERN = re.compile(
    r"(?:const|let|var)\s+(?:\{([^}]+)\}|([a-zA-Z_$][\w$]*))\s*=\s*(use[A-Z][\w$]*)\s*\(",
    re.MULTILINE,
)

# JavaScript keywords to filter out from identifiers
JS_KEYWORDS = {
    "if",
    "else",
    "for",
    "while",
    "do",
    "switch",
    "case",
    "break",
    "continue",
    "return",
    "function",
    "const",
    "let",
    "var",
    "true",
    "false",
    "null",
    "undefined",
    "this",
    "new",
    "typeof",
    "instanceof",
    "in",
    "of",
    "and",
    "or",
    "not",
}


def build_symbol_table(
    script_chunks: list[Chunk], script_content: str | None = None
) -> VueSymbolTable:
    """Build a symbol table from script section chunks and/or full script content.

    Args:
        script_chunks: List of chunks from script section
        script_content: Optional full script content for better symbol extraction

    Returns:
        VueSymbolTable containing all extracted symbols
    """
    symbol_table = VueSymbolTable()

    # Strategy: Extract symbols from both individual chunks AND from full script content
    # - Individual chunks may have important metadata (vue_macros, etc.)
    # - Full script content catches all variable declarations which may not be chunked

    # First, extract from individual chunks (catches functions and macros with metadata)
    for chunk in script_chunks:
        symbols = extract_symbols_from_chunk(chunk)
        for symbol in symbols:
            symbol_table.add_symbol(symbol)

    # Second, if full script content is provided, extract from it
    # This catches variable declarations that may not be in individual chunks
    if script_content and script_chunks:
        # Create a temporary chunk with the full script
        first_chunk = script_chunks[0]
        last_chunk = script_chunks[-1] if len(script_chunks) > 1 else first_chunk
        temp_chunk = Chunk(
            symbol="<full_script>",
            start_line=first_chunk.start_line,
            end_line=last_chunk.end_line,
            code=script_content,
            chunk_type=first_chunk.chunk_type,
            file_id=first_chunk.file_id,
            language=first_chunk.language,
            file_path=first_chunk.file_path,
            metadata=first_chunk.metadata,  # May contain vue_macros
        )

        # Extract symbols from full script
        symbols = extract_symbols_from_chunk(temp_chunk)
        for symbol in symbols:
            # Only add if not already in table (avoid duplicates)
            existing = symbol_table.find_symbol(symbol.name)
            if not existing:
                symbol_table.add_symbol(symbol)

    return symbol_table


def extract_symbols_from_chunk(chunk: Chunk) -> list[VueSymbol]:
    """Extract all symbols from a chunk.

    Args:
        chunk: Chunk to extract symbols from

    Returns:
        List of VueSymbol objects
    """
    symbols: list[VueSymbol] = []
    code = chunk.code

    # Extract variable declarations (const, let, var)
    for match in CONST_VAR_PATTERN.finditer(code):
        keyword = match.group(1)
        var_name = match.group(2)

        # Check if this is a reactive variable
        is_reactive = False
        reactive_type = None

        # Look ahead in the code to see if it's reactive
        match_end = match.end()
        remaining_code = code[match_end : match_end + 100]  # Look ahead 100 chars

        for reactive_name, pattern in REACTIVE_PATTERNS.items():
            if pattern.search(remaining_code):
                is_reactive = True
                reactive_type = reactive_name
                break

        symbol_type = "constant" if keyword == "const" else "variable"
        if reactive_type == "computed":
            symbol_type = "computed"

        symbols.append(
            VueSymbol(
                name=var_name,
                type=symbol_type,
                chunk_symbol=chunk.symbol,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                is_reactive=is_reactive,
                metadata={
                    "keyword": keyword,
                    "reactive_type": reactive_type if reactive_type else None,
                },
            )
        )

    # Extract function declarations
    for match in FUNCTION_DECL_PATTERN.finditer(code):
        func_name = match.group(1)
        symbols.append(
            VueSymbol(
                name=func_name,
                type="function",
                chunk_symbol=chunk.symbol,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                is_reactive=False,
                metadata={"declaration_style": "function"},
            )
        )

    # Extract arrow functions
    for match in ARROW_FUNCTION_PATTERN.finditer(code):
        func_name = match.group(1)
        # Skip if already found as a variable (arrow functions are also variables)
        if not any(s.name == func_name for s in symbols):
            symbols.append(
                VueSymbol(
                    name=func_name,
                    type="function",
                    chunk_symbol=chunk.symbol,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    is_reactive=False,
                    metadata={"declaration_style": "arrow"},
                )
            )

    # Extract props from defineProps
    if chunk.metadata and "vue_macros" in chunk.metadata:
        if "defineProps" in chunk.metadata["vue_macros"]:
            # Try to extract prop names from defineProps
            props = extract_props_from_define_props(code)
            for prop_name in props:
                symbols.append(
                    VueSymbol(
                        name=prop_name,
                        type="prop",
                        chunk_symbol=chunk.symbol,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        is_reactive=True,  # Props are reactive
                        metadata={"source": "defineProps"},
                    )
                )

    # Extract composable destructured variables
    for match in COMPOSABLE_PATTERN.finditer(code):
        destructured = match.group(1)
        simple_var = match.group(2)
        composable_name = match.group(3)

        if destructured:
            # Destructured: const { user, login } = useUser()
            var_names = [
                v.strip() for v in destructured.split(",") if v.strip()
            ]
            for var_name in var_names:
                # Remove any aliases (e.g., "user: userData" -> "user")
                if ":" in var_name:
                    var_name = var_name.split(":")[0].strip()

                symbols.append(
                    VueSymbol(
                        name=var_name,
                        type="composable",
                        chunk_symbol=chunk.symbol,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        is_reactive=True,  # Composable returns are typically reactive
                        metadata={"composable": composable_name},
                    )
                )
        elif simple_var:
            # Simple: const userData = useUser()
            symbols.append(
                VueSymbol(
                    name=simple_var,
                    type="composable",
                    chunk_symbol=chunk.symbol,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    is_reactive=True,
                    metadata={"composable": composable_name},
                )
            )

    return symbols


def extract_props_from_define_props(code: str) -> list[str]:
    """Extract prop names from defineProps call.

    Args:
        code: Script code containing defineProps

    Returns:
        List of prop names
    """
    props = []

    # Try to find defineProps with TypeScript interface
    # defineProps<{ title: string, count?: number }>()
    ts_interface_pattern = re.compile(
        r"defineProps\s*<\s*\{([^}]+)\}\s*>", re.MULTILINE | re.DOTALL
    )
    match = ts_interface_pattern.search(code)

    if match:
        props_str = match.group(1)
        # Extract prop names from TypeScript interface
        prop_pattern = re.compile(r"([a-zA-Z_$][\w$]*)\s*[?:]")
        for prop_match in prop_pattern.finditer(props_str):
            props.append(prop_match.group(1))
    else:
        # Try to find defineProps with object syntax
        # defineProps({ title: String, count: Number })
        # This is more complex, so we'll just look for identifiers before ":"
        obj_pattern = re.compile(
            r"defineProps\s*\(\s*\{([^}]+)\}", re.MULTILINE | re.DOTALL
        )
        match = obj_pattern.search(code)
        if match:
            props_str = match.group(1)
            prop_pattern = re.compile(r"([a-zA-Z_$][\w$]*)\s*:")
            for prop_match in prop_pattern.finditer(props_str):
                props.append(prop_match.group(1))

    return props


def extract_identifiers_from_expression(expression: str) -> list[str]:
    """Extract all JavaScript identifiers from an expression.

    Args:
        expression: JavaScript expression string

    Returns:
        List of identifier names (filtered to exclude keywords)
    """
    # Pattern to match JavaScript identifiers
    identifier_pattern = re.compile(r"\b[a-zA-Z_$][\w$]*\b")

    identifiers = []
    for match in identifier_pattern.finditer(expression):
        identifier = match.group(0)
        # Filter out JavaScript keywords
        if identifier not in JS_KEYWORDS:
            identifiers.append(identifier)

    return identifiers


def match_template_references(
    template_chunks: list[Chunk], symbol_table: VueSymbolTable
) -> list[Chunk]:
    """Match template references to script symbols and add metadata.

    Args:
        template_chunks: List of chunks from template section
        symbol_table: Symbol table built from script section

    Returns:
        List of template chunks with added cross-reference metadata
    """
    updated_chunks = []

    for chunk in template_chunks:
        # Extract references from this chunk's metadata
        references = extract_references_from_chunk(chunk)

        # Match references against symbol table
        matched_symbols = []
        undefined_references = []

        for ref in references:
            symbol = symbol_table.find_symbol(ref)
            if symbol:
                matched_symbols.append(ref)
            else:
                undefined_references.append(ref)

        # Add cross-reference metadata to chunk
        if matched_symbols or undefined_references:
            metadata = chunk.metadata.copy() if chunk.metadata else {}

            if matched_symbols:
                metadata["script_references"] = matched_symbols

            if undefined_references:
                metadata["undefined_references"] = undefined_references

            # Create updated chunk with new metadata
            updated_chunk = replace(chunk, metadata=metadata)
            updated_chunks.append(updated_chunk)
        else:
            # No references found, keep original chunk
            updated_chunks.append(chunk)

    return updated_chunks


def extract_references_from_chunk(chunk: Chunk) -> list[str]:
    """Extract all variable references from a template chunk.

    Args:
        chunk: Template chunk to extract references from

    Returns:
        List of unique variable names referenced
    """
    references = set()

    # Check metadata for expressions
    if chunk.metadata:
        # Interpolations: {{ expression }}
        if "interpolation_expression" in chunk.metadata:
            expr = chunk.metadata["interpolation_expression"]
            identifiers = extract_identifiers_from_expression(expr)
            references.update(identifiers)

        # Event handlers: @click="handler"
        if "handler_expression" in chunk.metadata:
            expr = chunk.metadata["handler_expression"]
            identifiers = extract_identifiers_from_expression(expr)
            references.update(identifiers)

        # Property bindings: :prop="expression"
        if "binding_expression" in chunk.metadata:
            expr = chunk.metadata["binding_expression"]
            identifiers = extract_identifiers_from_expression(expr)
            references.update(identifiers)

        # v-if conditions: v-if="condition"
        if "condition" in chunk.metadata:
            expr = chunk.metadata["condition"]
            identifiers = extract_identifiers_from_expression(expr)
            references.update(identifiers)

        # v-for loops: v-for="item in items"
        if "loop_iterable" in chunk.metadata:
            expr = chunk.metadata["loop_iterable"]
            identifiers = extract_identifiers_from_expression(expr)
            references.update(identifiers)

        # v-model: v-model="variable"
        if "model_binding" in chunk.metadata:
            expr = chunk.metadata["model_binding"]
            identifiers = extract_identifiers_from_expression(expr)
            references.update(identifiers)

    return list(references)


def add_cross_references(
    script_chunks: list[Chunk],
    template_chunks: list[Chunk],
    script_content: str | None = None,
) -> tuple[VueSymbolTable, list[Chunk]]:
    """Add cross-reference metadata to template chunks.

    This is the main entry point for cross-reference analysis.

    Args:
        script_chunks: List of chunks from script section
        template_chunks: List of chunks from template section
        script_content: Optional full script content for better symbol extraction

    Returns:
        Tuple of (symbol_table, updated_template_chunks)
    """
    # Build symbol table from script chunks and/or full script content
    symbol_table = build_symbol_table(script_chunks, script_content)

    # Match template references to script symbols
    updated_template_chunks = match_template_references(template_chunks, symbol_table)

    return symbol_table, updated_template_chunks
