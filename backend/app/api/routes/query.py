# #"""
# #Query endpoint: vector similarity search.
# #"""
# #from fastapi import APIRouter, HTTPException

# #from app.api.schemas import QueryRequest
# #from app.retrieval.vector_search import retrieve_similar
# from app.llm.generator import generate_answer

# router = APIRouter()


# @router.post("/query")
# async def query_documents(request: QueryRequest):
#     """Query documents using vector similarity search."""
#     try:
#         results = await retrieve_similar(request.query, request.top_k)
#         assessment = await generate_answer(request.query, results)
        
#         response_text = f"Based on the retrieved documents:\n\n"
#         for i, r in enumerate(results, 1):
#             response_text += f"Document {r['id']}: {r['content']}\n\n"
#         response_text += f"Answer: {assessment}"
        
#         return {
#             "query": request.query,
#             "results": results,
#             "response": response_text
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



"""
Query endpoint: vector similarity search.
"""
from fastapi import APIRouter, HTTPException
from app.api.schemas import QueryRequest
from app.retrieval.vector_search import retrieve_similar
from app.llm.generator import generate_answer

router = APIRouter()

@router.post("/query")
async def query_documents(request: QueryRequest):
    """Query documents using vector similarity search."""
    try:
        results = await retrieve_similar(request.query, request.top_k)
        assessment = await generate_answer(request.query, results)

        return {
            "query": request.query,
            "results": results,
            "response": assessment  # just the answer, no raw doc dump
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
