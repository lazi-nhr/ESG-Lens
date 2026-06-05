"""Cross-encoder reranker for refining search results."""
from typing import List, Dict, Tuple
from sentence_transformers import CrossEncoder
import logging

logger = logging.getLogger(__name__)


class DocumentReranker:
    """
    Rerank documents using a cross-encoder model.
    
    Cross-encoders directly score query-document relevance pairs,
    providing more accurate ranking than combining separate embeddings.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        """
        Initialize the reranker.
        
        Args:
            model_name: HuggingFace cross-encoder model name.
                       Default: ms-marco-MiniLM-L-12-v2 (small, fast, good quality)
            
        Popular alternatives:
            - "cross-encoder/qnli-distilroberta-base" - Q&A focused
            - "cross-encoder/ms-marco-TinyBERT-L-2-v2" - Very fast, smaller
            - "cross-encoder/ms-marco-MiniLM-L-6-v2" - Faster than default
            - "Qwen/Qwen3-Reranker-0.6B"
        """
        try:
            self.model = CrossEncoder(model_name)
            logger.info(f"✅ Loaded reranker: {model_name}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load reranker {model_name}: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = None,
        threshold: float = None
    ) -> List[Dict]:
        """
        Rerank documents by query relevance.
        
        Args:
            query: The search query
            documents: List of document dicts with at least 'content' and 'id'
            top_k: Return only top-k results (optional)
            threshold: Filter documents with score below threshold (0-1) (optional)
        
        Returns:
            Reranked documents sorted by relevance score (highest first)
        """
        if not self.model:
            logger.warning("Reranker not available, returning original order")
            return documents
        
        if not documents:
            return []
        
        # Prepare query-document pairs for cross-encoder
        doc_contents = [doc.get('content', '') for doc in documents]
        pairs = [[query, content] for content in doc_contents]
        
        # Score pairs
        scores = self.model.predict(pairs)
        
        # Add scores to documents
        scored_docs = [
            {**doc, 'rerank_score': float(score)}
            for doc, score in zip(documents, scores)
        ]
        
        # Sort by rerank score (descending)
        ranked = sorted(scored_docs, key=lambda x: x['rerank_score'], reverse=True)
        
        # Apply threshold filter if provided
        if threshold is not None:
            ranked = [d for d in ranked if d['rerank_score'] >= threshold]
        
        # Apply top_k if provided
        if top_k is not None:
            ranked = ranked[:top_k]
        
        return ranked
    
    def rerank_with_reasons(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
        include_context: bool = True
    ) -> List[Dict]:
        """
        Rerank with additional scoring context.
        
        Args:
            query: The search query
            documents: Documents to rerank
            top_k: Return top-k results
            include_context: Include document preview in results
        
        Returns:
            Ranked documents with detailed scores and context
        """
        if not self.model:
            return documents[:top_k] if top_k else documents
        
        # Rerank
        ranked = self.rerank(query, documents, top_k=top_k)
        
        # Add context
        if include_context:
            for doc in ranked:
                # Add preview of content
                content = doc.get('content', '')
                preview = content[:150] + "..." if len(content) > 150 else content
                doc['preview'] = preview
                
                # Add relevance interpretation
                score = doc.get('rerank_score', 0)
                if score >= 0.9:
                    doc['relevance'] = "Excellent"
                elif score >= 0.7:
                    doc['relevance'] = "Good"
                elif score >= 0.5:
                    doc['relevance'] = "Fair"
                else:
                    doc['relevance'] = "Poor"
        
        return ranked
    
    def batch_rerank(
        self,
        query_doc_pairs: List[Tuple[str, str]],
        return_scores: bool = True
    ) -> List[float]:
        """
        Rerank multiple query-document pairs efficiently.
        
        Args:
            query_doc_pairs: List of (query, document) tuples
            return_scores: Return scores or just ranking
        
        Returns:
            List of relevance scores
        """
        if not self.model:
            return [0.0] * len(query_doc_pairs)
        
        return self.model.predict(query_doc_pairs)


# Singleton instance for convenience
_reranker = None


def get_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2") -> DocumentReranker:
    """Get or create the global reranker instance."""
    global _reranker
    if _reranker is None:
        _reranker = DocumentReranker(model_name)
    return _reranker
