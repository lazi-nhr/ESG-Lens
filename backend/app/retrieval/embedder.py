"""
Embedding function: convert text to vector representation using sentence-transformers.
"""
import os
from app.core.config import EMBEDDING_DIM, EMBEDDING_MODEL

_model = None
# Dynamically grab the model from environment variables
MODEL_NAME = EMBEDDING_MODEL

def _get_model():
    """Load sentence-transformers model (lazy loading)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def create_embedding(text: str, is_query: bool = False) -> str:
    """
    Create embedding vector from text using sentence-transformers.
    """
    if not text or not text.strip():
        return "[" + ",".join(["0.0"] * EMBEDDING_DIM) + "]"
    
    # --- THE BGE BUG FIX ---
    # Apply the asymmetric query prefix if this is a search query
    if is_query and "bge" in MODEL_NAME.lower():
        encode_text = f"Represent this sentence for searching relevant passages: {text}"
    else:
        encode_text = text

    model = _get_model()
    embedding = model.encode(encode_text, convert_to_tensor=False)
    embedding_list = embedding.tolist()
    
    return "[" + ",".join(map(str, embedding_list)) + "]"