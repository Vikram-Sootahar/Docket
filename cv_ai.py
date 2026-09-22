"""Turns raw interview answers into a structured CV using Gemini (never invents facts)."""

import json

from gemini_retry import generate_with_retry
from ai_chat import client

MODEL = "gemini-3.6-flash"


def structure_cv(answers: dict) -> dict:
    try:
        from google.genai import types

        prompt = (
            "You are helping a student write a CV. Below are their raw answers to interview questions.\n"
            "Turn them into a clean, professional CV in English.\n\n"
            "STRICT RULES:\n"
            "- Use ONLY facts present in the answers. Never invent employers, dates, numbers, skills, degrees or achievements.\n"
            "- You may fix grammar, translate to English and rephrase into concise professional bullet points.\n"
            "- If an answer is 'skip', 'none', empty or not relevant, return an empty list for that section.\n"
            "- summary: 1-2 sentences using only the given facts. If there is too little information, return an empty string.\n"
            "- Keep contact details exactly as given.\n\n"
            "Return ONLY valid JSON with exactly this shape:\n"
            '{"name": str, "contact": {"email": str, "phone": str, "location": str, "links": [str]}, '
            '"summary": str, '
            '"education": [{"degree": str, "institution": str, "dates": str, "details": [str]}], '
            '"skills": [str], '
            '"experience": [{"title": str, "organization": str, "dates": str, "bullets": [str]}], '
            '"projects": [{"name": str, "bullets": [str]}], '
            '"certifications": [str]}\n\n'
            f"ANSWERS:\n{json.dumps(answers, ensure_ascii=False, indent=2)}"
        )
        response = generate_with_retry(
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        cv = json.loads(text)
        if not isinstance(cv, dict):
            return {"success": False, "error": "Model did not return a JSON object"}
        return {"success": True, "cv": cv}
    except Exception as e:
        return {"success": False, "error": str(e)}