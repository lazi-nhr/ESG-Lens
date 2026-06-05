from typing import List, Dict, Optional, Tuple
from pymongo import MongoClient, ASCENDING


class MongoStore:
    def __init__(self, uri: str, db_name: str = "rag"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        # ensure indexes
        self.db.chunks.create_index([("doc_id", ASCENDING)])
        self.db.chunks.create_index([("parent_id", ASCENDING)])

    def save_doc(self, doc: Dict):
        return self.db.docs.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    def insert_chunks(self, chunks: List[Dict], ordered: bool = False):
        if not chunks:
            return None
        # ensure each chunk has a unique _id
        for c in chunks:
            if "_id" not in c:
                c["_id"] = f"{c['doc_id']}_p{c.get('page','0')}_r{c.get('chunk_rank',0)}"
        return self.db.chunks.insert_many(chunks, ordered=ordered)

    def upsert_chunk(self, chunk: Dict):
        return self.db.chunks.replace_one({"_id": chunk["_id"]}, chunk, upsert=True)

    def find_chunks(self, filter: Dict = None, limit: int = 100):
        if filter is None:
            filter = {}
        return list(self.db.chunks.find(filter).limit(limit))

    def all_chunk_texts_and_ids(self) -> Tuple[List[str], List[str]]:
        docs = list(self.db.chunks.find({}, {"_id": 1, "text": 1}))
        # prefer cleaned text if available for retrieval/tokenization consistency
        texts = [d.get("clean_text") or d.get("text", "") for d in docs]
        ids = [d.get("_id") for d in docs]
        return texts, ids

    def save_faiss_mapping(self, mappings: List[Dict]):
        # mappings: list of {faiss_id: int, chunk_id: str}
        if not mappings:
            return None
        # replace collection for simplicity
        self.db.faiss_mapping.delete_many({})
        return self.db.faiss_mapping.insert_many(mappings)

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict]:
        return self.db.chunks.find_one({"_id": chunk_id})

    def get_faiss_mapping(self) -> Dict[int, str]:
        """Return a mapping of faiss_id -> chunk_id from the DB."""
        docs = list(self.db.faiss_mapping.find({}, {"faiss_id": 1, "chunk_id": 1}))
        mapping = {}
        for d in docs:
            try:
                mapping[int(d.get("faiss_id"))] = d.get("chunk_id")
            except Exception:
                continue
        return mapping
