import os
import chromadb

_path = os.environ.get("RAG_DB_DIR") or os.path.join(os.path.expanduser("~"), "AdminAgentData", "rag_db")
os.makedirs(_path, exist_ok=True)
_client = chromadb.PersistentClient(path=_path)
_col = _client.get_or_create_collection("library", metadata={"hnsw:space": "cosine"})


def _chunk(text, size=800, overlap=150):
    text = " ".join(text.split())
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def add_document(filename, text, doc_type="other", uploaded_at=""):
    _col.delete(where={"filename": filename})
    chunks = _chunk(text)
    if not chunks:
        return 0
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


def _latest_files():
    """Har doc_type ki sabse nayi uploaded file ka naam."""
    metas = _col.get(include=["metadatas"])["metadatas"]
    latest = {}
    for m in metas:
        t = m["doc_type"]
        if t not in latest or m["uploaded_at"] > latest[t][1]:
            latest[t] = (m["filename"], m["uploaded_at"])
    return [name for name, _ in latest.values()]


def search(query, doc_type=None, top_k=10, min_score=0.2, latest_only=False):
    total = _col.count()
    if total == 0:
        return []

    conditions = []
    if doc_type:
        conditions.append({"doc_type": doc_type})
    if latest_only:
        conditions.append({"filename": {"$in": _latest_files()}})
    if len(conditions) == 0:
        where = None
    elif len(conditions) == 1:
        where = conditions[0]
    else:
        where = {"$and": conditions}

    res = _col.query(query_texts=[query], n_results=min(top_k, total), where=where)

    best = {}  # har file ka sabse achha chunk
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        score = round(1 - dist, 3)
        name = meta["filename"]
        if name not in best or score > best[name]["score"]:
            best[name] = {
                "filename": name,
                "doc_type": meta["doc_type"],
                "uploaded_at": meta["uploaded_at"],
                "score": score,
                "preview": doc[:100],
            }

    hits = [h for h in best.values() if h["score"] >= min_score]
    return sorted(hits, key=lambda h: h["score"], reverse=True)

import re
from rank_bm25 import BM25Okapi

_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with",
         "is", "are", "my", "me", "i", "from", "this", "that", "it", "as", "at", "by", "be"}


def _tok(text):
    return [w for w in re.findall(r"\w+", text.lower()) if w not in _STOP]


def _where(doc_type, latest_only):
    conditions = []
    if doc_type:
        conditions.append({"doc_type": doc_type})
    if latest_only:
        conditions.append({"filename": {"$in": _latest_files()}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def hybrid_search(query, doc_type=None, top_k=5, min_score=0.2, latest_only=False, pool=20):
    total = _col.count()
    if total == 0:
        return []
    where = _where(doc_type, latest_only)

    # 1) vector search
    v = _col.query(query_texts=[query], n_results=min(pool, total), where=where)
    vec = {}
    for rank, (cid, dist) in enumerate(zip(v["ids"][0], v["distances"][0])):
        vec[cid] = (rank, round(1 - dist, 3))

    # 2) keyword search (BM25)
    allc = _col.get(where=where, include=["documents", "metadatas"])
    ids, docs, metas = allc["ids"], allc["documents"], allc["metadatas"]
    if not ids:
        return []
    bm = BM25Okapi([_tok(d) or ["_"] for d in docs])
    scores = bm.get_scores(_tok(query))
    order = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)
    kw = {}
    for rank, i in enumerate(order):
        if scores[i] > 0:
            kw[ids[i]] = (rank, float(scores[i]))

    # 3) dono ko milao (Reciprocal Rank Fusion)
    info = {ids[i]: (docs[i], metas[i]) for i in range(len(ids))}
    best = {}
    for cid in set(vec) | set(kw):
        s = 0.0
        if cid in vec:
            s += 1 / (60 + vec[cid][0])
        if cid in kw:
            s += 1 / (60 + kw[cid][0])
        cos = vec[cid][1] if cid in vec else 0.0
        bm25s = kw[cid][1] if cid in kw else 0.0
        if cos < min_score and bm25s <= 0:
            continue
        doc, meta = info[cid]
        name = meta["filename"]
        if name not in best or s > best[name]["rrf"]:
            best[name] = {"filename": name, "doc_type": meta["doc_type"],
                          "rrf": round(s, 4), "cosine": cos,
                          "bm25": round(bm25s, 2), "preview": doc[:100], "text": doc}
    return sorted(best.values(), key=lambda h: h["rrf"], reverse=True)[:top_k]

from flashrank import Ranker, RerankRequest

_ranker = None


def _get_ranker():
    global _ranker
    if _ranker is None:
        cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rerank_cache")
        _ranker = Ranker(cache_dir=cache)
    return _ranker


def rerank_search(query, doc_type=None, latest_only=False, top_k=3, pool=10, min_score=0.2):
    cands = hybrid_search(query, doc_type=doc_type, top_k=pool,
                          min_score=min_score, latest_only=latest_only)
    if not cands:
        return []
    passages = [{"id": i, "text": c["text"]} for i, c in enumerate(cands)]
    ranked = _get_ranker().rerank(RerankRequest(query=query, passages=passages))
    out = []
    for r in ranked[:top_k]:
        c = dict(cands[r["id"]])
        c["rerank"] = round(float(r["score"]), 3)
        out.append(c)
    return out

def remove_document(filename):
    _col.delete(where={"filename": filename})