"""Database module for ChunkHound - DuckDB connection and schema management."""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import duckdb
from loguru import logger

from .parser import CodeParser
from .chunker import Chunker
from .embeddings import EmbeddingManager

class Database:
    """Database connection manager with DuckDB and vss extension."""

    def __init__(self, db_path: Union[Path, str], embedding_manager: Optional[EmbeddingManager] = None):
        """Initialize database connection.

        Args:
            db_path: Path to DuckDB database file or ":memory:" for in-memory database
            embedding_manager: Optional embedding manager for vector generation
        """
        self.db_path = db_path
        self.connection: Optional[Any] = None
        self.embedding_manager = embedding_manager

    def connect(self) -> None:
        """Connect to DuckDB and load required extensions."""
        logger.info(f"Connecting to database: {self.db_path}")

        # Ensure parent directory exists for file-based databases
        if isinstance(self.db_path, Path):
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
                    chunk_type TEXT,  -- 'function', 'class', 'method', 'block', 'header_1', 'header_2', 'header_3', 'header_4', 'header_5', 'header_6', 'code_block', 'paragraph'
                    language_info TEXT,  -- Additional language/type information (e.g., 'python', 'javascript', 'markdown')
                    parent_header TEXT,  -- For nested content, reference to parent header
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
                # File exists - return existing ID, mtime will be updated after chunk cleanup
                return existing[0]
            else:
                # Insert new - use simple auto-increment
                result = self.connection.execute("""
                    INSERT INTO files (path, mtime, language, size_bytes)
                    VALUES (?, to_timestamp(?), ?, ?)
                    RETURNING id
                """, [path, mtime, language, size_bytes]).fetchone()
                return result[0]

        except Exception as e:
            logger.error(f"Failed to insert file {path}: {e}")
            raise

    def insert_chunk(self, file_id: int, symbol: str, start_line: int, end_line: int,
                    code: str, chunk_type: str, language_info: Optional[str] = None,
                    parent_header: Optional[str] = None) -> int:
        """Insert a code chunk.

        Args:
            file_id: ID of the parent file
            symbol: Symbol name (function/class name)
            start_line: Starting line number
            end_line: Ending line number
            code: Code content
            chunk_type: Type of chunk ('function', 'class', 'method', 'block', 'header_1', etc.)
            language_info: Additional language/type information
            parent_header: Reference to parent header for nested content

        Returns:
            Chunk ID
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            result = self.connection.execute("""
                INSERT INTO chunks (file_id, symbol, start_line, end_line, code, chunk_type, language_info, parent_header)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, [file_id, symbol, start_line, end_line, code, chunk_type, language_info, parent_header]).fetchone()

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
        """Delete all chunks for a file (manual cascade for embeddings).

        Args:
            file_id: File ID
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # First delete embeddings to avoid foreign key constraint violations
            self.connection.execute("""
                DELETE FROM embeddings 
                WHERE chunk_id IN (SELECT id FROM chunks WHERE file_id = ?)
            """, [file_id])

            # Then delete chunks
            self.connection.execute("DELETE FROM chunks WHERE file_id = ?", [file_id])
            
            logger.debug(f"Deleted chunks and embeddings for file {file_id}")

        except Exception as e:
            logger.error(f"Failed to delete chunks for file {file_id}: {e}")
            raise

    def delete_file_completely(self, file_path: str) -> bool:
        """Delete a file and all its chunks/embeddings completely.

        Args:
            file_path: Path to the file to delete

        Returns:
            True if file was deleted, False if not found
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Get file ID
            existing = self.connection.execute(
                "SELECT id FROM files WHERE path = ?", [file_path]
            ).fetchone()

            if not existing:
                return False

            file_id = existing[0]

            # Delete chunks and embeddings first
            self.delete_file_chunks(file_id)

            # Delete the file record
            self.connection.execute("DELETE FROM files WHERE id = ?", [file_id])
            
            logger.debug(f"Completely deleted file {file_path} and all associated data")
            return True

        except Exception as e:
            logger.error(f"Failed to completely delete file {file_path}: {e}")
            raise

    def execute_query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as dictionaries.
        
        Args:
            query: SQL query string
            params: Optional list of parameters for the query
            
        Returns:
            List of dictionaries with column names as keys
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            if params is None:
                params = []

            results = self.connection.execute(query, params).fetchall()

            # Get column names from the connection description
            # DuckDB cursor description format: [(name, type_info), ...]
            column_names = [desc[0] for desc in self.connection.description]

            # Convert to dictionaries
            return [
                {column_names[i]: row[i] for i in range(len(column_names))}
                for row in results
            ]

        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
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

    async def process_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a file end-to-end: parse, chunk, and store in database.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                raise ValueError(f"File not found or not readable: {file_path}")
            
            # Determine file language based on extension
            suffix = file_path.suffix.lower()
            if suffix == '.py':
                language = "python"
            elif suffix in ['.md', '.markdown']:
                language = "markdown"
            elif suffix == '.java':
                language = "java"
            else:
                logger.debug(f"Skipping unsupported file type: {file_path}")
                return {"status": "skipped", "reason": "unsupported_type", "chunks": 0}
            
            # Get file metadata
            stat = file_path.stat()
            mtime = stat.st_mtime
            size_bytes = stat.st_size
            
            # Check if file needs to be reprocessed
            existing_file = self.get_file_by_path(str(file_path))
            if existing_file and existing_file["mtime"]:
                existing_mtime = existing_file["mtime"].timestamp()
                # Use tolerance for floating-point precision (1 second tolerance)
                if abs(existing_mtime - mtime) < 1.0:
                    logger.debug(f"File {file_path} is up to date, skipping")
                    return {"status": "up_to_date", "chunks": 0}
                else:
                    logger.debug(f"File {file_path} modified (existing: {existing_mtime}, current: {mtime}), reprocessing")
            
            # Initialize parser and chunker
            parser = CodeParser()
            parser.setup()
            chunker = Chunker()
            
            # Parse the file
            parsed_data = parser.parse_file(file_path)
            if not parsed_data:
                logger.debug(f"No parseable content in {file_path}")
                return {"status": "no_content", "chunks": 0}
            
            # Create chunks
            chunks = chunker.chunk_file(file_path, parsed_data)
            if not chunks:
                logger.debug(f"No chunks created from {file_path}")
                return {"status": "no_chunks", "chunks": 0}
            
            # Store in database
            file_id = self.insert_file(
                path=str(file_path),
                mtime=mtime,
                language=language,
                size_bytes=size_bytes
            )
            
            # If file was updated, delete old chunks and update file record
            if existing_file:
                logger.debug(f"Deleting old chunks for updated file {file_path}")
                self.delete_file_chunks(file_id)
                
                # Now update the file record with new mtime
                self.connection.execute("""
                    UPDATE files 
                    SET mtime = to_timestamp(?), language = ?, size_bytes = ? 
                    WHERE id = ?
                """, [mtime, language, size_bytes, file_id])
                logger.debug(f"Updated file record for {file_path}")
            
            # Insert new chunks
            chunk_ids = []
            for chunk in chunks:
                chunk_id = self.insert_chunk(
                    file_id=file_id,
                    symbol=chunk["symbol"],
                    start_line=chunk["start_line"],
                    end_line=chunk["end_line"],
                    code=chunk["code"],
                    chunk_type=chunk["chunk_type"],
                    language_info=chunk.get("language_info"),
                    parent_header=chunk.get("parent_header")
                )
                chunk_ids.append(chunk_id)

            # Generate embeddings if embedding manager is available
            embeddings_generated = 0
            if self.embedding_manager and chunk_ids:
                try:
                    embeddings_generated = await self._generate_embeddings_for_chunks(chunk_ids, chunks)
                except Exception as e:
                    logger.warning(f"Failed to generate embeddings for {file_path}: {e}")

            logger.info(f"Successfully processed {file_path}: {len(chunks)} chunks, {embeddings_generated} embeddings")
            return {
                "status": "success",
                "file_id": file_id,
                "chunks": len(chunks),
                "chunk_ids": chunk_ids,
                "embeddings": embeddings_generated
            }
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return {"status": "error", "error": str(e), "chunks": 0}

    async def process_directory(self, directory: Path, patterns: Optional[List[str]] = None, exclude_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Process all supported files in a directory.
        
        Args:
            directory: Directory to process
            patterns: List of glob patterns for files to process
            exclude_patterns: List of glob patterns to exclude
            
        Returns:
            Dictionary with processing summary
        """
        if patterns is None:
            patterns = ["**/*.py"]
        try:
            logger.info(f"Processing directory: {directory} with patterns: {patterns}")
            if exclude_patterns:
                logger.info(f"Exclude patterns: {exclude_patterns}")
            
            # Find all matching files from all patterns
            files = []
            for pattern in patterns:
                files.extend(directory.glob(pattern))
            
            # Remove duplicates while preserving order
            seen = set()
            unique_files = []
            for file_path in files:
                if file_path not in seen:
                    seen.add(file_path)
                    unique_files.append(file_path)
            files = unique_files
            
            # Filter out excluded files
            if exclude_patterns:
                from fnmatch import fnmatch
                filtered_files = []
                for file_path in files:
                    # Convert to relative path from directory for pattern matching
                    rel_path = file_path.relative_to(directory)
                    excluded = False
                    for exclude_pattern in exclude_patterns:
                        if fnmatch(str(rel_path), exclude_pattern) or fnmatch(str(file_path), exclude_pattern):
                            excluded = True
                            break
                    if not excluded:
                        filtered_files.append(file_path)
                files = filtered_files
            
            if not files:
                logger.warning(f"No files found matching patterns {patterns} in {directory}")
                return {"status": "no_files", "processed": 0, "errors": 0}
            
            # Process each file
            results = {"processed": 0, "errors": 0, "skipped": 0, "total_chunks": 0}
            
            for file_path in files:
                result = await self.process_file(file_path)
                
                if result["status"] == "success":
                    results["processed"] += 1
                    results["total_chunks"] += result["chunks"]
                elif result["status"] == "error":
                    results["errors"] += 1
                else:
                    results["skipped"] += 1
            
            logger.info(f"Directory processing complete: {results}")
            return {"status": "complete", **results}
            
        except Exception as e:
            logger.error(f"Failed to process directory {directory}: {e}")
            return {"status": "error", "error": str(e)}

    async def _generate_embeddings_for_chunks(self, chunk_ids: List[int], chunks: List[Dict[str, Any]]) -> int:
        """Generate embeddings for a list of chunks.
        
        Args:
            chunk_ids: List of chunk IDs from database
            chunks: List of chunk data dictionaries
            
        Returns:
            Number of embeddings generated
        """
        if not self.embedding_manager:
            return 0
            
        try:
            # Extract code text from chunks
            texts = [chunk["code"] for chunk in chunks]
            
            # Generate embeddings
            result = await self.embedding_manager.embed_texts(texts)
            
            # Store embeddings in database
            stored_count = 0
            for chunk_id, embedding in zip(chunk_ids, result.embeddings):
                try:
                    self.insert_embedding(
                        chunk_id=chunk_id,
                        provider=result.provider,
                        model=result.model,
                        dims=result.dims,
                        vector=embedding
                    )
                    stored_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store embedding for chunk {chunk_id}: {e}")
            
            return stored_count
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return 0

    async def generate_missing_embeddings(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate embeddings for chunks that don't have them yet.
        
        Args:
            provider_name: Specific provider to use (uses default if None)
            
        Returns:
            Dictionary with generation results
        """
        if not self.embedding_manager:
            return {"status": "no_embedding_manager", "generated": 0}
        
        try:
            # Find chunks without embeddings for the specified provider
            provider = self.embedding_manager.get_provider(provider_name)
            
            query = """
                SELECT c.id, c.code 
                FROM chunks c
                LEFT JOIN embeddings e ON c.id = e.chunk_id 
                    AND e.provider = ? AND e.model = ?
                WHERE e.chunk_id IS NULL
            """
            
            if self.connection is None:
                raise RuntimeError("Database connection not established")
            
            results = self.connection.execute(query, [provider.name, provider.model]).fetchall()
            
            if not results:
                logger.info("No missing embeddings found")
                return {"status": "up_to_date", "generated": 0}
            
            chunk_ids = [row[0] for row in results]
            texts = [row[1] for row in results]
            
            logger.info(f"Generating embeddings for {len(chunk_ids)} chunks using {provider.name}/{provider.model}")
            
            # Generate embeddings
            embedding_result = await self.embedding_manager.embed_texts(texts, provider_name)
            
            # Store embeddings
            stored_count = 0
            for chunk_id, embedding in zip(chunk_ids, embedding_result.embeddings):
                try:
                    self.insert_embedding(
                        chunk_id=chunk_id,
                        provider=embedding_result.provider,
                        model=embedding_result.model,
                        dims=embedding_result.dims,
                        vector=embedding
                    )
                    stored_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store embedding for chunk {chunk_id}: {e}")
            
            logger.info(f"Generated and stored {stored_count} embeddings")
            return {"status": "success", "generated": stored_count}
            
        except Exception as e:
            logger.error(f"Failed to generate missing embeddings: {e}")
            return {"status": "error", "error": str(e), "generated": 0}

    def detach_database(self) -> bool:
        """
        Detach the database for coordination with other processes.
        
        Returns:
            True if successfully detached, False otherwise
        """
        if not self.connection:
            return True
            
        try:
            # Force checkpoint to ensure all changes are written
            self.connection.execute("FORCE CHECKPOINT")
            
            # Close the connection to release file lock
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed for coordination")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to detach database: {e}")
            return False

    def reattach_database(self) -> bool:
        """
        Reattach the database after coordination.
        
        Returns:
            True if successfully reattached, False otherwise
        """
        if self.connection:
            return True  # Already connected
            
        try:
            # Reconnect to the database
            self.connect()
            logger.info("Database reconnected after coordination")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to reattach database: {e}")
            return False

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")
