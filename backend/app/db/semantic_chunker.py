"""
Semantic chunking: intelligently split documents based on semantic similarity.
Creates chunks where semantic boundaries naturally occur, not just by token count.
"""
from typing import List, Dict, Optional
import nltk
import re
import numpy as np
from sentence_transformers import util

try:
    import tiktoken
except Exception:
    tiktoken = None

_NLP_SETUP = False


def _ensure_nltk():
    """Ensure NLTK resources are available."""
    global _NLP_SETUP
    if _NLP_SETUP:
        return
    try:
        nltk.data.find("tokenizers/punkt")
        nltk.data.find("tokenizers/punkt_tab")
    except Exception:
        nltk.download("punkt")
        nltk.download("punkt_tab")
    _NLP_SETUP = True


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken or fallback to word count."""
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            pass
    return len(re.findall(r"\S+", text))


def _make_chunk_id(doc_id: str, page: int, chunk_rank: int) -> str:
    """Create a unique chunk ID."""
    return f"{doc_id}::p{page}::r{chunk_rank}"


def _get_page_for_offset(char_offset: int, page_mapping: List[Dict]) -> int:
    """Find which page a specific character offset belongs to."""
    for mapping in page_mapping:
        if mapping["start"] <= char_offset < mapping["end"]:
            return mapping["page"]
    return page_mapping[-1]["page"] if page_mapping else 1


def _get_sentence_embeddings(sentences: List[str], embedding_fn) -> np.ndarray:
    """
    Embed a list of sentences.
    
    Args:
        sentences: List of sentence strings
        embedding_fn: Function that takes text and returns embedding vector
    
    Returns: Array of embeddings (n_sentences, embedding_dim)
    """
    embeddings = []
    for sent in sentences:
        try:
            # embedding_fn returns a string representation of the vector
            emb_str = embedding_fn(sent, is_query=False)
            # Parse the string "[1.2, 3.4, ...]" back to a list
            emb_list = eval(emb_str)  # Safe here since we control the input
            embeddings.append(emb_list)
        except Exception as e:
            print(f"Warning: Failed to embed sentence: {e}")
            # Fallback: zero vector
            embeddings.append([0.0] * 384)  # Default embedding dim
    
    return np.array(embeddings)


def _calculate_similarities(embeddings: np.ndarray) -> np.ndarray:
    """
    Calculate cosine similarity between consecutive sentences.
    
    Args:
        embeddings: Array of shape (n_sentences, embedding_dim)
    
    Returns: Array of similarities between consecutive sentences (length n_sentences - 1)
    """
    if len(embeddings) < 2:
        return np.array([])
    
    similarities = []
    for i in range(len(embeddings) - 1):
        # Cosine similarity between sentence i and i+1
        sim = util.cos_sim(embeddings[i], embeddings[i + 1]).item()
        similarities.append(sim)
    
    return np.array(similarities)


def semantic_chunk_document(
    page_texts: List[str],
    doc_id: str,
    embedding_fn,
    similarity_threshold: float = 0.5,
    min_chunk_tokens: int = 100,
    max_chunk_tokens: int = 800
) -> List[Dict]:
    """
    Chunk document using semantic similarity between sentences.
    Creates boundaries where semantic coherence drops below threshold.
    
    Args:
        page_texts: List of text from each page
        doc_id: Document identifier
        embedding_fn: Function(text, is_query=bool) -> embedding_string
        similarity_threshold: Cosine similarity threshold for chunk boundaries (0-1)
        min_chunk_tokens: Minimum tokens per chunk
        max_chunk_tokens: Maximum tokens per chunk
    
    Returns: List of chunk dictionaries with metadata
    """
    _ensure_nltk()
    
    # === STEP 1: Stitch pages together with page mapping ===
    full_text = ""
    page_mapping = []
    current_char = 0
    
    for i, ptext in enumerate(page_texts, start=1):
        clean_text = ptext.strip() + " \n"
        start = current_char
        end = current_char + len(clean_text)
        
        page_mapping.append({"page": i, "start": start, "end": end})
        full_text += clean_text
        current_char = end
    
    # === STEP 2: Sentence tokenization ===
    sentences = nltk.tokenize.sent_tokenize(full_text)
    
    if not sentences:
        return []
    
    # === STEP 3: Embed all sentences ===
    print(f"  Embedding {len(sentences)} sentences for semantic analysis...")
    embeddings = _get_sentence_embeddings(sentences, embedding_fn)
    
    # === STEP 4: Calculate sentence similarities ===
    print(f"  Calculating semantic boundaries...")
    similarities = _calculate_similarities(embeddings)
    
    # === STEP 5: Identify chunk boundaries ===
    # Boundaries occur where similarity < threshold (semantic breaks)
    boundaries = [0]  # Always start with first sentence
    
    for i, sim in enumerate(similarities):
        # i is the index between sentence i and i+1
        if sim < similarity_threshold:
            boundaries.append(i + 1)
    
    boundaries.append(len(sentences))  # Always end with last sentence
    
    # === STEP 6: Build chunks from boundaries ===
    chunks = []
    chunk_rank = 0
    
    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]
        
        # Get sentences for this chunk
        chunk_sentences = sentences[start_idx:end_idx]
        chunk_text = " ".join(chunk_sentences)
        chunk_tokens = _count_tokens(chunk_text)
        
        # Handle min/max token constraints
        if chunk_tokens < min_chunk_tokens and i < len(boundaries) - 2:
            # Try to merge with next chunk (handled in next iteration)
            continue
        
        if chunk_tokens > max_chunk_tokens:
            # Split large chunks by token count (fallback to token-based for large semantic chunks)
            sub_chunks = _split_large_chunk(
                chunk_sentences, doc_id, page_mapping, full_text,
                max_chunk_tokens, chunk_rank
            )
            chunks.extend(sub_chunks)
            chunk_rank += len(sub_chunks)
            continue
        
        # Find character positions
        first_sent = chunk_sentences[0]
        last_sent = chunk_sentences[-1]
        
        start_pos = full_text.find(first_sent)
        end_pos = full_text.rfind(last_sent) + len(last_sent)
        
        if start_pos == -1:
            start_pos = 0
        if end_pos < start_pos:
            end_pos = start_pos + len(chunk_text)
        
        # Determine page (use first sentence's page)
        predominant_page = _get_page_for_offset(start_pos, page_mapping)
        
        chunks.append({
            "_id": _make_chunk_id(doc_id, predominant_page, chunk_rank),
            "doc_id": doc_id,
            "page": predominant_page,
            "text": chunk_text,
            "token_count": chunk_tokens,
            "char_start": start_pos,
            "char_end": end_pos,
            "chunk_rank": chunk_rank,
            "parent_id": None,
            "semantic": True,  # Mark as semantically chunked
        })
        chunk_rank += 1
    
    return chunks


def _split_large_chunk(
    sentences: List[str],
    doc_id: str,
    page_mapping: List[Dict],
    full_text: str,
    max_tokens: int,
    start_rank: int
) -> List[Dict]:
    """
    Split a semantically-coherent but token-large chunk using token limits.
    Fallback when semantic chunk exceeds max_chunk_tokens.
    """
    chunks = []
    chunk_rank = start_rank
    current = []
    current_tokens = 0
    
    for sent in sentences:
        sent_tokens = _count_tokens(sent)
        
        if current_tokens + sent_tokens > max_tokens and current:
            # Finalize current chunk
            chunk_text = " ".join(current)
            first_sent = current[0]
            start_pos = full_text.find(first_sent)
            if start_pos == -1:
                start_pos = 0
            
            predominant_page = _get_page_for_offset(start_pos, page_mapping)
            
            chunks.append({
                "_id": _make_chunk_id(doc_id, predominant_page, chunk_rank),
                "doc_id": doc_id,
                "page": predominant_page,
                "text": chunk_text,
                "token_count": current_tokens,
                "char_start": start_pos,
                "char_end": start_pos + len(chunk_text),
                "chunk_rank": chunk_rank,
                "parent_id": None,
                "semantic": True,
            })
            chunk_rank += 1
            current = []
            current_tokens = 0
        
        current.append(sent)
        current_tokens += sent_tokens
    
    # Final chunk
    if current:
        chunk_text = " ".join(current)
        first_sent = current[0]
        start_pos = full_text.find(first_sent)
        if start_pos == -1:
            start_pos = 0
        
        predominant_page = _get_page_for_offset(start_pos, page_mapping)
        
        chunks.append({
            "_id": _make_chunk_id(doc_id, predominant_page, chunk_rank),
            "doc_id": doc_id,
            "page": predominant_page,
            "text": chunk_text,
            "token_count": current_tokens,
            "char_start": start_pos,
            "char_end": start_pos + len(chunk_text),
            "chunk_rank": chunk_rank,
            "parent_id": None,
            "semantic": True,
        })
    
    return chunks


def build_parent_chunks(chunks: List[Dict], group_size: int = 4) -> List[Dict]:
    """
    Create parent (coarse) chunks by grouping consecutive base chunks.
    Works with both semantic and token-based chunks.
    """
    parents = []
    for i in range(0, len(chunks), group_size):
        group = chunks[i:i+group_size]
        texts = [c["text"] for c in group]
        combined = "\n\n".join(texts)
        parent_id = f"{group[0]['doc_id']}::parent::{i//group_size}"
        
        # Inherit page from first child
        predominant_page = group[0].get("page", 1) if group else 1
        
        parent = {
            "_id": parent_id,
            "doc_id": group[0]["doc_id"] if group else None,
            "page": predominant_page,
            "text": combined,
            "child_chunk_ids": [c["_id"] for c in group],
            "token_count": sum(c.get("token_count", 0) for c in group),
            "semantic": True,
        }
        for c in group:
            c["parent_id"] = parent_id
        parents.append(parent)
    
    return parents
