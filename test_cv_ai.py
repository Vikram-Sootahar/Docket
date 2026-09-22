import json

from cv_ai import structure_cv
from cv_builder import build_cv_pdf

answers = {
    "name": "mera naam ali khan hai",
    "contact": "ali.khan@example.com, 0300-0000000, hyderabad, github.com/example-user",
    "education": "bs software engineering example university se, 2022 se 2026, cgpa 3.5",
    "skills": "python, sql, machine learning",
    "experience": "youth organization mein mentor, 2024 se abhi tak, students ko programming sikhata hoon",
    "projects": "AdminAgent - ai jo documents padh kar drafts banata hai",
    "certifications": "skip",
}

result = structure_cv(answers)
print(json.dumps(result, indent=2, ensure_ascii=False))
if result["success"]:
    print(build_cv_pdf(result["cv"], "test_cv_ai_output.pdf"))