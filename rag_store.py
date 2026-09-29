import os
import chromadb
from rank_bm25 import BM25Okapi

_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_db")
_client = chromadb.PersistentClient(path=_path)
_col = _client.get_or_create_collection("library", metadata={"hnsw:space": "cosine"})


def _chunk(text, size=800, overlap=150):
    text = " ".join((text or "").split())
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def add_document(filename, text, doc_type="other", uploaded_at=""):
    try:
        _col.delete(where={"filename": filename})
    except Exception as e:
        print(f"[RAG] Warning deleting {filename}: {e}")

    chunks = _chunk(text or "")
    if not chunks:
        return 0

    try:
        _col.upsert(
            ids=[f"{filename}::{i}" for i in range(len(chunks))],
            documents=chunks,
            metadatas=[
                {"filename": filename, "doc_type": doc_type,
                 "uploaded_at": uploaded_at, "chunk": i}
                for i in range(len(chunks))
            ],
        )
        return len(chunks)
    except Exception as e:
        print(f"[RAG ERROR] Failed to upsert {filename}: {e}")
        return 0


def _latest_filenames_per_type():
    try:
        all_docs = _col.get(include=["metadatas"])
        if not all_docs or not all_docs.get("metadatas"):
            return {}
        latest = {}
        for meta in all_docs["metadatas"]:
            if not meta:
                continue
            dt = meta.get("doc_type", "other")
            ts = meta.get("uploaded_at", "")
            fname = meta.get("filename", "")
            if fname and (dt not in latest or ts > latest[dt][0]):
                latest[dt] = (ts, fname)
        return {dt: fname for dt, (ts, fname) in latest.items()}
    except Exception as e:
        print(f"[RAG ERROR] _latest_filenames_per_type: {e}")
        return {}


def search(query, doc_type=None, top_k=5, latest_only=False, threshold=0.25):
    try:
        if _col.count() == 0:
            return []

        where = {"doc_type": doc_type} if doc_type else None
        res = _col.query(query_texts=[query], n_results=top_k * 3, where=where)

        if not res or not res.get("documents") or not res["documents"][0]:
            return []

        allowed_filenames = None
        if latest_only:
            allowed_filenames = set(_latest_filenames_per_type().values())

        hits = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            score = round(1 - dist, 3)
            if score < threshold:
                continue
            if allowed_filenames is not None and meta.get("filename") not in allowed_filenames:
                continue
            hits.append({
                "filename": meta.get("filename", ""),
                "doc_type": meta.get("doc_type", "other"),
                "score": score,
                "preview": doc[:100],
            })

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]
    except Exception as e:
        print(f"[RAG ERROR] search error: {e}")
        return []


def hybrid_search(query, doc_type=None, top_k=5, threshold=0.25, k_rrf=60):
    try:
        if _col.count() == 0:
            return []

        where = {"doc_type": doc_type} if doc_type else None
        all_docs = _col.get(where=where, include=["documents", "metadatas"])
        if not all_docs or not all_docs.get("documents"):
            return []

        corpus = all_docs["documents"]
        metas = all_docs["metadatas"]
        ids = all_docs["ids"]

        tokenized_corpus = [d.lower().split() for d in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(query.lower().split())
        bm25_by_id = {ids[i]: round(float(bm25_scores[i]), 3) for i in range(len(ids))}

        cosine_res = _col.query(query_texts=[query], n_results=min(top_k * 5, len(corpus)), where=where)
        cosine_by_id = {}
        if cosine_res and cosine_res.get("ids") and cosine_res["ids"][0]:
            for _id, dist in zip(cosine_res["ids"][0], cosine_res["distances"][0]):
                cosine_by_id[_id] = round(1 - dist, 3)

        cosine_rank = {doc_id: rank for rank, doc_id in
                       enumerate(sorted(cosine_by_id, key=cosine_by_id.get, reverse=True))}
        bm25_rank = {doc_id: rank for rank, doc_id in
                     enumerate(sorted(bm25_by_id, key=bm25_by_id.get, reverse=True))}

        best_by_file = {}
        for i, doc_id in enumerate(ids):
            cosine_score = cosine_by_id.get(doc_id, 0.0)
            bm25_score = bm25_by_id.get(doc_id, 0.0)
            if cosine_score < threshold and bm25_score <= 0:
                continue

            c_rank = cosine_rank.get(doc_id, len(ids))
            b_rank = bm25_rank.get(doc_id, len(ids))
            rrf = round(1 / (k_rrf + c_rank + 1) + 1 / (k_rrf + b_rank + 1), 4)

            fname = metas[i].get("filename", "")
            entry = {
                "filename": fname,
                "doc_type": metas[i].get("doc_type", "other"),
                "rrf": rrf,
                "cosine": cosine_score,
                "bm25": bm25_score,
                "preview": corpus[i][:100],
                "text": corpus[i],
            }
            if fname not in best_by_file or entry["rrf"] > best_by_file[fname]["rrf"]:
                best_by_file[fname] = entry

        hits = sorted(best_by_file.values(), key=lambda h: h["rrf"], reverse=True)
        return hits[:top_k]
    except Exception as e:
        print(f"[RAG ERROR] hybrid_search error: {e}")
        return []


def remove_document(filename):
    """RAG database se ek document poori tarah hata do."""
    try:
        _col.delete(where={"filename": filename})
    except Exception as e:
        print(f"[RAG ERROR] remove_document error: {e}")