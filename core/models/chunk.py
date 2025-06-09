"""ChunkHound Chunk Domain Model - Represents a semantic code chunk in the system.

This module contains the Chunk domain model which represents a semantic unit of code
that has been extracted from a source file. The Chunk model encapsulates chunk metadata,
content, and provides methods for working with chunk data in a type-safe manner.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..types import ChunkId, FileId, FilePath, ChunkType, Language, LineNumber, ByteOffset
from ..exceptions import ValidationError, ModelError


@dataclass(frozen=True)
class Chunk:
    """Domain model representing a semantic code chunk.
    
    This immutable model encapsulates all information about a semantic unit of code
    that has been extracted from a source file, including its location, content,
    and metadata.
    
    Attributes:
        symbol: Function, class, or element name
        start_line: Starting line number (1-based)
        end_line: Ending line number (1-based, inclusive)
        code: Raw code content
        chunk_type: Type of semantic chunk
        file_id: Reference to the parent file
        language: Programming language of the chunk
        id: Unique chunk identifier (None for new chunks)
        file_path: Path to the source file (for convenience)
        parent_header: Parent header for nested content (markdown)
        start_byte: Starting byte offset (optional)
        end_byte: Ending byte offset (optional)
        created_at: When the chunk was first indexed
        updated_at: When the chunk was last updated
    """
    
    symbol: str
    start_line: LineNumber
    end_line: LineNumber
    code: str
    chunk_type: ChunkType
    file_id: FileId
    language: Language
    id: Optional[ChunkId] = None
    file_path: Optional[FilePath] = None
    parent_header: Optional[str] = None
    start_byte: Optional[ByteOffset] = None
    end_byte: Optional[ByteOffset] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate chunk model after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate chunk model attributes."""
        # Symbol validation
        if not self.symbol or not self.symbol.strip():
            raise ValidationError("symbol", self.symbol, "Symbol cannot be empty")
        
        # Line number validation
        if self.start_line < 1:
            raise ValidationError("start_line", self.start_line, "Start line must be positive")
        
        if self.end_line < 1:
            raise ValidationError("end_line", self.end_line, "End line must be positive")
        
        if self.start_line > self.end_line:
            raise ValidationError(
                "line_range", 
                f"{self.start_line}-{self.end_line}", 
                "Start line cannot be greater than end line"
            )
        
        # Code validation
        if not self.code:
            raise ValidationError("code", self.code, "Code content cannot be empty")
        
        # Byte offset validation (if provided)
        if self.start_byte is not None and self.start_byte < 0:
            raise ValidationError("start_byte", self.start_byte, "Start byte cannot be negative")
        
        if self.end_byte is not None and self.end_byte < 0:
            raise ValidationError("end_byte", self.end_byte, "End byte cannot be negative")
        
        if (self.start_byte is not None and self.end_byte is not None and 
            self.start_byte > self.end_byte):
            raise ValidationError(
                "byte_range",
                f"{self.start_byte}-{self.end_byte}",
                "Start byte cannot be greater than end byte"
            )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        """Create a Chunk model from a dictionary.
        
        This method provides backward compatibility with existing code that
        uses dictionary representations of chunks.
        
        Args:
            data: Dictionary containing chunk data
            
        Returns:
            Chunk model created from dictionary data
            
        Raises:
            ValidationError: If required fields are missing or invalid
        """
        try:
            # Extract required fields
            symbol = data.get("symbol")
            if not symbol:
                raise ValidationError("symbol", symbol, "Symbol is required")
            
            start_line = data.get("start_line")
            if start_line is None:
                raise ValidationError("start_line", start_line, "Start line is required")
            
            end_line = data.get("end_line")
            if end_line is None:
                raise ValidationError("end_line", end_line, "End line is required")
            
            code = data.get("code")
            if not code:
                raise ValidationError("code", code, "Code content is required")
            
            file_id = data.get("file_id")
            if file_id is None:
                raise ValidationError("file_id", file_id, "File ID is required")
            
            # Handle chunk_type - could be string or ChunkType enum
            chunk_type_value = data.get("chunk_type", data.get("type"))
            if isinstance(chunk_type_value, ChunkType):
                chunk_type = chunk_type_value
            elif isinstance(chunk_type_value, str):
                chunk_type = ChunkType.from_string(chunk_type_value)
            else:
                chunk_type = ChunkType.UNKNOWN
            
            # Handle language - could be string or Language enum
            language_value = data.get("language", data.get("language_info"))
            if isinstance(language_value, Language):
                language = language_value
            elif isinstance(language_value, str):
                language = Language.from_string(language_value)
            else:
                language = Language.UNKNOWN
            
            # Handle optional fields
            chunk_id = data.get("id")
            if chunk_id is not None:
                chunk_id = ChunkId(chunk_id)
            
            file_path = data.get("file_path", data.get("path"))
            if file_path:
                file_path = FilePath(file_path)
            
            parent_header = data.get("parent_header")
            
            start_byte = data.get("start_byte")
            if start_byte is not None:
                start_byte = ByteOffset(start_byte)
            
            end_byte = data.get("end_byte")
            if end_byte is not None:
                end_byte = ByteOffset(end_byte)
            
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            
            updated_at = data.get("updated_at")
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            
            return cls(
                id=chunk_id,
                symbol=symbol,
                start_line=LineNumber(int(start_line)),
                end_line=LineNumber(int(end_line)),
                code=code,
                chunk_type=chunk_type,
                file_id=FileId(file_id),
                language=language,
                file_path=file_path,
                parent_header=parent_header,
                start_byte=start_byte,
                end_byte=end_byte,
                created_at=created_at,
                updated_at=updated_at
            )
            
        except (ValueError, TypeError) as e:
            raise ValidationError("data", data, f"Invalid data format: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Chunk model to dictionary.
        
        This method provides backward compatibility with existing code that
        expects dictionary representations of chunks.
        
        Returns:
            Dictionary representation of the chunk
        """
        result = {
            "symbol": self.symbol,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code,
            "chunk_type": self.chunk_type.value,
            "file_id": self.file_id,
            "language": self.language.value,
        }
        
        if self.id is not None:
            result["id"] = self.id
        
        if self.file_path is not None:
            result["file_path"] = self.file_path
        
        if self.parent_header is not None:
            result["parent_header"] = self.parent_header
        
        if self.start_byte is not None:
            result["start_byte"] = self.start_byte
        
        if self.end_byte is not None:
            result["end_byte"] = self.end_byte
        
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at.isoformat()
        
        return result
    
    @property
    def line_count(self) -> int:
        """Get the number of lines in this chunk."""
        return self.end_line - self.start_line + 1
    
    @property
    def char_count(self) -> int:
        """Get the number of characters in the code content."""
        return len(self.code)
    
    @property
    def byte_count(self) -> Optional[int]:
        """Get the number of bytes in this chunk (if byte offsets are available)."""
        if self.start_byte is not None and self.end_byte is not None:
            return self.end_byte - self.start_byte + 1
        return None
    
    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this chunk."""
        if self.chunk_type.is_code:
            return f"{self.chunk_type.value}: {self.symbol}"
        else:
            # For documentation chunks, show truncated content
            content_preview = self.code[:50].replace('\n', ' ').strip()
            if len(self.code) > 50:
                content_preview += "..."
            return f"{self.chunk_type.value}: {content_preview}"
    
    @property
    def relative_path(self) -> Optional[str]:
        """Get relative file path (if available)."""
        if self.file_path:
            try:
                return str(Path(self.file_path).relative_to(Path.cwd()))
            except ValueError:
                return self.file_path
        return None
    
    def is_code_chunk(self) -> bool:
        """Check if this chunk represents code structure."""
        return self.chunk_type.is_code
    
    def is_documentation_chunk(self) -> bool:
        """Check if this chunk represents documentation."""
        return self.chunk_type.is_documentation
    
    def is_small_chunk(self, min_lines: int = 3) -> bool:
        """Check if this chunk is considered small.
        
        Args:
            min_lines: Minimum line count threshold
            
        Returns:
            True if chunk has fewer lines than threshold
        """
        return self.line_count < min_lines
    
    def is_large_chunk(self, max_lines: int = 500) -> bool:
        """Check if this chunk is considered large.
        
        Args:
            max_lines: Maximum line count threshold
            
        Returns:
            True if chunk has more lines than threshold
        """
        return self.line_count > max_lines
    
    def contains_line(self, line_number: LineNumber) -> bool:
        """Check if the given line number is within this chunk.
        
        Args:
            line_number: Line number to check (1-based)
            
        Returns:
            True if line is within chunk boundaries
        """
        return self.start_line <= line_number <= self.end_line
    
    def overlaps_with(self, other: "Chunk") -> bool:
        """Check if this chunk overlaps with another chunk.
        
        Args:
            other: Another chunk to compare with
            
        Returns:
            True if chunks overlap in line ranges
        """
        return not (self.end_line < other.start_line or other.end_line < self.start_line)
    
    def with_id(self, chunk_id: ChunkId) -> "Chunk":
        """Create a new Chunk instance with the specified ID.
        
        Args:
            chunk_id: Chunk ID to set
            
        Returns:
            New Chunk instance with the ID set
        """
        return Chunk(
            id=chunk_id,
            symbol=self.symbol,
            start_line=self.start_line,
            end_line=self.end_line,
            code=self.code,
            chunk_type=self.chunk_type,
            file_id=self.file_id,
            language=self.language,
            file_path=self.file_path,
            parent_header=self.parent_header,
            start_byte=self.start_byte,
            end_byte=self.end_byte,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
    
    def with_file_path(self, file_path: FilePath) -> "Chunk":
        """Create a new Chunk instance with the specified file path.
        
        Args:
            file_path: File path to set
            
        Returns:
            New Chunk instance with the file path set
        """
        return Chunk(
            id=self.id,
            symbol=self.symbol,
            start_line=self.start_line,
            end_line=self.end_line,
            code=self.code,
            chunk_type=self.chunk_type,
            file_id=self.file_id,
            language=self.language,
            file_path=file_path,
            parent_header=self.parent_header,
            start_byte=self.start_byte,
            end_byte=self.end_byte,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
    
    def __str__(self) -> str:
        """Return string representation of the chunk."""
        location = f"{self.relative_path or 'unknown'}:{self.start_line}-{self.end_line}"
        return f"Chunk(id={self.id}, {self.chunk_type.value}: {self.symbol} @ {location})"
    
    def __repr__(self) -> str:
        """Return detailed string representation of the chunk."""
        return (
            f"Chunk(id={self.id}, symbol='{self.symbol}', "
            f"type={self.chunk_type.value}, file_id={self.file_id}, "
            f"lines={self.start_line}-{self.end_line}, "
            f"language={self.language.value})"
        )