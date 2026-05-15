"""Vector similarity searcher using pgvector."""
from typing import List, Dict
from app.retrieval.searchers.base import BaseSearcher
from app.db.repositories.documents_repo import DocumentRepository
from app.retrieval.embedder import create_embedding


class VectorSearcher(BaseSearcher):
    """Semantic similarity search using vector embeddings and pgvector."""
    
    def __init__(self):
        """Initialize vector searcher."""
        pass
    
    def build_index(self):
        """
        Build index.
        
        For pgvector, the index is managed by PostgreSQL.
        This is a no-op but provided for interface compatibility.
        """
        pass
    
    def refresh_index(self):
        """
        Refresh index.
        
        For pgvector, the index automatically updates with new documents.
        This is a no-op but provided for interface compatibility.
        """
        pass
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform vector similarity search using pgvector.
        """
        # --- UPDATE THIS LINE TO USE is_query=True ---
        embedding = create_embedding(query, is_query=True)
        
        # Search by similarity in database
        results = DocumentRepository.search_by_similarity(embedding, top_k)
        
        return results
