"""Retriever for BM25 + FAISS hybrid retrieval using Reciprocal Rank Fusion (RRF)."""
import os
from typing import List, Dict, Callable, Optional
from rank_bm25 import BM25Okapi
import numpy as np

class Retriever:
    def __init__(self, faiss_indexer=None):
        self.faiss = faiss_indexer
        self.bm25 = None
        self.corpus_texts: List[str] = []
        self.chunk_ids: List[str] = []
        self.faiss_mapping: Dict[int, str] = {}

    def build_bm25(self, texts: List[str], chunk_ids: List[str], tokenizer: Callable[[str], List[str]] = lambda x: x.split()):
        tokenized = [tokenizer(t) for t in texts]
        self.bm25 = BM25Okapi(tokenized)
        self.corpus_texts = texts
        self.chunk_ids = chunk_ids

    def bm25_query(self, query: str, top_n: int = 100, tokenizer: Callable[[str], List[str]] = lambda x: x.split()):
        if self.bm25 is None:
            raise RuntimeError("BM25 not built")
        qtok = tokenizer(query)
        scores = self.bm25.get_scores(qtok)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_n]
        return [(self.chunk_ids[idx], float(score)) for idx, score in ranked]

    def hybrid_query(self, query: str, k: int = 10, bm25_top_n: int = 100):
        # 1. Get BM25 Ranked Results (Higher score is better)
        bm25_res = self.bm25_query(query, top_n=bm25_top_n)
        bm25_ranked = [cid for cid, score in bm25_res]
        
        # 2. Get FAISS Ranked Results (L2 Distance: Lower distance is better)
        faiss_ranked = []
        if self.faiss and hasattr(self.faiss, 'embed_texts'):
            
            # --- THE BGE BUG FIX ---
            # Asymmetric models require a strict instruction prefix for queries
            model_name = os.environ.get("EMBEDDING_MODEL", "").lower()
            if "bge" in model_name:
                faiss_query = f"Represent this sentence for searching relevant passages: {query}"
            else:
                faiss_query = query
                
            q_emb = self.faiss.embed_texts([faiss_query])
            D_all, I_all = self.faiss.search(q_emb, k=bm25_top_n)
            
            faiss_results = []
            for dist, idx in zip(D_all[0], I_all[0]):
                faiss_results.append((int(idx), float(dist)))
            
            # Sort FAISS by distance ascending (lower distance = better match)
            faiss_results.sort(key=lambda x: x[1])
            
            for fid, dist in faiss_results:
                cid = self.faiss_mapping.get(fid)
                if cid and cid not in faiss_ranked:
                    faiss_ranked.append(cid)

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_k = 60
        rrf_scores = {}
        
        for rank, cid in enumerate(bm25_ranked):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
            
        for rank, cid in enumerate(faiss_ranked):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
            
        # 4. Sort final results by RRF score descending
        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for cid, score in sorted_items[:k]:
            source = "both" if cid in bm25_ranked and cid in faiss_ranked else ("bm25" if cid in bm25_ranked else "faiss")
            results.append({"chunk_id": cid, "score": round(score, 4), "source": source})
            
        return results