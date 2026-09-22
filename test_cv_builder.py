from cv_builder import build_cv_pdf

sample = {
    "name": "peter",
    "contact": {
        "email": "peter@example.com",
        "phone": "0322-0000000",
        "location": "Hyderabad, Pakistan",
        "links": ["github.com/example-user"],
    },
    "summary": "Final-year software engineering student interested in data science and machine learning.",
    "education": [
        {"degree": "BS Software Engineering", "institution": "Example University",
         "dates": "2022 - 2026", "details": ["CGPA: 3.5/4.0", "Final year project on crop disease detection"]},
    ],
    "skills": ["Python", "SQL", "Machine Learning", "Data Analysis"],
    "experience": [
        {"title": "Volunteer Mentor", "organization": "Example Youth Organization", "dates": "2024 - Present",
         "bullets": ["Guided students in learning programming basics", "Organized weekly study sessions"]},
    ],
    "projects": [
        {"name": "AdminAgent", "bullets": ["AI assistant that reads documents and prepares drafts for approval"]},
    ],
    "certifications": ["Google Prompting Essentials"],
}

print(build_cv_pdf(sample, "test_cv_builder_output.pdf"))