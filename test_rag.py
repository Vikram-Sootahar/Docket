from rag_store import add_document, search

add_document("IMG_2031.jpeg",
    "Semester 1 Result. Course Code CS101 Grade A. GPA 3.5. Sindh Agriculture University",
    doc_type="transcript", uploaded_at="2026-09-01")
add_document("cv_old.docx",
    "Vikram. Skills: Python. Education: BS Software Engineering. Experience: intern",
    doc_type="cv", uploaded_at="2026-08-01")
add_document("cv_new.docx",
    "Vikram. Skills: Python, Machine Learning, Reflex. Education: BS Software Engineering. Experience: freelance data science",
    doc_type="cv", uploaded_at="2026-09-15")

print("--- 1. transcript query")
for h in search("academic transcript with grades"):
    print(h["filename"], h["score"])

print("--- 2. CV query, latest_only (cv_new hi aana chahiye, cv_old nahi)")
for h in search("CV with skills and education", latest_only=True):
    print(h["filename"], h["score"])

print("--- 3. bekaar query (kuch nahi aana chahiye)")
print(search("cricket world cup final"))

from rag_store import hybrid_search

print("--- 4. exact keyword: CS101")
for h in hybrid_search("CS101"):
    print(h["filename"], "cosine", h["cosine"], "bm25", h["bm25"])

print("--- 5. hybrid, transcript query")
for h in hybrid_search("academic transcript with grades"):
    print(h["filename"], "cosine", h["cosine"], "bm25", h["bm25"])

print("--- 6. bekaar query")
print(hybrid_search("cricket world cup final"))