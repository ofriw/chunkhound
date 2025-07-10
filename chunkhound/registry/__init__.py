"""Provider registry and dependency injection container for ChunkHound."""

import os
from typing import Any, TypeVar, Optional

from loguru import logger

# Import core types
from chunkhound.core.types.common import Language

# Import centralized configuration
from chunkhound.core.config.config import Config

# Import concrete providers
from chunkhound.providers.database.duckdb_provider import DuckDBProvider
from chunkhound.providers.embeddings.openai_provider import OpenAIEmbeddingProvider

# Import embedding factory for unified provider creation
from chunkhound.core.config.embedding_factory import EmbeddingProviderFactory
from chunkhound.core.config.embedding_config import EmbeddingConfig
from chunkhound.providers.parsing.bash_parser import BashParser
from chunkhound.providers.parsing.c_parser import CParser
from chunkhound.providers.parsing.cpp_parser import CppParser
from chunkhound.providers.parsing.csharp_parser import CSharpParser
from chunkhound.providers.parsing.go_parser import GoParser
from chunkhound.providers.parsing.groovy_parser import GroovyParser
from chunkhound.providers.parsing.java_parser import JavaParser
from chunkhound.providers.parsing.javascript_parser import JavaScriptParser
from chunkhound.providers.parsing.kotlin_parser import KotlinParser
from chunkhound.providers.parsing.makefile_parser import MakefileParser
from chunkhound.providers.parsing.markdown_parser import MarkdownParser
from chunkhound.providers.parsing.matlab_parser import MatlabParser

# Import language parsers
from chunkhound.providers.parsing.python_parser import PythonParser
from chunkhound.providers.parsing.rust_parser import RustParser
from chunkhound.providers.parsing.text_parser import JsonParser, PlainTextParser, YamlParser
from chunkhound.providers.parsing.toml_parser import TomlParser
from chunkhound.providers.parsing.typescript_parser import TypeScriptParser

# Import services
from chunkhound.services.base_service import BaseService
from chunkhound.services.embedding_service import EmbeddingService
from chunkhound.services.indexing_coordinator import IndexingCoordinator
from chunkhound.services.search_service import SearchService

T = TypeVar("T")


