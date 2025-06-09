"""Provider registry and dependency injection container for ChunkHound."""

from typing import Any, Dict, Optional, Type, TypeVar
import inspect
from loguru import logger

from core.types import Language

# Import concrete providers
from providers.database.duckdb_provider import DuckDBProvider
from providers.embeddings.openai_provider import OpenAIEmbeddingProvider

# Import language parsers
from providers.parsing.python_parser import PythonParser
from providers.parsing.java_parser import JavaParser
from providers.parsing.javascript_parser import JavaScriptParser
from providers.parsing.typescript_parser import TypeScriptParser
from providers.parsing.csharp_parser import CSharpParser
from providers.parsing.markdown_parser import MarkdownParser

# Import services
from services.base_service import BaseService
from services.indexing_coordinator import IndexingCoordinator
from services.search_service import SearchService
from services.embedding_service import EmbeddingService

T = TypeVar('T')


class ProviderRegistry:
    """Registry for managing provider implementations and dependency injection."""
    
    def __init__(self):
        """Initialize the provider registry."""
        self._providers: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._language_parsers: Dict[Language, Any] = {}
        self._config: Dict[str, Any] = {}
        
        # Register default providers
        self._register_default_providers()
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the registry with application settings.
        
        Args:
            config: Configuration dictionary with provider settings
        """
        self._config = config.copy()
        logger.info("Provider registry configured")
    
    def register_provider(self, name: str, implementation: Any, singleton: bool = True) -> None:
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
        
        logger.debug(f"Registered {implementation.__name__} as {name}")
    
    def register_language_parser(self, language: Language, parser_class: Any) -> None:
        """Register a language parser for a specific programming language.
        
        Args:
            language: Programming language identifier
            parser_class: Parser implementation class
        """
        # Create and setup parser instance
        parser = parser_class()
        if hasattr(parser, 'setup'):
            parser.setup()
        
        self._language_parsers[language] = parser
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
    
    def get_language_parser(self, language: Language) -> Optional[Any]:
        """Get parser for specified programming language.
        
        Args:
            language: Programming language identifier
            
        Returns:
            Parser instance or None if not supported
        """
        return self._language_parsers.get(language)
    
    def get_all_language_parsers(self) -> Dict[Language, Any]:
        """Get all registered language parsers.
        
        Returns:
            Dictionary mapping languages to parser instances
        """
        return self._language_parsers.copy()
    
    def create_service(self, service_class: Type[T]) -> T:
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
        except ValueError:
            logger.warning("No embedding provider configured")
        
        language_parsers = self.get_all_language_parsers()
        
        return IndexingCoordinator(
            database_provider=database_provider,
            embedding_provider=embedding_provider,
            language_parsers=language_parsers
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
            database_provider=database_provider,
            embedding_provider=embedding_provider
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
        
        # Get batch configuration from config
        batch_size = self._config.get('embedding', {}).get('batch_size', 50)
        max_concurrent = self._config.get('embedding', {}).get('max_concurrent_batches', 3)
        
        return EmbeddingService(
            database_provider=database_provider,
            embedding_provider=embedding_provider,
            batch_size=batch_size,
            max_concurrent_batches=max_concurrent
        )
    
    def _register_default_providers(self) -> None:
        """Register default provider implementations."""
        # Database providers
        self.register_provider("database", DuckDBProvider, singleton=True)
        
        # Embedding providers
        self.register_provider("embedding", OpenAIEmbeddingProvider, singleton=True)
        
        # Language parsers
        try:
            self.register_language_parser(Language.PYTHON, PythonParser)
            logger.debug("Registered Python parser")
        except Exception as e:
            logger.warning(f"Failed to register Python parser: {e}")
        
        try:
            self.register_language_parser(Language.JAVA, JavaParser)
            logger.debug("Registered Java parser")
        except Exception as e:
            logger.warning(f"Failed to register Java parser: {e}")
        
        try:
            self.register_language_parser(Language.JAVASCRIPT, JavaScriptParser)
            logger.debug("Registered JavaScript parser")
        except Exception as e:
            logger.warning(f"Failed to register JavaScript parser: {e}")
        
        try:
            self.register_language_parser(Language.TYPESCRIPT, TypeScriptParser)
            logger.debug("Registered TypeScript parser")
        except Exception as e:
            logger.warning(f"Failed to register TypeScript parser: {e}")
        
        try:
            self.register_language_parser(Language.CSHARP, CSharpParser)
            logger.debug("Registered C# parser")
        except Exception as e:
            logger.warning(f"Failed to register C# parser: {e}")
        
        try:
            self.register_language_parser(Language.MARKDOWN, MarkdownParser)
            logger.debug("Registered Markdown parser")
        except Exception as e:
            logger.warning(f"Failed to register Markdown parser: {e}")
        
        logger.info("Default providers registered")
    
    def _create_instance(self, cls: Any) -> Any:
        """Create an instance with basic dependency injection.
        
        Args:
            cls: Class to instantiate
            
        Returns:
            Instance with dependencies injected
        """
        try:
            # Handle specific provider types
            if hasattr(cls, '__name__'):
                if 'DuckDBProvider' in cls.__name__:
                    # DuckDB provider needs db_path parameter and connection
                    db_path = self._config.get('database', {}).get('path', '.chunkhound.db')
                    instance = cls(db_path)
                    instance.connect()
                    return instance
                elif 'Database' in cls.__name__:
                    # Other database providers - use default path
                    return cls()
                elif 'Embedding' in cls.__name__:
                    # Embedding provider - use defaults
                    return cls()
                else:
                    # Other services - try with no args first
                    return cls()
            else:
                return cls()
        except Exception as e:
            logger.error(f"Failed to create instance: {e}")
            raise


# Global registry instance
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Get the global provider registry instance.
    
    Returns:
        Global ProviderRegistry instance
    """
    return _registry


def configure_registry(config: Dict[str, Any]) -> None:
    """Configure the global provider registry.
    
    Args:
        config: Configuration dictionary
    """
    _registry.configure(config)


def get_provider(name: str) -> Any:
    """Get a provider from the global registry.
    
    Args:
        name: Provider name
        
    Returns:
        Provider instance
    """
    return _registry.get_provider(name)


def create_indexing_coordinator() -> IndexingCoordinator:
    """Create an IndexingCoordinator from the global registry.
    
    Returns:
        Configured IndexingCoordinator instance
    """
    return _registry.create_indexing_coordinator()


def create_search_service() -> SearchService:
    """Create a SearchService from the global registry.
    
    Returns:
        Configured SearchService instance
    """
    return _registry.create_search_service()


def create_embedding_service() -> EmbeddingService:
    """Create an EmbeddingService from the global registry.
    
    Returns:
        Configured EmbeddingService instance
    """
    return _registry.create_embedding_service()


__all__ = [
    'ProviderRegistry',
    'get_registry',
    'configure_registry', 
    'get_provider',
    'create_indexing_coordinator',
    'create_search_service',
    'create_embedding_service'
]