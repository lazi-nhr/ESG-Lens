"""
Evaluate endpoint: ESG evaluation with structured report.
"""
import logging
from fastapi import APIRouter, HTTPException

from app.api.schemas import EvaluateRequest, EvaluateResponse
from app.services.evaluate_service import evaluate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_esg(request: EvaluateRequest):
    """Generate an ESG evaluation report."""
    logger.info(f"[POST /evaluate] Received request | company={request.company}, criterion={request.criterion}")
    logger.debug(f"[POST /evaluate] Full request: company={request.company}, criterion={request.criterion}, query={request.query}, top_k={request.top_k}, format={request.format}")
    
    try:
        result = await evaluate(
            company=request.company,
            criterion=request.criterion,
            query=request.query,
            top_k=request.top_k,
            format=request.format
        )
        logger.info(f"[POST /evaluate] Success | company={request.company}, criterion={request.criterion}, retrieved_count={result.get('retrieved_count', 0)}")
        logger.debug(f"[POST /evaluate] Response report size: {len(result.get('report', ''))} characters")
        return result
    except Exception as e:
        logger.error(f"[POST /evaluate] Failed | company={request.company}, criterion={request.criterion} | {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
