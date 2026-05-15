"""BM25 keyword searcher for lexical search."""
from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
from app.retrieval.searchers.base import BaseSearcher
from app.db.repositories.documents_repo import DocumentRepository


class BM25Searcher(BaseSearcher):
    """Keyword-based search using BM25 algorithm."""
    
    def __init__(self):
        """Initialize BM25 searcher."""
        self.bm25 = None
        self.all_docs = []
    
    def build_index(self):
        """Load all documents from database and build BM25 index."""
        self.all_docs = DocumentRepository.list_all()
        texts = [doc['content'] for doc in self.all_docs]
        tokenized = [t.split() for t in texts]
        self.bm25 = BM25Okapi(tokenized)
    
    def refresh_index(self):
        """Rebuild the BM25 index (call after adding new documents)."""
        self.bm25 = None
        self.all_docs = []
        self.build_index()
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform BM25 keyword search.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of documents with 'bm25_score' field
        """
        if not self.bm25:
            self.build_index()
        
        # Get BM25 scores
        scores = self.bm25.get_scores(query.split())
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Return documents with scores
        results = []
        for idx, score in ranked:
            doc = self.all_docs[idx].copy()
            doc['bm25_score'] = float(score)
            results.append(doc)
        
        return results
    
    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize BM25 scores to 0-1 range."""
        max_score = max(scores) if scores else 1.0
        if max_score <= 0:
            return [0.0] * len(scores)
        return [s / max_score for s in scores]
