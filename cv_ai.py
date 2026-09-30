"""Turns raw interview answers into a structured CV using Gemini (expands sparse facts into a polished, professional CV without inventing new facts)."""

import json

from gemini_retry import generate_with_retry
from ai_chat import client

MODEL = "gemini-3.6-flash"


def structure_cv(answers: dict) -> dict:
    try:
        from google.genai import types

        prompt = (
            "You are an expert CV writer helping a student turn short, informal interview answers "
            "into a polished, highly professional CV in English.\n\n"
            "HOW TO THINK ABOUT THIS:\n"
            "The person will give you sparse, casual notes — sometimes just a tool name, a project title, "
            "or one short sentence. Your job is to expand that into confident, detailed, professional "
            "writing, the way a skilled resume writer would. Do not just lightly rephrase their words — "
            "elaborate on them using your own knowledge of what that work typically involves.\n\n"
            "WHAT YOU MAY ADD (grounded elaboration):\n"
            "- If they name a technology, tool, or method (e.g. 'used Python', 'built with RAG', 'used SQL'), "
            "you may describe, in the context of the stated project or role, what that tool is commonly used "
            "for and the kind of technical work it implies — e.g. 'used Python' inside a described data project "
            "can become 'Built data-processing scripts in Python to clean and analyze [the stated dataset/topic]'. "
            "Ground this elaboration strictly in the project or role they actually described; do not invent a "
            "different project, technology, employer, number, date, or outcome that was never mentioned.\n"
            "- You may write confident, professional bullet phrasing for something they described in only one "
            "short sentence (e.g. 'was a mentor' becomes a bullet about guiding/supporting others), as long as "
            "the bullet stays a natural professional description of that same stated activity, not a new claim.\n\n"
            "WHAT YOU MAY NEVER ADD (invented facts):\n"
            "- Never invent employers, organizations, dates, durations, team sizes, specific numbers/metrics, "
            "degrees, certifications, or named tools/technologies the person did not mention anywhere.\n"
            "- Do NOT infer a field of study, profession, or category (e.g. do not write 'Agricultural student') "
            "unless those exact words or a clear equivalent appear in the answers.\n"
            "- If you are not sure whether something is implied or invented, leave it out.\n\n"
            "OTHER RULES:\n"
            "- If an answer is 'skip', 'none', empty, or truly gives nothing to work with, return an empty "
            "list/string for that section instead of guessing.\n"
            "- summary: 2-3 sentences, written at a highly professional, confident level, based only on the "
            "stated facts (field, skills, experience). If there is truly too little information to write any "
            "summary, return an empty string rather than inventing one.\n"
            "- experience: if any answer mentions a job, internship, volunteering, or work-like activity, create "
            "an experience entry with 2-3 detailed, professional bullets describing the work, expanded using the "
            "grounded-elaboration rule above. Never leave this empty if the person described any activity at all.\n"
            "- projects: same as experience — expand a short project description into 2-3 technical, professional "
            "bullets about what was built and how, grounded in the technologies/goals they actually named.\n"
            "- skills: list every tool, language, or method mentioned anywhere in the answers (including inside "
            "project/experience descriptions), properly capitalized (e.g. 'Python' not 'python').\n"
            "- Some answers may be transcribed from voice and contain filler words (um, uh) or false starts — "
            "clean these up but do not change the meaning.\n"
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