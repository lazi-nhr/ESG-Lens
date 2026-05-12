"""
LLM generation: wrapper for language model calls.
Integrates with Hugging Face Inference API.
Falls back to simple placeholder if API key not configured.
"""
from typing import List, Dict
import aiohttp

from app.core.config import HF_MODEL, HF_API_KEY, LLM_PROVIDER
from app.core.errors import GenerationError


async def generate_answer(query: str, retrieved_docs: List[Dict]) -> str:
    """
    Generate an answer based on the query and retrieved documents.
    Uses Hugging Face Inference API if configured, otherwise falls back to placeholder.
    
    Args:
        query: The user's question.
        retrieved_docs: List of similar documents from the database.
    
    Returns: Generated answer string.
    """
    try:
        if not retrieved_docs:
            return "No relevant documents found in the database."

        # If HF API is configured, use it
        if HF_API_KEY and LLM_PROVIDER == "huggingface":
            return await _call_huggingface_api(query, retrieved_docs)
        else:
            # Fallback: return placeholder answer
            return _placeholder_answer(retrieved_docs)
    except Exception as e:
        raise GenerationError(f"Error generating answer: {str(e)}")


async def _call_huggingface_api(query: str, retrieved_docs: List[Dict]) -> str:
    """
    Call Hugging Face Inference API with context from retrieved documents.
    
    Args:
        query: The user's question.
        retrieved_docs: List of similar documents.
    
    Returns: LLM-generated answer.
    """
    # Build context from retrieved documents
    context = "\n\n".join(
        f"Document {i+1}:\n{doc['content']}"
        for i, doc in enumerate(retrieved_docs[:3])  # Use top 3 docs
    )
    
    # Build prompt for ESG evaluation
    prompt = f"""Based on the following documents, provide a professional ESG evaluation response.

Documents:
{context}

Question: {query}

Response:"""
    
    # Call HF Inference API
    api_url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 500}}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    # HF returns list of dicts with 'generated_text'
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get("generated_text", "").strip()
                    return str(result)
                else:
                    error_text = await resp.text()
                    raise GenerationError(f"HF API error ({resp.status}): {error_text}")
    except aiohttp.ClientError as e:
        raise GenerationError(f"Failed to connect to HF API: {str(e)}")


def _placeholder_answer(retrieved_docs: List[Dict]) -> str:
    """
    Fallback: return a simple answer from the best matching document.
    Used when HF API is not configured.
    
    Args:
        retrieved_docs: List of similar documents.
    
    Returns: Simple answer string.
    """
    best_match = retrieved_docs[0]
    content = best_match["content"]
    
    if len(content) > 300:
        return f"Based on the documents, here's a summary: {content[:300]}..."
    else:
        return f"Based on the documents, here's what I found: {content}"
