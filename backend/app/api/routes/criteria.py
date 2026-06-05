"""
Criteria endpoints: get evaluation criteria
"""
from fastapi import APIRouter
from app.core.config import EVALUATION_CRITERIA

router = APIRouter()

@router.get("/criteria")
async def list_criteria():
    """List all available ESG evaluation criteria.
    
    Returns: List of dicts with id, name, description, category, question, context_instructions, etc.
    """
    return EVALUATION_CRITERIA


@router.get("/criteria/{criterion_id}")
async def get_criterion(criterion_id: str):
    """Get a specific criterion by ID.
    
    Args:
        criterion_id: The criterion ID (e.g., 'environment', 'overall')
    
    Returns: Criterion dict with all metadata, or 404 if not found.
    """
    for criterion in EVALUATION_CRITERIA:
        if criterion["id"] == criterion_id:
            return criterion
    
    return {"error": f"Criterion '{criterion_id}' not found"}, 404


def get_criterion_by_id(criterion_id: str):
    """Helper function to get criterion metadata for internal use.
    
    Args:
        criterion_id: The criterion ID
    
    Returns: Criterion dict or None if not found.
    """
    for criterion in EVALUATION_CRITERIA:
        if criterion["id"] == criterion_id:
            return criterion
    return None