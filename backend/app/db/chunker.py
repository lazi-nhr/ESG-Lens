from typing import List, Dict, Optional

import nltk
import unicodedata
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
    except Exception:
        nltk.download("punkt")
    _NLP_SETUP = True


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            pass
    # fallback: approximate by whitespace
    return len(re.findall(r"\S+", text))


def _make_chunk_id(doc_id: str, page: int, chunk_rank: int) -> str:
    return f"{doc_id}::p{page}::r{chunk_rank}"

def _normalize_for_bm25(text: str) -> str:
    """Lightweight normalization for BM25: fix hyphenation, collapse whitespace, unicode normalize, lowercase."""
    if not text:
        return ""
    # fix common hyphenation where a word is split at line break
    text = text.replace("-\n", "")
    # normalize newlines to spaces
    text = text.replace("\n", " ")
    # unicode normalization
    text = unicodedata.normalize("NFKC", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()

def chunk_text_by_page(page_text: str,
                       doc_id: str,
                       page_number: int,
                       base_tokens: int = 512,
                       overlap_tokens: int = 64) -> List[Dict]:
    """Chunk a single page into base chunks using sentence boundaries.

    Returns list of chunk metadata dicts with text and provenance.
    This implementation computes approximate character offsets for provenance.
    """
    _ensure_nltk()
    sentences = nltk.tokenize.sent_tokenize(page_text)

    chunks = []
    current = []
    current_tokens = 0
    search_cursor = 0
    chunk_rank = 0

    # Precompute sentence start positions to get precise offsets
    spans = []
    for sent in sentences:
        idx = page_text.find(sent, search_cursor)
        if idx == -1:
            # fallback: find anywhere
            idx = page_text.find(sent)
        spans.append((sent, idx))
        if idx != -1:
            search_cursor = idx + len(sent)

    for i, (sent, start_pos) in enumerate(spans):
        sent_tokens = _count_tokens(sent)
        if current_tokens + sent_tokens > base_tokens and current:
            chunk_text = " ".join(current)
            # compute start/end from first/last sentence in current
            first = current[0]
            last = current[-1]
            start = page_text.find(first)
            end = page_text.rfind(last) + len(last)
            token_count = _count_tokens(chunk_text)
            chunk_id = _make_chunk_id(doc_id, page_number, chunk_rank)
            chunks.append({
                "_id": chunk_id,
                "doc_id": doc_id,
                "page": page_number,
                "text": chunk_text,
                "token_count": token_count,
                "char_start": start if start != -1 else None,
                "char_end": end if end != -1 else None,
                "chunk_rank": chunk_rank,
                "parent_id": None,
            })
            chunk_rank += 1
            # build overlap: keep trailing sentences until overlap satisfied
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
        last = current[-1]
        start = page_text.find(first)
        end = page_text.rfind(last) + len(last)
        token_count = _count_tokens(chunk_text)
        chunk_id = _make_chunk_id(doc_id, page_number, chunk_rank)
        chunks.append({
            "_id": chunk_id,
            "doc_id": doc_id,
            "page": page_number,
            "text": chunk_text,
            "token_count": token_count,
            "char_start": start if start != -1 else None,
            "char_end": end if end != -1 else None,
            "chunk_rank": chunk_rank,
            "parent_id": None,
        })

    return chunks


def chunk_document(page_texts: List[str], doc_id: str, base_tokens: int = 512, overlap_tokens: int = 64) -> List[Dict]:
    """Chunk an entire document (list of page texts) into base chunks.

    Returns a flat list of chunks with page provenance.
    """
    all_chunks = []
    for i, ptext in enumerate(page_texts, start=1):
        page_chunks = chunk_text_by_page(ptext, doc_id, i, base_tokens=base_tokens, overlap_tokens=overlap_tokens)
        all_chunks.extend(page_chunks)
    return all_chunks


def build_parent_chunks(chunks: List[Dict], group_size: int = 4) -> List[Dict]:
    """Create parent (coarse) chunks by grouping consecutive base chunks.

    Returns list of parent chunk dicts and updates child `parent_id` in-place.
    """
    parents = []
    for i in range(0, len(chunks), group_size):
        group = chunks[i:i+group_size]
        texts = [c["text"] for c in group]
        combined = "\n\n".join(texts)
        parent_id = f"{group[0]['doc_id']}::parent::{i//group_size}"
        parent = {
            "_id": parent_id,
            "doc_id": group[0]["doc_id"] if group else None,
            "text": combined,
            "child_chunk_ids": [c["_id"] for c in group],
            "token_count": sum(c.get("token_count", 0) for c in group),
        }
        # annotate children
        for c in group:
            c["parent_id"] = parent_id
        parents.append(parent)
    return parents
