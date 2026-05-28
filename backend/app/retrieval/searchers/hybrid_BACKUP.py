"""Hybrid searcher combining vector and keyword search with reranking."""
from typing import List, Dict, Optional
from app.retrieval.searchers.base import BaseSearcher
from app.retrieval.searchers.vector import VectorSearcher
from app.retrieval.searchers.bm25 import BM25Searcher
from app.retrieval.reranker import DocumentReranker
import os

# load environment variables
import dotenv
dotenv.load_dotenv()

FUSION_CONSTANT = os.getenv("FUSION_CONSTANT", 60)

class HybridSearcher(BaseSearcher):
    """
    Hybrid search combining:
    - BM25 keyword search
    - Vector semantic search
    - Optional cross-encoder reranking
    """
    
    def __init__(
        self,
        vector_searcher: Optional[VectorSearcher] = None,
        bm25_searcher: Optional[BM25Searcher] = None,
        enable_reranking: bool = True,
        reranker_model: Optional[str] = None
    ):
        """
        Initialize hybrid searcher with sub-searchers.
        
        Args:
            vector_searcher: VectorSearcher instance (created if None)
            bm25_searcher: BM25Searcher instance (created if None)
            enable_reranking: Enable cross-encoder reranking
            reranker_model: Custom cross-encoder model (optional)
        """
        self.vector_searcher = vector_searcher or VectorSearcher()
        self.bm25_searcher = bm25_searcher or BM25Searcher()
        self.enable_reranking = enable_reranking
        self.reranker = None
        
        if enable_reranking:
            model = reranker_model or "cross-encoder/ms-marco-MiniLM-L-12-v2"
            self.reranker = DocumentReranker(model)
    
    def build_index(self):
        """Build indices for both searchers."""
        self.vector_searcher.build_index()
        self.bm25_searcher.build_index()
    
    def refresh_index(self):
        """Refresh indices for both searchers."""
        self.vector_searcher.refresh_index()
        self.bm25_searcher.refresh_index()
    
    def set_reranking(self, enabled: bool):
        """Enable or disable reranking."""
        self.enable_reranking = enabled
        if enabled and self.reranker is None:
            self.reranker = DocumentReranker()
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform hybrid search with optional reranking.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            Ranked documents (with 'rerank_score' if reranking enabled)
        """
        # Get results from both searchers (request more for merging/reranking)
        vector_results = self.vector_searcher.search(query, top_k * 2)
        bm25_results = self.bm25_searcher.search(query, top_k * 2)
        
        # Merge results by combining scores
        merged = self._merge_results(vector_results, bm25_results)
        
        # Get candidate documents sorted by hybrid score
        candidates = sorted(
            merged.values(),
            key=lambda x: x['hybrid_score'],
            reverse=True
        )
        
        # Apply reranking if enabled
        if self.enable_reranking and self.reranker:
            final_results = self.reranker.rerank(query, candidates, top_k=top_k)
        else:
            final_results = candidates[:top_k]
        
        return final_results
    
    def search_with_details(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform hybrid search and return detailed scoring information.
        
        Returns documents with BM25 score, vector score, hybrid score, and rerank score.
        """
        # Get results from both searchers
        vector_results = self.vector_searcher.search(query, top_k * 2)
        bm25_results = self.bm25_searcher.search(query, top_k * 2)
        
        # Merge with detailed scores
        merged = self._merge_results_detailed(vector_results, bm25_results)
        
        # Sort by hybrid score
        candidates = sorted(
            merged.values(),
            key=lambda x: x['hybrid_score'],
            reverse=True
        )
        
        # Apply reranking if enabled
        if self.enable_reranking and self.reranker:
            final_results = self.reranker.rerank(query, candidates, top_k=top_k)
            for doc in final_results:
                doc['method'] = 'reranked'
        else:
            final_results = candidates[:top_k]
            for doc in final_results:
                doc['method'] = 'hybrid'
        
        return final_results
    
    def _merge_results(self, vector_results: List[Dict], bm25_results: List[Dict]) -> Dict:
        """
        Merge vector and BM25 results using score averaging.
        
        Returns dict of {doc_id: {doc, hybrid_score}}
        """
        # Normalize BM25 scores
        max_bm25 = max(
            [r.get('bm25_score', 0) for r in bm25_results],
            default=1.0
        )
        bm25_scores = {
            r['id']: r.get('bm25_score', 0) / max_bm25 if max_bm25 > 0 else 0
            for r in bm25_results
        }
        
        # Vector scores already normalized (0-1)
        vector_scores = {
            r['id']: r.get('similarity', 0)
            for r in vector_results
        }
        
        # Merge with average scoring
        merged = {}
        
        # Add vector results
        for doc in vector_results:
            doc_id = doc['id']
            vector_score = vector_scores[doc_id]
            bm25_score = bm25_scores.get(doc_id, 0)
            
            combined = (vector_score + bm25_score) / 2 if bm25_score > 0 else vector_score
            merged[doc_id] = {'doc': doc, 'hybrid_score': combined}
        
        # Add BM25-only results
        for doc in bm25_results:
            doc_id = doc['id']
            if doc_id not in merged:
                merged[doc_id] = {'doc': doc, 'hybrid_score': bm25_scores[doc_id]}
        
        return merged
    
    def _merge_results_detailed(self, vector_results: List[Dict], bm25_results: List[Dict]) -> Dict:
        """
        Merge results with detailed score tracking.
        
        Returns dict with bm25_score, vector_score, and hybrid_score.
        """
        # Normalize BM25 scores
        max_bm25 = max(
            [r.get('bm25_score', 0) for r in bm25_results],
            default=1.0
        )
        bm25_scores = {
            r['id']: r.get('bm25_score', 0) / max_bm25 if max_bm25 > 0 else 0
            for r in bm25_results
        }
        
        vector_scores = {
            r['id']: r.get('similarity', 0)
            for r in vector_results
        }
        
        merged = {}
        
        # Add vector results with details
        for doc in vector_results:
            doc_id = doc['id']
            vector_score = vector_scores[doc_id]
            bm25_score = bm25_scores.get(doc_id, 0)
            combined = (vector_score + bm25_score) / 2 if bm25_score > 0 else vector_score
            
            merged[doc_id] = {
                'doc': doc,
                'bm25_score': bm25_score,
                'vector_score': vector_score,
                'hybrid_score': combined
            }
        
        # Add BM25-only results
        for doc in bm25_results:
            doc_id = doc['id']
            if doc_id not in merged:
                merged[doc_id] = {
                    'doc': doc,
                    'bm25_score': bm25_scores[doc_id],
                    'vector_score': 0,
                    'hybrid_score': bm25_scores[doc_id]
                }
        
        return merged
