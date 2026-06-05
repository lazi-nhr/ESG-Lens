"""Hybrid retrieval helper with optional company filtering.

This module uses the pre-existing HybridSearcher class and reshapes its
output into the flat document format expected by the evaluation pipeline.
"""
from typing import List, Dict, Optional

from app.core.config import DEFAULT_TOP_K
from app.retrieval.searchers import HybridSearcher

_hybrid_searcher = HybridSearcher(enable_reranking=False)


def _normalize_company_name(value: Optional[str]) -> str:
    return str(value or "").strip().casefold()


def _flatten_results(results: List[Dict]) -> List[Dict]:
    flattened: List[Dict] = []

    for result in results:
        document = result.get("doc", {}).copy()
        hybrid_score = float(result.get("hybrid_score", 0.0))

        document["bm25_score"] = float(result.get("bm25_score", 0.0))
        document["vector_score"] = float(result.get("vector_score", 0.0))
        document["hybrid_score"] = hybrid_score
        document["similarity"] = hybrid_score
        document["method"] = result.get("method", "hybrid")
        flattened.append(document)

    return flattened


async def retrieve_similar_hybrid(
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    company: Optional[str] = None,
    oversample_factor: int = 10,
) -> List[Dict]:
    """Retrieve documents using hybrid search and optional company filtering.

    Args:
        query_text: Search query used for both vector and BM25 retrieval.
        top_k: Number of final documents to return.
        company: Optional company name filter.
        oversample_factor: How many extra candidates to fetch before filtering.

    Returns:
        Flat document dictionaries with similarity and hybrid score fields.
    """
    search_query = query_text
    if company:
        search_query = f"{query_text} Company: {company}"

    candidate_count = max(top_k * oversample_factor, top_k)
    raw_results = _hybrid_searcher.search_with_details(search_query, top_k=candidate_count)
    flattened = _flatten_results(raw_results)

    if company:
        target_company = _normalize_company_name(company)
        flattened = [
            doc for doc in flattened
            if _normalize_company_name(doc.get("company")) == target_company
        ]

    flattened.sort(key=lambda doc: doc.get("similarity", 0.0), reverse=True)
    return flattened[:top_k]