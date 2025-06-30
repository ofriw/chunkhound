"""DuckDB connection and schema management for ChunkHound."""

import os
import shutil
import time
from pathlib import Path
from typing import Any

import duckdb
from loguru import logger


class DuckDBConnectionManager:
    """Manages DuckDB connections, schema creation, and database operations."""
    
    def __init__(self, db_path: Path | str, config: "DatabaseConfig | None" = None):
        """Initialize DuckDB connection manager.
        
        Args:
            db_path: Path to DuckDB database file or ":memory:" for in-memory database
            config: Database configuration for provider-specific settings
        """
        self._db_path = db_path
        self.connection: Any | None = None
        self.config = config
        
        # Enhanced checkpoint tracking
        self._operations_since_checkpoint = 0
        self._checkpoint_threshold = 100  # Checkpoint every N operations
        self._last_checkpoint_time = time.time()

    @property
    def db_path(self) -> Path | str:
        """Database connection path or identifier."""
        return self._db_path

    @property
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        return self.connection is not None

    def connect(self) -> None:
        """Establish database connection and initialize schema with WAL validation."""
        logger.info(f"Connecting to DuckDB database: {self.db_path}")

        # Ensure parent directory exists for file-based databases
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if duckdb is None:
                raise ImportError("duckdb not available")

            # Connect to DuckDB with WAL corruption handling
            self._connect_with_wal_validation()
            logger.info("DuckDB connection established")

            # Load required extensions
            self._load_extensions()

            # Enable experimental HNSW persistence for disk-based databases
            if self.connection is not None:
                self.connection.execute("SET hnsw_enable_experimental_persistence = true")
                logger.debug("HNSW experimental persistence enabled")

            # Create schema and indexes
            self.create_schema()
            self.create_indexes()

            # Migrate legacy embeddings table if it exists
            self._migrate_legacy_embeddings_table()

            logger.info("DuckDB connection manager initialization complete")

        except Exception as e:
            logger.error(f"DuckDB connection failed: {e}")
            raise

    def _connect_with_wal_validation(self) -> None:
        """Connect to DuckDB with WAL corruption detection and automatic cleanup."""
        try:
            # Attempt initial connection
            self.connection = duckdb.connect(str(self.db_path))
            logger.debug("DuckDB connection successful")

        except duckdb.Error as e:
            error_msg = str(e)

            # Check for WAL corruption patterns
            if self._is_wal_corruption_error(error_msg):
                logger.warning(f"WAL corruption detected: {error_msg}")
                self._handle_wal_corruption()

                # Retry connection after WAL cleanup
                try:
                    self.connection = duckdb.connect(str(self.db_path))
                    logger.info("DuckDB connection successful after WAL cleanup")
                except Exception as retry_error:
                    logger.error(f"Connection failed even after WAL cleanup: {retry_error}")
                    raise
            else:
                # Not a WAL corruption error, re-raise original exception
                raise

    def _is_wal_corruption_error(self, error_msg: str) -> bool:
        """Check if error message indicates WAL corruption."""
        corruption_indicators = [
            "Failure while replaying WAL file",
            "Catalog \"chunkhound\" does not exist",
            "BinderException",
            "Binder Error",
            "Cannot bind index",
            "unknown index type",
            "HNSW",
            "You need to load the extension"
        ]

        return any(indicator in error_msg for indicator in corruption_indicators)

    def _handle_wal_corruption(self) -> None:
        """Handle WAL corruption using advanced recovery with VSS extension preloading."""
        db_path = Path(self.db_path)
        wal_file = db_path.with_suffix(db_path.suffix + '.wal')

        if not wal_file.exists():
            logger.warning(f"WAL corruption detected but no WAL file found at: {wal_file}")
            return

        # Get WAL file size for logging
        file_size = wal_file.stat().st_size
        logger.warning(f"WAL corruption detected. File size: {file_size:,} bytes")

        # First attempt: Try recovery with VSS extension preloaded
        logger.info("Attempting WAL recovery with VSS extension preloaded...")
        
        try:
            # Create a temporary recovery connection
            recovery_conn = duckdb.connect(":memory:")
            
            # Load VSS extension first
            recovery_conn.execute("INSTALL vss")
            recovery_conn.execute("LOAD vss")
            
            # Enable experimental persistence for HNSW indexes
            recovery_conn.execute("SET hnsw_enable_experimental_persistence = true")
            
            # Now attach the database file - this will trigger WAL replay with extension loaded
            recovery_conn.execute(f"ATTACH '{db_path}' AS recovery_db")
            
            # Verify tables are accessible
            recovery_conn.execute("SELECT COUNT(*) FROM recovery_db.files").fetchone()
            
            # Force a checkpoint to ensure WAL is integrated
            recovery_conn.execute("CHECKPOINT recovery_db")
            
            # Detach and close
            recovery_conn.execute("DETACH recovery_db")
            recovery_conn.close()
            
            logger.info("WAL recovery successful with VSS extension preloaded")
            return
            
        except Exception as recovery_error:
            logger.warning(f"Recovery with VSS preloading failed: {recovery_error}")
            
            # Second attempt: Conservative recovery - remove WAL but create backup first
            try:
                # Create backup of WAL file before removal
                backup_path = wal_file.with_suffix('.wal.corrupt')
                shutil.copy2(wal_file, backup_path)
                logger.info(f"Created WAL backup at: {backup_path}")
                
                # Remove corrupted WAL file
                os.remove(wal_file)
                logger.warning(f"Removed corrupted WAL file: {wal_file} (backup saved)")
                
            except Exception as e:
                logger.error(f"Failed to handle corrupted WAL file {wal_file}: {e}")
                raise

    def _maybe_checkpoint(self, force: bool = False) -> None:
        """Perform checkpoint if needed based on operations count or time elapsed.
        
        Args:
            force: Force checkpoint regardless of thresholds
        """
        if self.connection is None:
            return
            
        current_time = time.time()
        time_since_checkpoint = current_time - self._last_checkpoint_time
        
        # Checkpoint if forced, operations threshold reached, or 5 minutes elapsed
        should_checkpoint = (
            force or 
            self._operations_since_checkpoint >= self._checkpoint_threshold or
            time_since_checkpoint >= 300  # 5 minutes
        )
        
        if should_checkpoint:
            try:
                self.connection.execute("CHECKPOINT")
                self._operations_since_checkpoint = 0
                self._last_checkpoint_time = current_time
                if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                    logger.debug(f"Checkpoint completed (operations: {self._operations_since_checkpoint}, time: {time_since_checkpoint:.1f}s)")
            except Exception as e:
                if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                    logger.warning(f"Checkpoint failed: {e}")

    def disconnect(self, skip_checkpoint: bool = False) -> None:
        """Close database connection with optional checkpointing.
        
        Args:
            skip_checkpoint: If True, skip the checkpoint operation (useful when checkpoint 
                           was already done recently to avoid checkpoint conflicts)
        """
        if self.connection is not None:
            try:
                if not skip_checkpoint:
                    # Force checkpoint before close to ensure durability
                    self.connection.execute("CHECKPOINT")
                    # Only log in non-MCP mode to avoid JSON-RPC interference
                    if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                        logger.debug("Database checkpoint completed before disconnect")
                else:
                    if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                        logger.debug("Skipping checkpoint before disconnect (already done)")
            except Exception as e:
                # Only log errors in non-MCP mode
                if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                    logger.error(f"Checkpoint failed during disconnect: {e}")
                # Continue with close - don't block shutdown
            finally:
                self.connection.close()
                self.connection = None
                if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                    logger.info("DuckDB connection closed")

    def _load_extensions(self) -> None:
        """Load required DuckDB extensions."""
        logger.info("Loading DuckDB extensions")

        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Install and load VSS extension for vector operations
            self.connection.execute("INSTALL vss")
            self.connection.execute("LOAD vss")
            logger.info("VSS extension loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load DuckDB extensions: {e}")
            raise

    def create_schema(self) -> None:
        """Create database schema for files, chunks, and embeddings."""
        logger.info("Creating DuckDB schema")

        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Create sequence for files table
            self.connection.execute("CREATE SEQUENCE IF NOT EXISTS files_id_seq")

            # Files table
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY DEFAULT nextval('files_id_seq'),
                    path TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    extension TEXT,
                    size INTEGER,
                    modified_time TIMESTAMP,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create sequence for chunks table
            self.connection.execute("CREATE SEQUENCE IF NOT EXISTS chunks_id_seq")

            # Chunks table
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY DEFAULT nextval('chunks_id_seq'),
                    file_id INTEGER REFERENCES files(id),
                    chunk_type TEXT NOT NULL,
                    symbol TEXT,
                    code TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    start_byte INTEGER,
                    end_byte INTEGER,
                    size INTEGER,
                    signature TEXT,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create sequence for embeddings table
            self.connection.execute("CREATE SEQUENCE IF NOT EXISTS embeddings_id_seq")

            # Embeddings table
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS embeddings_1536 (
                    id INTEGER PRIMARY KEY DEFAULT nextval('embeddings_id_seq'),
                    chunk_id INTEGER REFERENCES chunks(id),
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    embedding FLOAT[1536],
                    dims INTEGER NOT NULL DEFAULT 1536,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create HNSW index for 1536-dimensional embeddings
            try:
                self.connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_hnsw_1536 ON embeddings_1536
                    USING HNSW (embedding)
                    WITH (metric = 'cosine')
                """)
                logger.info("HNSW index for 1536-dimensional embeddings created successfully")
            except Exception as e:
                logger.warning(f"Failed to create HNSW index for 1536-dimensional embeddings: {e}")

            # Note: Additional dimension tables (4096, etc.) will be created on-demand
            
            # Handle schema migrations for existing databases
            self._migrate_schema()
            
            logger.info("DuckDB schema created successfully with multi-dimension support")

        except Exception as e:
            logger.error(f"Failed to create DuckDB schema: {e}")
            raise

    def _migrate_schema(self) -> None:
        """Handle schema migrations for existing databases."""
        if self.connection is None:
            raise RuntimeError("No database connection")
        
        try:
            # Future schema migrations would go here
            pass
        
        except Exception as e:
            logger.warning(f"Failed to migrate schema: {e}")

    def create_indexes(self) -> None:
        """Create database indexes for performance optimization."""
        logger.info("Creating DuckDB indexes")

        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # File indexes
            self.connection.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
            self.connection.execute("CREATE INDEX IF NOT EXISTS idx_files_language ON files(language)")

            # Chunk indexes
            self.connection.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id)")
            self.connection.execute("CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type)")
            self.connection.execute("CREATE INDEX IF NOT EXISTS idx_chunks_symbol ON chunks(symbol)")

            # Embedding indexes are created per-table in _ensure_embedding_table_exists()
            # No need for global embedding indexes since we use dimension-specific tables

            logger.info("DuckDB indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create DuckDB indexes: {e}")
            raise

    def _migrate_legacy_embeddings_table(self) -> None:
        """Migrate legacy 'embeddings' table to dimension-specific tables."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        # Check if legacy embeddings table exists
        if not self._table_exists("embeddings"):
            return

        logger.info("Found legacy embeddings table, migrating to dimension-specific tables...")

        try:
            # Get all embeddings with their dimensions
            embeddings = self.connection.execute("""
                SELECT id, chunk_id, provider, model, embedding, dims, created_at
                FROM embeddings
            """).fetchall()

            if not embeddings:
                logger.info("Legacy embeddings table is empty, dropping it")
                self.connection.execute("DROP TABLE embeddings")
                return

            # Group by dimensions
            by_dims = {}
            for emb in embeddings:
                dims = emb[5]  # dims column
                if dims not in by_dims:
                    by_dims[dims] = []
                by_dims[dims].append(emb)

            # Migrate each dimension group
            for dims, emb_list in by_dims.items():
                table_name = self._ensure_embedding_table_exists(dims)
                logger.info(f"Migrating {len(emb_list)} embeddings to {table_name}")

                # Insert data into dimension-specific table
                for emb in emb_list:
                    vector_str = str(emb[4])  # embedding column
                    self.connection.execute(f"""
                        INSERT INTO {table_name} (chunk_id, provider, model, embedding, dims, created_at)
                        VALUES (?, ?, ?, {vector_str}, ?, ?)
                    """, [emb[1], emb[2], emb[3], emb[5], emb[6]])

            # Drop legacy table
            self.connection.execute("DROP TABLE embeddings")
            logger.info(f"Successfully migrated embeddings to {len(by_dims)} dimension-specific tables")

        except Exception as e:
            logger.error(f"Failed to migrate legacy embeddings table: {e}")
            raise

    def health_check(self) -> dict[str, Any]:
        """Perform health check and return status information."""
        status = {
            "provider": "duckdb",
            "connected": self.is_connected,
            "db_path": str(self.db_path),
            "version": None,
            "extensions": [],
            "tables": [],
            "errors": []
        }

        if not self.is_connected:
            status["errors"].append("Not connected to database")
            return status

        try:
            # Check connection before proceeding
            if self.connection is None:
                status["errors"].append("Database connection is None")
                return status

            # Get DuckDB version
            version_result = self.connection.execute("SELECT version()").fetchone()
            status["version"] = version_result[0] if version_result else "unknown"

            # Check if VSS extension is loaded
            extensions_result = self.connection.execute("""
                SELECT extension_name, loaded
                FROM duckdb_extensions()
                WHERE extension_name = 'vss'
            """).fetchone()

            if extensions_result:
                status["extensions"].append({
                    "name": extensions_result[0],
                    "loaded": extensions_result[1]
                })

            # Check if tables exist
            tables_result = self.connection.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
            """).fetchall()

            status["tables"] = [table[0] for table in tables_result]

            # Basic functionality test
            test_result = self.connection.execute("SELECT 1").fetchone()
            if test_result[0] != 1:
                status["errors"].append("Basic query test failed")

        except Exception as e:
            status["errors"].append(f"Health check error: {str(e)}")

        return status

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about the database connection."""
        return {
            "provider": "duckdb",
            "db_path": str(self.db_path),
            "connected": self.is_connected,
            "memory_database": str(self.db_path) == ":memory:",
            "connection_type": type(self.connection).__name__ if self.connection else None
        }

    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        result = self.connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [table_name]
        ).fetchone()
        return result is not None

    def _get_table_name_for_dimensions(self, dims: int) -> str:
        """Get table name for given embedding dimensions."""
        return f"embeddings_{dims}"

    def _ensure_embedding_table_exists(self, dims: int) -> str:
        """Ensure embedding table exists for given dimensions, create if needed."""
        table_name = self._get_table_name_for_dimensions(dims)

        if self._table_exists(table_name):
            return table_name

        if self.connection is None:
            raise RuntimeError("No database connection")

        logger.info(f"Creating embedding table for {dims} dimensions: {table_name}")

        try:
            # Create table with fixed dimensions for HNSW compatibility
            self.connection.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY DEFAULT nextval('embeddings_id_seq'),
                    chunk_id INTEGER REFERENCES chunks(id),
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    embedding FLOAT[{dims}],
                    dims INTEGER NOT NULL DEFAULT {dims},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create HNSW index for performance
            hnsw_index_name = f"idx_hnsw_{dims}"
            self.connection.execute(f"""
                CREATE INDEX {hnsw_index_name} ON {table_name}
                USING HNSW (embedding)
                WITH (metric = 'cosine')
            """)

            # Create regular indexes for fast lookups
            self.connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{dims}_chunk_id ON {table_name}(chunk_id)")
            self.connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{dims}_provider_model ON {table_name}(provider, model)")

            logger.info(f"Created {table_name} with HNSW index {hnsw_index_name} and regular indexes")
            return table_name

        except Exception as e:
            logger.error(f"Failed to create embedding table for {dims} dimensions: {e}")
            raise

    def _get_all_embedding_tables(self) -> list[str]:
        """Get list of all embedding tables (dimension-specific)."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        tables = self.connection.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name LIKE 'embeddings_%'
        """).fetchall()

        return [table[0] for table in tables]