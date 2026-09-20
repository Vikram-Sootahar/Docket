"""CV parsing logic - extracts structured fields from CV text using regex. No AI/API calls."""

import re


def extract_email(text: str) -> str:
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else "[EMAIL NOT FOUND]"


def extract_phone(text: str) -> str:
    match = re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}", text)
    return match.group(0).strip() if match else "[PHONE NOT FOUND]"


def extract_linkedin(text: str) -> str:
    match = re.search(r"(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9\-_/]+", text)
    return match.group(0) if match else "[LINKEDIN NOT FOUND]"


def extract_github(text: str) -> str:
    match = re.search(r"(https?://)?(www\.)?github\.com/[a-zA-Z0-9\-_/]+", text)
    return match.group(0) if match else "[GITHUB NOT FOUND]"


def extract_name(text: str) -> str:
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if lines:
        first_line = lines[0]
        if len(first_line.split()) <= 5 and "@" not in first_line:
            return first_line
    return "[NAME NOT FOUND]"


def parse_cv_fields(cv_text: str) -> dict:
    """Extract structured fields from raw CV text using pattern matching only."""
    return {
        "name": extract_name(cv_text),
        "email": extract_email(cv_text),
        "phone": extract_phone(cv_text),
        "linkedin": extract_linkedin(cv_text),
        "github": extract_github(cv_text),
    }