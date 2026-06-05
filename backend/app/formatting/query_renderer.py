"""
Query formatting: construct enriched queries for semantic search.
"""


def build_enriched_query(
    company: str = None,
    criterion: str = None,
    query: str = None,
    retrieval_bias: list[str] | None = None,
) -> str:
    """
    Build an enriched query by prepending company and criterion context.
    
    Args:
        company: Company name (optional)
        criterion: ESG criterion (optional)
        query: Base query string
    
    Returns: Enriched query string suitable for embedding and vector search
    
    Example:
        build_enriched_query("Apple", "emissions", "sustainability report")
        → "emissions - Apple: sustainability report"
    """
    parts = []
    
    if criterion:
        parts.append(criterion.lower())
    
    if query:
        parts.append(query)

    if retrieval_bias:
        bias_terms = [term for term in retrieval_bias if term]
        if bias_terms:
            parts.append("Focus terms: " + ", ".join(bias_terms))

    if company:
        parts.append(f"Company: {company}")
    
    return " - ".join(parts).strip() if parts else ""
