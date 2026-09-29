from rag_store import add_document, hybrid_search, rerank_search

add_document("fee_challan.docx",
    "University fee challan. Semester 1 fee Rs 45000 paid. Bank HBL. Challan No 8891. Due date 15 Sep 2026",
    doc_type="fee", uploaded_at="2026-09-05")
add_document("inter_certificate.jpeg",
    "Board of Intermediate Education Hyderabad. Pre-Engineering certificate. Grade A. Roll No 4471",
    doc_type="certificate", uploaded_at="2026-08-20")

q = "document showing my semester grades and GPA"

print("--- hybrid order")
for h in hybrid_search(q):
    print(h["filename"], "cosine", h["cosine"], "bm25", h["bm25"])

print("--- reranked order")
for h in rerank_search(q):
    print(h["filename"], "rerank", h["rerank"])

def remove_document(filename):
    _col.delete(where={"filename": filename})