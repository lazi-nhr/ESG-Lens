"""
Companies endpoints: get companies available in DB.
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/companies")
async def list_companies():
    """List all available companies for the frontend dropdown."""
    
    # We return an array of objects so the frontend gets both the ID and the display name
    companies = [
        {"id": "apple", "name": "Apple"},
        {"id": "microsoft", "name": "Microsoft"},
        {"id": "tesla", "name": "Tesla"},
        {"id": "unilever", "name": "Unilever"},
        {"id": "nestle", "name": "Nestlé"},
        {"id": "bp", "name": "BP"},
        {"id": "ABB", "name": "ABB"},
        {"id": "Roche", "name": "Roche"}

    ]

    # Later we can insert dynamically fetch these companies from the DB
    
    return companies