from typing import List, Dict, Optional
import nltk
import re

try:
    import tiktoken
except Exception:
    tiktoken = None

_NLP_SETUP = False

def _ensure_nltk():
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
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            pass
    return len(re.findall(r"\S+", text))

def _make_chunk_id(doc_id: str, page: int, chunk_rank: int) -> str:
    return f"{doc_id}::p{page}::r{chunk_rank}"

def _get_page_for_offset(char_offset: int, page_mapping: List[Dict]) -> int:
    """Helper to find which page a specific character offset belongs to."""
    for mapping in page_mapping:
        if mapping["start"] <= char_offset < mapping["end"]:
            return mapping["page"]
    return page_mapping[-1]["page"] if page_mapping else 1

def chunk_document(page_texts: List[str], doc_id: str, base_tokens: int = 384, overlap_tokens: int = 64) -> List[Dict]:
    """
    Chunk an entire document by treating it as a continuous stream of text, 
    preventing sentences from being broken across page boundaries.
    """
    _ensure_nltk()
    
    # 1. Stitch pages together and build a character-to-page map
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

    # 2. Tokenize the ENTIRE document into sentences
    sentences = nltk.tokenize.sent_tokenize(full_text)
    
    chunks = []
    current = []
    current_tokens = 0
    search_cursor = 0
    chunk_rank = 0
    
    spans = []
    for sent in sentences:
        idx = full_text.find(sent, search_cursor)
        if idx == -1:
            idx = full_text.find(sent)
        spans.append((sent, idx))
        if idx != -1:
            search_cursor = idx + len(sent)

    # 3. Build chunks using the sliding window
    for i, (sent, start_pos) in enumerate(spans):
        sent_tokens = _count_tokens(sent)
        
        if current_tokens + sent_tokens > base_tokens and current:
            chunk_text = " ".join(current)
            first = current[0]
            last = current[-1]
            start = full_text.find(first)
            end = full_text.rfind(last) + len(last)
            
            # Map the chunk's starting character back to its original page
            predominant_page = _get_page_for_offset(start, page_mapping)
            
            chunks.append({
                "_id": _make_chunk_id(doc_id, predominant_page, chunk_rank),
                "doc_id": doc_id,
                "page": predominant_page,
                "text": chunk_text,
                "token_count": _count_tokens(chunk_text),
                "char_start": start if start != -1 else None,
                "char_end": end if end != -1 else None,
                "chunk_rank": chunk_rank,
                "parent_id": None,
            })
            chunk_rank += 1
            
            # Build overlap
            if overlap_tokens > 0:
                overlap_buf = []
                overlap_tokens_acc = 0
                while current and overlap_tokens_acc < overlap_tokens:
                    tok = _count_tokens(current[-1])
                    overlap_buf.insert(0, current.pop())
                    overlap_tokens_acc += tok
                current = overlap_buf.copy()
                current_tokens = sum(_count_tokens(s) for s in current)
            else:
                current = []
                current_tokens = 0

        current.append(sent)
        current_tokens += sent_tokens

    if current:
        chunk_text = " ".join(current)
        first = current[0]
        start = full_text.find(first)
        end = start + len(chunk_text)
        predominant_page = _get_page_for_offset(start, page_mapping)
        
        chunks.append({
            "_id": _make_chunk_id(doc_id, predominant_page, chunk_rank),
            "doc_id": doc_id,
            "page": predominant_page,
            "text": chunk_text,
            "token_count": _count_tokens(chunk_text),
            "char_start": start if start != -1 else None,
            "char_end": end if end != -1 else None,
            "chunk_rank": chunk_rank,
            "parent_id": None,
        })

    return chunks


def build_parent_chunks(chunks: List[Dict], group_size: int = 4) -> List[Dict]:
    """Create parent (coarse) chunks by grouping consecutive base chunks."""
    parents = []
    for i in range(0, len(chunks), group_size):
        group = chunks[i:i+group_size]
        texts = [c["text"] for c in group]
        combined = "\n\n".join(texts)
        parent_id = f"{group[0]['doc_id']}::parent::{i//group_size}"
        
        # BUG FIX: Ensure the parent chunk inherits the page number from its first child
        predominant_page = group[0].get("page", 1) if group else 1
        
        parent = {
            "_id": parent_id,
            "doc_id": group[0]["doc_id"] if group else None,
            "page": predominant_page,  # <--- THIS WAS MISSING
            "text": combined,
            "child_chunk_ids": [c["_id"] for c in group],
            "token_count": sum(c.get("token_count", 0) for c in group),
        }
        for c in group:
            c["parent_id"] = parent_id
        parents.append(parent)
    return parents