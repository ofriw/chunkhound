"""Database module for ChunkHound - DuckDB connection and schema management."""

from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import duckdb
from loguru import logger

class Database:
    """Database connection manager with DuckDB and vss extension."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = db_path
        self.connection: Optional[Any] = None

    def connect(self) -> None:
        """Connect to DuckDB and load required extensions."""
        logger.info(f"Connecting to database: {self.db_path}")

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if duckdb is None:
                raise ImportError("duckdb not available")
            # Connect to DuckDB
            self.connection = duckdb.connect(str(self.db_path))
            logger.info("DuckDB connection established")

            # Load required extensions
            self._load_extensions()

            # Enable experimental HNSW persistence for disk-based databases
            if self.connection is not None:
                self.connection.execute("SET hnsw_enable_experimental_persistence = true")
                logger.debug("HNSW experimental persistence enabled")

            # Create schema
            self._create_schema()

            logger.info("Database initialization complete")

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def _load_extensions(self) -> None:
        """Load required DuckDB extensions."""
        logger.info("Loading DuckDB extensions")

        try:
            # Install and load vss extension for vector search
            if self.connection is not None:
                self.connection.execute("INSTALL vss")
                self.connection.execute("LOAD vss")
                logger.info("VSS extension loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load extensions: {e}")
            raise

    def _create_schema(self) -> None:
        """Create database schema for files, chunks, and embeddings."""
        logger.info("Creating database schema")

        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Create files table with sequence
            self.connection.execute("CREATE SEQUENCE IF NOT EXISTS files_id_seq")
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY DEFAULT nextval('files_id_seq'),
                    path TEXT UNIQUE NOT NULL,
                    mtime TIMESTAMP NOT NULL,
                    language TEXT,
                    size_bytes BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("Files table created")

            # Create chunks table with sequence
            self.connection.execute("CREATE SEQUENCE IF NOT EXISTS chunks_id_seq")
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY DEFAULT nextval('chunks_id_seq'),
                    file_id INTEGER NOT NULL REFERENCES files(id),
                    symbol TEXT,
                    start_line INT NOT NULL,
                    end_line INT NOT NULL,
                    code TEXT NOT NULL,
                    chunk_type TEXT,  -- 'function', 'class', 'method', 'block'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("Chunks table created")

            # Create embeddings table
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dims INT NOT NULL,
                    vector FLOAT[1536] NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chunk_id, provider, model)
                )
            """)
            logger.debug("Embeddings table created")

            # Create indexes for performance
            self._create_indexes()

            logger.info("Database schema created successfully")

        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise

    def _create_indexes(self) -> None:
        """Create database indexes for performance."""
        logger.info("Creating database indexes")

        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Index on file path for fast lookups
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)
            """)

            # Index on file modification time for incremental updates
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime)
            """)

            # Index on chunks file_id for joins
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id)
            """)

            # Index on chunk symbol for symbol-based searches
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_symbol ON chunks(symbol)
            """)

            # Index on embeddings for provider/model lookups
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_provider_model
                ON embeddings(provider, model)
            """)

            logger.debug("Standard indexes created")

        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise

    def create_hnsw_index(self, provider: str, model: str, dims: int, metric: str = "cosine") -> None:
        """Create HNSW index for specific provider/model/dims combination.

        Args:
            provider: Embedding provider name (e.g., "openai")
            model: Model name (e.g., "text-embedding-3-small")
            dims: Vector dimensions (e.g., 1536)
            metric: Distance metric ("cosine", "l2sq", "ip")
        """
        index_name = f"hnsw_{provider}_{model}_{dims}_{metric}".replace("-", "_").replace(".", "_")

        logger.info(f"Creating HNSW index: {index_name}")

        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Check if we have any embeddings for this provider/model/dims
            result = self.connection.execute("""
                SELECT COUNT(*) as count
                FROM embeddings
                WHERE provider = ? AND model = ? AND dims = ?
            """, [provider, model, dims]).fetchone()

            if result[0] == 0:
                logger.warning(f"No embeddings found for {provider}/{model}/{dims}, skipping HNSW index")
                return

            # Create HNSW index on vector column (no WHERE clause - DuckDB doesn't support partial indexes)
            self.connection.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON embeddings
                USING HNSW (vector)
                WITH (metric = '{metric}')
            """)

            logger.info(f"HNSW index {index_name} created successfully")

        except Exception as e:
            logger.error(f"Failed to create HNSW index {index_name}: {e}")
            raise

    def insert_file(self, path: str, mtime: Union[str, float], language: str, size_bytes: int) -> int:
        """Insert or update a file record.

        Args:
            path: File path
            mtime: Modification time (Unix timestamp)
            language: Programming language
            size_bytes: File size in bytes

        Returns:
            File ID
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Try to get existing file
            existing = self.connection.execute(
                "SELECT id FROM files WHERE path = ?", [path]
            ).fetchone()

            if existing:
                # Update existing
                self.connection.execute("""
                    UPDATE files
                    SET mtime = ?::TIMESTAMP, language = ?, size_bytes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE path = ?
                """, [mtime, language, size_bytes, path])
                return existing[0]
            else:
                # Insert new - use simple auto-increment
                result = self.connection.execute("""
                    INSERT INTO files (path, mtime, language, size_bytes)
                    VALUES (?, ?::TIMESTAMP, ?, ?)
                    RETURNING id
                """, [path, mtime, language, size_bytes]).fetchone()
                return result[0]

        except Exception as e:
            logger.error(f"Failed to insert file {path}: {e}")
            raise

    def insert_chunk(self, file_id: int, symbol: str, start_line: int, end_line: int,
                    code: str, chunk_type: str) -> int:
        """Insert a code chunk.

        Args:
            file_id: ID of the parent file
            symbol: Symbol name (function/class name)
            start_line: Starting line number
            end_line: Ending line number
            code: Code content
            chunk_type: Type of chunk ('function', 'class', 'method', 'block')

        Returns:
            Chunk ID
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            result = self.connection.execute("""
                INSERT INTO chunks (file_id, symbol, start_line, end_line, code, chunk_type)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
            """, [file_id, symbol, start_line, end_line, code, chunk_type]).fetchone()

            return result[0]

        except Exception as e:
            logger.error(f"Failed to insert chunk {symbol}: {e}")
            raise

    def insert_embedding(self, chunk_id: int, provider: str, model: str,
                        dims: int, vector: List[float]) -> None:
        """Insert an embedding vector.

        Args:
            chunk_id: ID of the chunk
            provider: Embedding provider
            model: Model name
            dims: Vector dimensions
            vector: Embedding vector
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            self.connection.execute("""
                INSERT OR REPLACE INTO embeddings (chunk_id, provider, model, dims, vector)
                VALUES (?, ?, ?, ?, ?)
            """, [chunk_id, provider, model, dims, vector])

        except Exception as e:
            logger.error(f"Failed to insert embedding for chunk {chunk_id}: {e}")
            raise

    def search_semantic(self, query_vector: List[float], provider: str, model: str,
                       limit: int = 10, threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity.

        Args:
            query_vector: Query embedding vector
            provider: Embedding provider
            model: Model name
            limit: Maximum number of results
            threshold: Distance threshold (optional)

        Returns:
            List of search results with metadata
        """
        try:
            # Build query with optional threshold
            where_clause = "WHERE e.provider = ? AND e.model = ?"
            params: List[Any] = [provider, model]

            if threshold is not None:
                where_clause += " AND array_distance(e.vector, ?::FLOAT[1536]) <= ?"
                params.append(query_vector)
                params.append(threshold)

            query = f"""
                SELECT
                    c.id as chunk_id,
                    c.symbol,
                    c.start_line,
                    c.end_line,
                    c.code,
                    c.chunk_type,
                    f.path,
                    f.language,
                    array_distance(e.vector, ?::FLOAT[1536]) as distance
                FROM embeddings e
                JOIN chunks c ON e.chunk_id = c.id
                JOIN files f ON c.file_id = f.id
                {where_clause}
                ORDER BY array_distance(e.vector, ?::FLOAT[1536])
                LIMIT ?
            """

            # Add query vector twice (for SELECT and ORDER BY) plus limit
            all_params = [query_vector] + params + [query_vector, limit]

            if self.connection is None:
                raise RuntimeError("Database connection not established")

            results = self.connection.execute(query, all_params).fetchall()

            # Convert to dictionaries
            return [
                {
                    "chunk_id": row[0],
                    "symbol": row[1],
                    "start_line": row[2],
                    "end_line": row[3],
                    "code": row[4],
                    "chunk_type": row[5],
                    "file_path": row[6],
                    "language": row[7],
                    "distance": row[8]
                }
                for row in results
            ]

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise

    def search_regex(self, pattern: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform regex search on code content.

        Args:
            pattern: Regular expression pattern
            limit: Maximum number of results

        Returns:
            List of search results
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            results = self.connection.execute("""
                SELECT
                    c.id as chunk_id,
                    c.symbol,
                    c.start_line,
                    c.end_line,
                    c.code,
                    c.chunk_type,
                    f.path,
                    f.language
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE regexp_matches(c.code, ?)
                ORDER BY f.path, c.start_line
                LIMIT ?
            """, [pattern, limit]).fetchall()

            # Convert to dictionaries
            return [
                {
                    "chunk_id": row[0],
                    "symbol": row[1],
                    "start_line": row[2],
                    "end_line": row[3],
                    "code": row[4],
                    "chunk_type": row[5],
                    "file_path": row[6],
                    "language": row[7]
                }
                for row in results
            ]

        except Exception as e:
            logger.error(f"Regex search failed: {e}")
            raise

    def get_file_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file record by path.

        Args:
            path: File path

        Returns:
            File record or None if not found
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            result = self.connection.execute("""
                SELECT id, path, mtime, language, size_bytes
                FROM files
                WHERE path = ?
            """, [path]).fetchone()

            if result:
                return {
                    "id": result[0],
                    "path": result[1],
                    "mtime": result[2],
                    "language": result[3],
                    "size_bytes": result[4]
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get file {path}: {e}")
            raise

    def delete_file_chunks(self, file_id: int) -> None:
        """Delete all chunks for a file (cascades to embeddings).

        Args:
            file_id: File ID
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            self.connection.execute("DELETE FROM chunks WHERE file_id = ?", [file_id])

        except Exception as e:
            logger.error(f"Failed to delete chunks for file {file_id}: {e}")
            raise

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics.

        Returns:
            Dictionary with counts of files, chunks, and embeddings
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            files_count = self.connection.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            chunks_count = self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embeddings_count = self.connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

            return {
                "files": files_count,
                "chunks": chunks_count,
                "embeddings": embeddings_count
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")
