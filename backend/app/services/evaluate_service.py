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
from app.api.routes.criteria import get_criterion_by_id

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
        # Load criterion metadata
        criterion_config = get_criterion_by_id(criterion)
        if not criterion_config:
            raise ValueError(f"Unknown criterion: {criterion}")
        
        logger.info(f"Criterion: {criterion_config['name']} | Output format: {criterion_config.get('output_format', 'narrative')}")
        logger.debug(f"Criterion instructions: {criterion_config.get('context_instructions', 'N/A')}")
        
        retrieval_bias = criterion_config.get("retrieval_bias", [])

        # Use criterion's predefined question with company context
        criterion_question = criterion_config.get('question', '')
        base_query = build_enriched_query(
            company=company,
            criterion=criterion,
            query=criterion_question,
        )
        
        retrieval_query = build_enriched_query(
            company=company,
            criterion=criterion,
            query=criterion_question,
            retrieval_bias=retrieval_bias,
        )
        
        # Fallback to old method if criterion question is missing
        if not criterion_question:
            base_query = build_enriched_query(
                company=company,
                criterion=criterion,
                query=query,
            )
            retrieval_query = build_enriched_query(
                company=company,
                criterion=criterion,
                query=query,
                retrieval_bias=retrieval_bias,
            )
        
        logger.debug(f"Query for vector search: {retrieval_query[:200]}..." if len(retrieval_query) > 200 else f"Query: {retrieval_query}")

        # Retrieve similar documents
        logger.info("Retrieving similar documents...")
        retrieval_start = time.time()
        retrieved_docs = await retrieve_similar(
            retrieval_query,
            top_k,
            company,
        )
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
        assessment = await generate_answer(
            base_query,
            retrieved_docs,
            company=company,
            criterion=criterion_config["name"],
        )
        generation_time = time.time() - generation_start
        logger.info(f"Assessment generated in {generation_time:.2f}s")
        logger.debug(f"Assessment preview: {assessment[:200]}..." if len(assessment) > 200 else f"Assessment: {assessment}")

        # Format the report
        logger.info(f"Formatting report as {format}...")
        formatting_start = time.time()
        if format == "markdown":
            report = format_report_markdown(company, criterion, base_query, retrieved_docs, assessment) # @todo: add date and fix criterion description
        else:
            report = format_report_text(company, criterion, base_query, retrieved_docs, assessment)
        formatting_time = time.time() - formatting_start
        logger.info(f"Report formatted in {formatting_time:.2f}s")
        logger.debug(f"Report size: {len(report)} characters")

        total_time = time.time() - start_time
        logger.info(f"Evaluation completed in {total_time:.2f}s (retrieval={retrieval_time:.2f}s, generation={generation_time:.2f}s, formatting={formatting_time:.2f}s)")

        return {
            "company": company,
            "criterion": criterion,
            "query": base_query,
            "retrieved_count": len(retrieved_docs),
            "report": report,
            "format": format,
        }
    
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Evaluation failed after {elapsed:.2f}s | company={company}, criterion={criterion} | Error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise
