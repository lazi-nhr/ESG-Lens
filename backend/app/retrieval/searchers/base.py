"""Abstract base class for search implementations."""
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseSearcher(ABC):
    """Abstract base class for document searchers."""
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for documents matching the query.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of documents with search-specific scoring
        """
        pass
    
    @abstractmethod
    def build_index(self):
        """Build/initialize the search index."""
        pass
    
    @abstractmethod
    def refresh_index(self):
        """Refresh/rebuild the search index."""
        pass