class ProviderRegistry:
    """Registry for managing provider implementations and dependency injection."""

    def __init__(self):
        """Initialize the provider registry."""
        self._providers: dict[str, Any] = {}
        self._singletons: dict[str, Any] = {}
        self._language_parsers: dict[Language, Any] = {}
        self._config: Optional[Config] = None

        # Register default providers
        self._register_default_providers()

    def configure(self, config: Config) -> None:
        """Configure the registry with application settings.

        Args:
            config: Configuration object with provider settings
        """
        self._config = config

        # Register database provider after configuration is available
        self._register_database_provider()

        # Register embedding provider after configuration is available
        self._register_embedding_provider()

        # Provider registry configured (logging disabled for MCP/CLI compatibility)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            pass  # Could enable logging here for non-MCP modes if needed

    def register_provider(
        self, name: str, implementation: Any, singleton: bool = True
    ) -> None:
        """Register a provider implementation.

        Args:
            name: Provider name/identifier
            implementation: Concrete implementation class or instance
            singleton: Whether to use singleton pattern for this provider
        """
        self._providers[name] = (implementation, singleton)

        # Clear existing singleton if registered
        if singleton and name in self._singletons:
            del self._singletons[name]

        # Suppress logging during MCP mode initialization
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug(f"Registered {implementation.__name__} as {name}")

    def register_language_parser(self, language: Language, parser_class: Any) -> None:
        """Register a language parser for a specific programming language.

        Args:
            language: Programming language identifier
            parser_class: Parser implementation class
        """
        # Create and setup parser instance
        parser = parser_class()
        if hasattr(parser, "setup"):
            parser.setup()

        self._language_parsers[language] = parser

        # Suppress logging during MCP mode initialization
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug(f"Registered {parser_class.__name__} for {language.value}")

    def get_provider(self, name: str) -> Any:
        """Get a provider instance for the specified name.

        Args:
            name: Provider name to get

        Returns:
            Provider instance

        Raises:
            ValueError: If no provider is registered for the name
        """
        if name not in self._providers:
            raise ValueError(f"No provider registered for {name}")

        implementation_class, is_singleton = self._providers[name]

        if is_singleton:
            if name not in self._singletons:
                self._singletons[name] = self._create_instance(implementation_class)
            return self._singletons[name]
        else:
            return self._create_instance(implementation_class)

    def get_language_parser(self, language: Language) -> Any | None:
        """Get parser for specified programming language.

        Args:
            language: Programming language identifier

        Returns:
            Parser instance or None if not supported
        """
        return self._language_parsers.get(language)

    def get_all_language_parsers(self) -> dict[Language, Any]:
        """Get all registered language parsers.

        Returns:
            Dictionary mapping languages to parser instances
        """
        return self._language_parsers.copy()

    def create_service(self, service_class: type[T]) -> T:
        """Create a service instance with dependency injection.

        Args:
            service_class: Service class to instantiate

        Returns:
            Service instance with dependencies injected
        """
        if not issubclass(service_class, BaseService):
            raise ValueError(f"{service_class} must inherit from BaseService")

        return self._create_instance(service_class)

    def create_indexing_coordinator(self) -> IndexingCoordinator:
        """Create an IndexingCoordinator with all dependencies.

        Returns:
            Configured IndexingCoordinator instance
        """
        database_provider = self.get_provider("database")
        embedding_provider = None

        try:
            embedding_provider = self.get_provider("embedding")
        except ValueError as e:
            # No embedding provider configured (logging disabled for MCP/CLI compatibility)
            if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                pass  # Could enable logging here for non-MCP modes if needed
        except Exception as e:
            # Failed to create embedding provider (logging disabled for MCP/CLI compatibility)
            if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                pass  # Could enable logging here for non-MCP modes if needed

        language_parsers = self.get_all_language_parsers()

        return IndexingCoordinator(
            database_provider=database_provider,
            embedding_provider=embedding_provider,
            language_parsers=language_parsers,
        )

    def create_search_service(self) -> SearchService:
        """Create a SearchService with all dependencies.

        Returns:
            Configured SearchService instance
        """
        database_provider = self.get_provider("database")
        embedding_provider = None

        try:
            embedding_provider = self.get_provider("embedding")
        except ValueError:
            logger.warning("No embedding provider configured for search service")

        return SearchService(
            database_provider=database_provider, embedding_provider=embedding_provider
        )

    def create_embedding_service(self) -> EmbeddingService:
        """Create an EmbeddingService with all dependencies.

        Returns:
            Configured EmbeddingService instance
        """
        database_provider = self.get_provider("database")
        embedding_provider = None

        try:
            embedding_provider = self.get_provider("embedding")
        except ValueError:
            logger.warning("No embedding provider configured for embedding service")

        # Get unified batch configuration from config object
        # Optimized defaults based on DuckDB performance research and HNSW vector index best practices
        if self._config and self._config.embedding:
            embedding_batch_size = self._config.embedding.batch_size
            db_batch_size = self._config.indexing.db_batch_size
            max_concurrent = self._config.embedding.max_concurrent_batches
            # Get optimization frequency with default
            optimization_batch_frequency = getattr(
                self._config.embedding, "optimization_batch_frequency", 1000
            )
        else:
            # Fallback defaults if no config
            embedding_batch_size = 1000
            db_batch_size = 5000
            max_concurrent = 8
            optimization_batch_frequency = 1000

        logger.info(
            f"EmbeddingService configuration: embedding_batch_size={embedding_batch_size}, "
            f"db_batch_size={db_batch_size}, max_concurrent={max_concurrent}, "
            f"optimization_batch_frequency={optimization_batch_frequency}"
        )

        return EmbeddingService(
            database_provider=database_provider,
            embedding_provider=embedding_provider,
            embedding_batch_size=embedding_batch_size,
            db_batch_size=db_batch_size,
            max_concurrent_batches=max_concurrent,
            optimization_batch_frequency=optimization_batch_frequency,
        )

    def _register_default_providers(self) -> None:
        """Register default provider implementations."""
        # Database providers will be registered after configuration in configure()
        # This ensures the provider gets the correct configuration parameters

        # Embedding providers will be registered after configuration in configure()
        # This ensures the provider gets the correct configuration parameters

        # Language parsers
        self.register_language_parser(Language.PYTHON, PythonParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Python parser")

        self.register_language_parser(Language.JAVA, JavaParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Java parser")

        self.register_language_parser(Language.JAVASCRIPT, JavaScriptParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered JavaScript parser")

        self.register_language_parser(Language.JSX, JavaScriptParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered JSX parser")

        self.register_language_parser(Language.TYPESCRIPT, TypeScriptParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered TypeScript parser")

        self.register_language_parser(Language.TSX, TypeScriptParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered TSX parser")

        self.register_language_parser(Language.CSHARP, CSharpParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered C# parser")

        self.register_language_parser(Language.GROOVY, GroovyParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Groovy parser")

        self.register_language_parser(Language.KOTLIN, KotlinParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Kotlin parser")

        self.register_language_parser(Language.GO, GoParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Go parser")

        self.register_language_parser(Language.BASH, BashParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Bash parser")

        self.register_language_parser(Language.C, CParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered C parser")

        self.register_language_parser(Language.CPP, CppParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered C++ parser")

        self.register_language_parser(Language.MATLAB, MatlabParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Matlab parser")

        self.register_language_parser(Language.MAKEFILE, MakefileParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Makefile parser")

        self.register_language_parser(Language.RUST, RustParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Rust parser")

        self.register_language_parser(Language.MARKDOWN, MarkdownParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Markdown parser")

        # Register text-based parsers
        self.register_language_parser(Language.JSON, JsonParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered JSON parser")

        self.register_language_parser(Language.YAML, YamlParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered YAML parser")

        self.register_language_parser(Language.TOML, TomlParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered TOML parser")

        self.register_language_parser(Language.TEXT, PlainTextParser)
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.debug("Registered Plain Text parser")

    def _register_database_provider(self) -> None:
        """Register the appropriate database provider based on configuration."""
        if not self._config:
            # Default to DuckDB if no config
            self.register_provider("database", DuckDBProvider, singleton=True)
            return
            
        provider_type = self._config.database.provider

        if provider_type == "duckdb":
            self.register_provider("database", DuckDBProvider, singleton=True)
        elif provider_type == "lancedb":
            from chunkhound.providers.database.lancedb_provider import LanceDBProvider

            self.register_provider("database", LanceDBProvider, singleton=True)
        else:
            logger.warning(
                f"Unsupported database provider type: {provider_type}. Falling back to DuckDB."
            )
            self.register_provider("database", DuckDBProvider, singleton=True)

    def _register_embedding_provider(self) -> None:
        """Register the appropriate embedding provider based on configuration using factory."""
        if not self._config or not self._config.embedding:
            # Skip embedding provider registration if no config or no embedding config
            # This allows the system to run without embeddings
            return
            
        embedding_config = self._config.embedding
        
        # Register a factory-based provider that creates the correct instance on demand
        class FactoryEmbeddingProvider:
            """Wrapper that uses factory to create correct provider type."""
            def __new__(cls, **kwargs):
                # Merge config with any runtime kwargs
                merged_config = embedding_config.model_dump()
                merged_config.update(kwargs)
                
                try:
                    # Create EmbeddingConfig from merged configuration
                    config = EmbeddingConfig(**merged_config)
                    # Use factory to create the correct provider
                    return EmbeddingProviderFactory.create_provider(config)
                except Exception as e:
                    logger.warning(f"Failed to create configured embedding provider: {e}. Falling back to OpenAI.")
                    # Fallback to OpenAI with minimal config
                    fallback_config = EmbeddingConfig(provider="openai", api_key=merged_config.get("api_key"))
                    return EmbeddingProviderFactory.create_provider(fallback_config)
        
        self.register_provider("embedding", FactoryEmbeddingProvider, singleton=True)
        
        # Suppress logging during MCP mode initialization
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.info("Factory-based embedding provider registered")

    def _create_instance(self, cls: Any) -> Any:
        """Create an instance with basic dependency injection.

        Args:
            cls: Class to instantiate

        Returns:
            Instance with dependencies injected
        """
        try:
            # Handle specific provider types
            if hasattr(cls, "__name__"):
                if (
                    "DuckDBProvider" in cls.__name__
                    or "LanceDBProvider" in cls.__name__
                ):
                    # Database providers need db_path parameter and config
                    if self._config:
                        db_path = str(self._config.database.path)
                        db_config = self._config.database
                    else:
                        # Default config if none provided
                        from chunkhound.core.config.database_config import DatabaseConfig
                        db_config = DatabaseConfig()
                        db_path = str(db_config.path)

                    instance = cls(db_path, config=db_config)
                    instance.connect()
                    return instance
                elif "Database" in cls.__name__:
                    # Other database providers - use default path
                    return cls()
                elif "Embedding" in cls.__name__ or cls.__name__ == "FactoryEmbeddingProvider":
                    # Factory-based embedding provider or legacy embedding provider
                    if cls.__name__ == "FactoryEmbeddingProvider":
                        if self._config:
                            logger.debug(f"Creating factory-based embedding provider with config")
                        return cls()
                    else:
                        # Legacy embedding provider - inject configuration
                        if self._config:
                            embedding_config = self._config.embedding
                            config_params = {}
                            if embedding_config.api_key:
                                config_params["api_key"] = embedding_config.api_key
                            if embedding_config.base_url:
                                config_params["base_url"] = embedding_config.base_url
                            if embedding_config.model:
                                config_params["model"] = embedding_config.model
                            if embedding_config.batch_size:
                                config_params["batch_size"] = embedding_config.batch_size

                            logger.debug(
                                f"Creating legacy embedding provider with config: {config_params}"
                            )
                            try:
                                return cls(**config_params)
                            except Exception as e:
                                logger.error(
                                    f"Failed to create embedding provider {cls.__name__}: {e}"
                                )
                                raise
                        else:
                            # No config - use default
                            return cls()
                else:
                    # Other services - try with no args first
                    return cls()
            else:
                return cls()
        except Exception as e:
            logger.error(f"Failed to create instance: {e}")
            raise

    def begin_transaction(self) -> None:
        """Begin transaction on registered database provider."""
        database_provider = self.get_provider("database")
        if hasattr(database_provider, "begin_transaction"):
            database_provider.begin_transaction()

    def commit_transaction(self) -> None:
        """Commit transaction on registered database provider."""
        database_provider = self.get_provider("database")
        if hasattr(database_provider, "commit_transaction"):
            database_provider.commit_transaction()
        elif hasattr(database_provider, "_provider") and hasattr(
            database_provider._provider, "_connection"
        ):
            # Fallback for existing pattern
            database_provider._provider._connection.commit()

    def rollback_transaction(self) -> None:
        """Rollback transaction on registered database provider."""
        database_provider = self.get_provider("database")
        if hasattr(database_provider, "rollback_transaction"):
            database_provider.rollback_transaction()
        elif hasattr(database_provider, "_provider") and hasattr(
            database_provider._provider, "_connection"
        ):
            # Fallback for existing pattern
            database_provider._provider._connection.rollback()


# Global registry instance (lazy initialization)
_registry = None


def get_registry() -> ProviderRegistry:
    """Get the global registry instance.

    Returns:
        Global ProviderRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def configure_registry(config: Config | dict[str, Any]) -> None:
    """Configure the global provider registry.

    Args:
        config: Configuration object or dictionary (for backward compatibility)
    """
    if isinstance(config, dict):
        # Backward compatibility - convert dict to Config object
        from chunkhound.core.config.config import Config as ConfigClass
        config_obj = ConfigClass(**config)
        get_registry().configure(config_obj)
    else:
        get_registry().configure(config)


def get_provider(name: str) -> Any:
    """Get a provider from the global registry.

    Args:
        name: Provider name

    Returns:
        Provider instance
    """
    return get_registry().get_provider(name)


def create_indexing_coordinator() -> IndexingCoordinator:
    """Create an IndexingCoordinator from the global registry.

    Returns:
        Configured IndexingCoordinator instance
    """
    return get_registry().create_indexing_coordinator()


def create_search_service() -> SearchService:
    """Create a SearchService from the global registry.

    Returns:
        Configured SearchService instance
    """
    return get_registry().create_search_service()


def create_embedding_service() -> EmbeddingService:
    """Create an EmbeddingService from the global registry.

    Returns:
        Configured EmbeddingService instance
    """
    return get_registry().create_embedding_service()


__all__ = [
    "ProviderRegistry",
    "get_registry",
    "configure_registry",
    "get_provider",
    "create_indexing_coordinator",
    "create_search_service",
    "create_embedding_service",
]
