"""
Companies endpoints: get companies available in DB.
"""
import logging
from fastapi import APIRouter
from app.db.repositories.documents_repo import DocumentRepository
from app.core.errors import DatabaseError

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/companies")
async def list_companies():
    """List all available companies from the database.
    
    Returns: List of dicts with 'id' (company name) and 'name' (display name).
    """
    try:
        logger.info("Fetching distinct companies from database...")
        companies = DocumentRepository.get_distinct_companies()
        logger.info(f"Found {len(companies)} distinct companies")
        
        # Return as list of dicts with both 'id' and 'name' for frontend compatibility
        # The company name serves as both the ID and display name
        return [{"id": company, "name": company} for company in companies]
    
    except DatabaseError as e:
        logger.error(f"Failed to fetch companies: {str(e)}")
        return {"error": str(e)}, 500
    except Exception as e:
        logger.error(f"Unexpected error fetching companies: {str(e)}", exc_info=True)
        return {"error": "Internal server error"}, 500