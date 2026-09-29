from rag_store import add_document, remove_document
from matching import match_documents_rag

# ek file jiske naam mein koi hint nahi, lekin andar transcript ka text hai
add_document("IMG_2031.jpeg",
    "Semester 1 Result. Course Code CS101 Grade A. GPA 3.5. Sindh Agriculture University",
    doc_type="Other", uploaded_at="2026-09-20T12:30:00")

lib = [
    {"filename": "Transcript.jpeg", "category": "Transcript", "uploaded_at": "2026-09-20T12:22:00"},
    {"filename": "IMG_2031.jpeg", "category": "Other", "uploaded_at": "2026-09-20T12:30:00"},
]
for m in match_documents_rag(["CV", "Transcript", "Photo", "Bank Statement", "National ID"], lib):
    print(m)

remove_document("IMG_2031.jpeg")