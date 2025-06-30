"""DuckDB chunk repository implementation - handles chunk CRUD operations."""

from typing import Any, TYPE_CHECKING

from loguru import logger

from core.models import Chunk
from core.types import ChunkType, Language

if TYPE_CHECKING:
    from providers.database.duckdb.connection_manager import DuckDBConnectionManager


class DuckDBChunkRepository:
    """Repository for chunk CRUD operations in DuckDB."""

    def __init__(self, connection_manager: "DuckDBConnectionManager"):
        """Initialize chunk repository.
        
        Args:
            connection_manager: DuckDB connection manager instance
        """
        self._connection_manager = connection_manager

    @property
    def connection(self) -> Any | None:
        """Get database connection from connection manager."""
        return self._connection_manager.connection
    
    def _get_connection(self) -> Any:
        """Get thread-safe connection for database operations."""
        import os
        # Use thread-safe connection in MCP mode
        if os.environ.get("CHUNKHOUND_MCP_MODE") and hasattr(self._connection_manager, 'get_thread_safe_connection'):
            return self._connection_manager.get_thread_safe_connection()
        # Fallback to main connection for backwards compatibility
        return self._connection_manager.connection

    def insert_chunk(self, chunk: Chunk) -> int:
        """Insert chunk record and return chunk ID."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            result = self._get_connection().execute("""
                INSERT INTO chunks (file_id, chunk_type, symbol, code, start_line, end_line,
                                  start_byte, end_byte, size, signature, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, [
                chunk.file_id,
                chunk.chunk_type.value if chunk.chunk_type else None,
                chunk.symbol,
                chunk.code,
                chunk.start_line,
                chunk.end_line,
                chunk.start_byte,
                chunk.end_byte,
                len(chunk.code),
                getattr(chunk, 'signature', None),
                chunk.language.value if chunk.language else None
            ]).fetchone()

            return result[0] if result else 0

        except Exception as e:
            logger.error(f"Failed to insert chunk: {e}")
            raise

    def insert_chunks_batch(self, chunks: list[Chunk]) -> list[int]:
        """Insert multiple chunks in batch using optimized DuckDB bulk loading."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        if not chunks:
            return []

        try:
            # Prepare values for bulk INSERT statement
            values_clauses = []
            params = []
            
            for chunk in chunks:
                values_clauses.append("(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
                params.extend([
                    chunk.file_id,
                    chunk.chunk_type.value if chunk.chunk_type else None,
                    chunk.symbol,
                    chunk.code,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.start_byte,
                    chunk.end_byte,
                    len(chunk.code),
                    getattr(chunk, 'signature', None),
                    chunk.language.value if chunk.language else None,
                ])

            # Use single bulk INSERT with RETURNING for optimal performance
            values_sql = ", ".join(values_clauses)
            query = f"""
                INSERT INTO chunks (file_id, chunk_type, symbol, code, start_line, end_line,
                                  start_byte, end_byte, size, signature, language)
                VALUES {values_sql}
                RETURNING id
            """
            
            # Execute bulk insert and get all IDs in one operation
            results = self._get_connection().execute(query, params).fetchall()
            chunk_ids = [result[0] for result in results]
            
            # Track batch operation for checkpoint management  
            self._connection_manager._operations_since_checkpoint += len(chunks)
            self._connection_manager._maybe_checkpoint()
            
            return chunk_ids

        except Exception as e:
            logger.error(f"Failed to insert chunks batch: {e}")
            raise

    def get_chunk_by_id(self, chunk_id: int, as_model: bool = False) -> dict[str, Any] | Chunk | None:
        """Get chunk record by ID."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            result = self._get_connection().execute("""
                SELECT id, file_id, chunk_type, symbol, code, start_line, end_line,
                       start_byte, end_byte, size, signature, language, created_at, updated_at
                FROM chunks WHERE id = ?
            """, [chunk_id]).fetchone()

            if not result:
                return None

            chunk_dict = {
                "id": result[0],
                "file_id": result[1],
                "chunk_type": result[2],
                "symbol": result[3],
                "code": result[4],
                "start_line": result[5],
                "end_line": result[6],
                "start_byte": result[7],
                "end_byte": result[8],
                "size": result[9],
                "signature": result[10],
                "language": result[11],
                "created_at": result[12],
                "updated_at": result[13]
            }

            if as_model:
                return Chunk(
                    file_id=result[1],
                    chunk_type=ChunkType(result[2]) if result[2] else ChunkType.UNKNOWN,
                    symbol=result[3],
                    code=result[4],
                    start_line=result[5],
                    end_line=result[6],
                    start_byte=result[7],
                    end_byte=result[8],
                    language=Language(result[11]) if result[11] else Language.UNKNOWN
                )

            return chunk_dict

        except Exception as e:
            logger.error(f"Failed to get chunk by ID {chunk_id}: {e}")
            return None

    def get_chunks_by_file_id(self, file_id: int, as_model: bool = False) -> list[dict[str, Any] | Chunk]:
        """Get all chunks for a specific file."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            results = self._get_connection().execute("""
                SELECT id, file_id, chunk_type, symbol, code, start_line, end_line,
                       start_byte, end_byte, size, signature, language, created_at, updated_at
                FROM chunks WHERE file_id = ?
                ORDER BY start_line
            """, [file_id]).fetchall()

            chunks = []
            for result in results:
                chunk_dict = {
                    "id": result[0],
                    "file_id": result[1],
                    "chunk_type": result[2],
                    "symbol": result[3],
                    "code": result[4],
                    "start_line": result[5],
                    "end_line": result[6],
                    "start_byte": result[7],
                    "end_byte": result[8],
                    "size": result[9],
                    "signature": result[10],
                    "language": result[11],
                    "created_at": result[12],
                    "updated_at": result[13]
                }

                if as_model:
                    chunks.append(Chunk(
                        file_id=result[1],
                        chunk_type=ChunkType(result[2]) if result[2] else ChunkType.UNKNOWN,
                        symbol=result[3],
                        code=result[4],
                        start_line=result[5],
                        end_line=result[6],
                        start_byte=result[7],
                        end_byte=result[8],
                        language=Language(result[11]) if result[11] else Language.UNKNOWN
                    ))
                else:
                    chunks.append(chunk_dict)

            return chunks

        except Exception as e:
            logger.error(f"Failed to get chunks for file {file_id}: {e}")
            return []

    def delete_file_chunks(self, file_id: int) -> None:
        """Delete all chunks for a file."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Get list of chunk IDs for explicit deletion
            chunk_ids_result = self._get_connection().execute(
                "SELECT id FROM chunks WHERE file_id = ?", [file_id]
            ).fetchall()
            
            if not chunk_ids_result:
                return  # No chunks to delete
                
            chunk_ids = [row[0] for row in chunk_ids_result]
            
            # Delete embeddings first using explicit chunk IDs to ensure complete removal
            for table_name in self._connection_manager._get_all_embedding_tables():
                # Use explicit chunk IDs instead of subquery to avoid potential issues
                placeholders = ','.join(['?'] * len(chunk_ids))
                self._get_connection().execute(f"""
                    DELETE FROM {table_name}
                    WHERE chunk_id IN ({placeholders})
                """, chunk_ids)

            # Then delete all chunks using explicit IDs
            placeholders = ','.join(['?'] * len(chunk_ids))
            self._get_connection().execute(f"DELETE FROM chunks WHERE id IN ({placeholders})", chunk_ids)

        except Exception as e:
            logger.error(f"Failed to delete chunks for file {file_id}: {e}")
            raise

    def delete_chunk(self, chunk_id: int) -> None:
        """Delete a single chunk by ID."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Delete embeddings for this chunk first
            for table_name in self._connection_manager._get_all_embedding_tables():
                self._get_connection().execute(f"""
                    DELETE FROM {table_name} WHERE chunk_id = ?
                """, [chunk_id])

            # Then delete the chunk itself
            self._get_connection().execute("DELETE FROM chunks WHERE id = ?", [chunk_id])

        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id}: {e}")
            raise

    def update_chunk(self, chunk_id: int, **kwargs) -> None:
        """Update chunk record with new values."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        if not kwargs:
            return

        try:
            # Build dynamic update query
            set_clauses = []
            values = []

            valid_fields = ["chunk_type", "symbol", "code", "start_line", "end_line",
                          "start_byte", "end_byte", "signature", "language"]

            for key, value in kwargs.items():
                if key in valid_fields:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)

            if set_clauses:
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                values.append(chunk_id)

                query = f"UPDATE chunks SET {', '.join(set_clauses)} WHERE id = ?"
                self._get_connection().execute(query, values)

        except Exception as e:
            logger.error(f"Failed to update chunk {chunk_id}: {e}")
            raise

    def get_all_chunks_with_metadata(self) -> list[dict[str, Any]]:
        """Get all chunks with their metadata including file paths (provider-agnostic)."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Use SQL to get chunks with file paths (DuckDB approach)
            query = """
                SELECT c.id, c.file_id, f.path as file_path, c.code, 
                       c.start_line, c.end_line, c.chunk_type, c.language, c.symbol
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                ORDER BY c.id
            """
            
            results = self._get_connection().execute(query).fetchall()
            
            # Convert to list of dictionaries
            result = []
            for row in results:
                result.append({
                    'id': row[0],
                    'file_id': row[1], 
                    'file_path': row[2],
                    'content': row[3],
                    'start_line': row[4],
                    'end_line': row[5],
                    'chunk_type': row[6],
                    'language': row[7],
                    'name': row[8]
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to get all chunks with metadata: {e}")
            return []