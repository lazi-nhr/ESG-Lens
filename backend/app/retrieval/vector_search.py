"""
Vector search orchestration: embed query and retrieve similar documents.
"""
from typing import List, Dict

from app.db.repositories.documents_repo import DocumentRepository
from app.retrieval.embedder import create_embedding
from app.core.config import DEFAULT_TOP_K
from app.core.errors import RetrievalError


async def retrieve_similar(
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    company: str = None,
) -> List[Dict]:
    """
    Retrieve documents most similar to the query.
    
    Args:
        query_text: The user's query string.
        top_k: Number of documents to retrieve.
        company: Optional company filter (e.g., 'ABB', 'Roche').
    
    Returns: List of documents with similarity scores.
    """
    try:
        query_embedding = create_embedding(query_text, is_query=True)
        results = DocumentRepository.search_by_similarity(query_embedding, top_k, company)
        return results
    except Exception as e:
        raise RetrievalError(f"Error retrieving similar documents: {str(e)}")
