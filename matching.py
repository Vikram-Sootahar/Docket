"""Document matching logic - compares required documents against user's uploaded library. No AI/API calls."""

import difflib
import re
from datetime import datetime


def guess_category(filename: str) -> str:
    """Guess a document category from its filename, no AI needed."""
    name = filename.lower()

    if any(word in name for word in ["cv", "resume"]):
        return "CV/Resume"
    if "transcript" in name:
        return "Transcript"
    if any(word in name for word in ["photo", "picture", "pic", "headshot"]) or name.endswith((".jpg", ".jpeg", ".png")):
        return "Photo"
    if any(word in name for word in ["bank", "statement", "financial", "income", "salary"]):
        return "Financial Document"
    if any(word in name for word in ["passport", "id", "cnic", "national"]):
        return "ID Document"
    if any(word in name for word in ["cert", "certificate", "diploma", "degree"]):
        return "Certificate"

    return "Other"


def get_latest_per_category(library_items: list[dict]) -> list[dict]:
    """
    Given all library items (with 'category' and 'uploaded_at' timestamp strings),
    mark only the most recently uploaded item per category as is_latest=True.
    Returns the same list with an added/updated 'is_latest' key.
    """
    latest_by_category = {}

    for item in library_items:
        category = item["category"]
        uploaded_at = item.get("uploaded_at", "")

        if category not in latest_by_category:
            latest_by_category[category] = item
        else:
            if uploaded_at > latest_by_category[category].get("uploaded_at", ""):
                latest_by_category[category] = item

    latest_filenames = {v["filename"] for v in latest_by_category.values()}

    result = []
    for item in library_items:
        new_item = dict(item)
        new_item["is_latest"] = item["filename"] in latest_filenames
        result.append(new_item)

    return result


def match_documents(required_documents: list[str], library_items: list[dict]) -> list[dict]:
    """
    Compare a list of required document names against the user's document library.
    Only the LATEST version per category is used for matching (older versions ignored).
    Returns a list of dicts: {document, status, matched_file, confidence}
    """
    items_with_latest = get_latest_per_category(library_items)
    usable_items = [item for item in items_with_latest if item["is_latest"]]

    results = []

    for req in required_documents:
        best_match = ""
        best_score = 0.0

        for lib_item in usable_items:
            score_category = difflib.SequenceMatcher(
                None, req.lower(), lib_item["category"].lower()
            ).ratio()
            score_filename = difflib.SequenceMatcher(
                None, req.lower(), lib_item["filename"].lower()
            ).ratio()
            score = max(score_category, score_filename)

            if score > best_score:
                best_score = score
                best_match = lib_item["filename"]

        status = "matched" if best_score >= 0.35 else "missing"

        results.append({
            "document": req,
            "status": status,
            "matched_file": best_match if status == "matched" else "",
            "confidence": round(best_score * 100),
        })

    return results

_QUERY_HINTS = {
    "cv": "curriculum vitae resume skills education work experience",
    "resume": "curriculum vitae resume skills education work experience",
    "transcript": "academic transcript semester results grades GPA courses",
    "photo": "passport size photograph portrait picture",
    "bank": "bank statement account balance transactions",
    "id": "national identity card CNIC identification number",
    "passport": "passport identification travel document",
    "certificate": "certificate diploma degree awarded",
}

_MATCH_THRESHOLD = 0.30


def _expand_query(req: str) -> str:
    words = set(re.findall(r"\w+", req.lower()))
    extra = [hint for key, hint in _QUERY_HINTS.items() if key in words]
    return req + " " + " ".join(extra)


def match_documents_rag(required_documents: list[str], library_items: list[dict]) -> list[dict]:
    """Content-based matching via RAG (ChromaDB). Falls back to filename matching on any error."""
    try:
        from rag_store import hybrid_search

        latest = {i["filename"] for i in get_latest_per_category(library_items) if i["is_latest"]}
        results = []

        for req in required_documents:
            hits = hybrid_search(_expand_query(req), top_k=10, min_score=0.1)
            hits = [h for h in hits if h["filename"] in latest]

            rag_name, rag_score = "", 0.0
            if hits:
                rag_name, rag_score = hits[0]["filename"], hits[0]["cosine"]

            old = match_documents([req], library_items)[0]
            old_score = old["confidence"] / 100
            if old_score < 0.6:
                old_score = 0.0  

            if rag_score >= old_score:
                name, score = rag_name, rag_score
            else:
                name, score = old["matched_file"], old_score

            print(f"[RAG-MATCH] {req!r} -> rag={rag_name}:{rag_score:.2f} filename={old_score:.2f}")

            status = "matched" if score >= _MATCH_THRESHOLD and name else "missing"
            results.append({
                "document": req,
                "status": status,
                "matched_file": name if status == "matched" else "",
                "confidence": round(score * 100),
            })
        return results
    except Exception as e:
        print(f"[RAG-MATCH] error, falling back to filename matching: {e}")
        return match_documents(required_documents, library_items)