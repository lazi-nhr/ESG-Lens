"""Simple CLI for indexing and querying."""
import argparse
import os
from backend.app.db.parser import parse_pdf_to_doc
from backend.app.db.chunker import chunk_document, build_parent_chunks
from backend.app.db.store import MongoStore
from backend.app.db.indexer import FaissIndexer
from backend.app.retrieval.retriever import Retriever
from typing import List


def cmd_index(args):
    mongo_uri = args.mongodb_uri or os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MongoDB URI required via --mongodb-uri or MONGODB_URI env var")

    store = MongoStore(mongo_uri, db_name=args.db)
    indexer = FaissIndexer(model_name=args.model)

    doc = parse_pdf_to_doc(args.path)
    store.save_doc({"_id": doc["_id"], "source_path": doc["source_path"], "title": doc["title"], "pages": doc["pages"], "imported_at": doc["imported_at"]})

    chunks = chunk_document(doc["page_texts"], doc["_id"], base_tokens=args.chunk_size, overlap_tokens=args.overlap)
    parents = build_parent_chunks(chunks, group_size=args.group_size)
    # insert children and parents
    store.insert_chunks(chunks)
    store.insert_chunks(parents)

    # build embeddings and FAISS index
    texts, ids = store.all_chunk_texts_and_ids()
    if texts:
        embeddings = indexer.embed_texts(texts, batch_size=args.batch_size)
        indexer.build_index(embeddings, use_hnsw=not args.flat)
        # persist index
        if args.index_path:
            indexer.save_index(args.index_path)
        # save mapping
        mappings = [{"faiss_id": int(i), "chunk_id": cid} for i, cid in enumerate(ids)]
        store.save_faiss_mapping(mappings)

    print(f"Indexed {len(texts)} chunks and stored mapping in MongoDB")


def cmd_rebuild(args):
    # rebuild index from MongoDB
    mongo_uri = args.mongodb_uri or os.environ.get("MONGODB_URI")
    store = MongoStore(mongo_uri, db_name=args.db)
    indexer = FaissIndexer(model_name=args.model)
    texts, ids = store.all_chunk_texts_and_ids()
    if not texts:
        print("No chunks found in store")
        return
    embeddings = indexer.embed_texts(texts, batch_size=args.batch_size)
    indexer.build_index(embeddings, use_hnsw=not args.flat)
    if args.index_path:
        indexer.save_index(args.index_path)
    mappings = [{"faiss_id": int(i), "chunk_id": cid} for i, cid in enumerate(ids)]
    store.save_faiss_mapping(mappings)
    print(f"Rebuilt index with {len(ids)} items")


def cmd_query(args):
    mongo_uri = args.mongodb_uri or os.environ.get("MONGODB_URI")
    store = MongoStore(mongo_uri, db_name=args.db)
    texts, ids = store.all_chunk_texts_and_ids()
    retriever = Retriever()
    retriever.build_bm25(texts, ids)

    if args.strategy == "bm25":
        res = retriever.bm25_query(args.q, top_n=args.bm25_top)
        # print chunk_id and score
        for cid, score in res[: args.k]:
            doc = store.get_chunk_by_id(cid)
            snippet = (doc.get("text")[:300] + "...") if doc and doc.get("text") else ""
            print(cid, float(score), snippet)
        return

    # hybrid uses FAISS if index exists
    faiss_indexer = FaissIndexer(model_name=args.model)
    if args.index_path and os.path.exists(args.index_path):
        faiss_indexer.load_index(args.index_path)
        retriever.faiss = faiss_indexer
        # load mapping from store and attach to retriever
        mapping = store.get_faiss_mapping()
        retriever.faiss_mapping = mapping

    res = retriever.hybrid_query(args.q, k=args.k, bm25_top_n=args.bm25_top)
    # fetch chunk docs for output
    for r in res:
        cid = r.get("chunk_id")
        score = r.get("score")
        source = r.get("source")
        doc = store.get_chunk_by_id(cid)
        snippet = (doc.get("text")[:500] + "...") if doc and doc.get("text") else ""
        print(f"{cid}  score={score:.4f} source={source}\n{snippet}\n")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()

    p_index = sub.add_parser("index")
    p_index.add_argument("path")
    p_index.add_argument("--mongodb-uri", default=None)
    p_index.add_argument("--db", default="rag")
    p_index.add_argument("--chunk-size", type=int, default=512)
    p_index.add_argument("--overlap", type=int, default=64)
    p_index.add_argument("--group-size", type=int, default=4)
    p_index.add_argument("--batch-size", type=int, default=64)
    p_index.add_argument("--index-path", default="faiss.index")
    p_index.add_argument("--model", default="all-MiniLM-L6-v2")
    p_index.add_argument("--flat", action="store_true", help="Use flat index instead of HNSW")
    p_index.set_defaults(func=cmd_index)

    p_rebuild = sub.add_parser("rebuild")
    p_rebuild.add_argument("--mongodb-uri", default=None)
    p_rebuild.add_argument("--db", default="rag")
    p_rebuild.add_argument("--index-path", default="faiss.index")
    p_rebuild.add_argument("--batch-size", type=int, default=64)
    p_rebuild.add_argument("--model", default="all-MiniLM-L6-v2")
    p_rebuild.add_argument("--flat", action="store_true")
    p_rebuild.set_defaults(func=cmd_rebuild)

    p_query = sub.add_parser("query")
    p_query.add_argument("q")
    p_query.add_argument("--k", type=int, default=10)
    p_query.add_argument("--bm25-top", type=int, default=200)
    p_query.add_argument("--strategy", choices=["bm25", "hybrid"], default="hybrid")
    p_query.add_argument("--mongodb-uri", default=None)
    p_query.add_argument("--db", default="rag")
    p_query.add_argument("--index-path", default="faiss.index")
    p_query.add_argument("--model", default="all-MiniLM-L6-v2")
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
