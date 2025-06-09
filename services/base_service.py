"""Base service class for ChunkHound services."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pathlib import Path

from interfaces.database_provider import DatabaseProvider


class BaseService(ABC):
    """Base service class providing common functionality and dependency management."""
    
    def __init__(self, database_provider: DatabaseProvider):
        """Initialize service with database provider dependency.
        
        Args:
            database_provider: Database provider implementation
        """
        self._db = database_provider
    
    @property
    def database(self) -> DatabaseProvider:
        """Get database provider instance."""
        return self._db