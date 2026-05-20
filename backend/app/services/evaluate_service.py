"""
Evaluate service: orchestrate retrieval + generation for ESG evaluation.
"""
import logging
import time
from typing import Dict

from app.retrieval.vector_search import retrieve_similar
from app.llm.generator import generate_answer
from app.formatting.query_renderer import build_enriched_query
from app.formatting.report_renderer import format_report_markdown, format_report_text
from app.core.config import DEFAULT_TOP_K, DEFAULT_FORMAT

logger = logging.getLogger(__name__)


async def evaluate(
    company: str,
    criterion: str,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    format: str = DEFAULT_FORMAT
) -> Dict:
    """
    Execute an ESG evaluation: retrieve documents, generate answer, format report.
    
    Args:
        company: Company name (e.g., "Microsoft")
        criterion: ESG criterion (e.g., "emissions", "governance", etc.)
        query: The evaluation query
        top_k: Number of documents to retrieve
        format: Output format ("markdown" or "text")
    
    Returns: Dict with company, criterion, query, retrieved_count, report, format
    """
    start_time = time.time()
    logger.info(f"Starting ESG evaluation | company={company}, criterion={criterion}, top_k={top_k}, format={format}")
    logger.debug(f"Raw query: {query}")
    
    try:
        # Build enriched query for vector search
        enriched_query = build_enriched_query(company, criterion, query)
        logger.debug(f"Enriched query: {enriched_query}")

        # Retrieve similar documents
        logger.info("Retrieving similar documents...")
        retrieval_start = time.time()
        retrieved_docs = await retrieve_similar(enriched_query, top_k, company)
        retrieval_time = time.time() - retrieval_start
        logger.info(f"Retrieved {len(retrieved_docs)} documents in {retrieval_time:.2f}s (company filter: {company})")
        
        if retrieved_docs:
            for i, doc in enumerate(retrieved_docs[:3], 1):
                score = doc.get('similarity', 'N/A')
                content_preview = doc.get('content', '')[:100].replace('\n', ' ')
                logger.debug(f"  Doc {i}: similarity={score}, content_preview='{content_preview}...'")

        # Generate assessment
        logger.info("Generating assessment...")
        generation_start = time.time()
        assessment = await generate_answer(enriched_query, retrieved_docs)
        generation_time = time.time() - generation_start
        logger.info(f"Assessment generated in {generation_time:.2f}s")
        logger.debug(f"Assessment preview: {assessment[:200]}..." if len(assessment) > 200 else f"Assessment: {assessment}")

        # Format the report
        logger.info(f"Formatting report as {format}...")
        formatting_start = time.time()
        if format == "markdown":
            report = format_report_markdown(company, criterion, enriched_query, retrieved_docs, assessment)
        else:
            report = format_report_text(company, criterion, enriched_query, retrieved_docs, assessment)
        formatting_time = time.time() - formatting_start
        logger.info(f"Report formatted in {formatting_time:.2f}s")
        logger.debug(f"Report size: {len(report)} characters")

        total_time = time.time() - start_time
        logger.info(f"Evaluation completed in {total_time:.2f}s (retrieval={retrieval_time:.2f}s, generation={generation_time:.2f}s, formatting={formatting_time:.2f}s)")

        return {
            "company": company,
            "criterion": criterion,
            "query": enriched_query,
            "retrieved_count": len(retrieved_docs),
            "report": report,
            "format": format,
        }
    
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Evaluation failed after {elapsed:.2f}s | company={company}, criterion={criterion} | Error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise
