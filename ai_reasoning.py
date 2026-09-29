"""
ai_reasoning.py

Uses Gemini AI to analyze extracted text and identify:
- Task type
- Deadlines
- Required documents/information
- Amount (if any)
- Recipient or purpose
- A short summary of what needs to be done
"""

import os
import json
import re
from datetime import date
from dotenv import load_dotenv
from gemini_retry import generate_with_retry

# Load the API key from .env
load_dotenv()


def analyze_text(text: str) -> dict:
    """
    Sends extracted text to Gemini and returns a structured analysis.
    """
    if not text or not text.strip():
        return {"success": False, "error": "No text provided to analyze."}

    prompt = f"""You are an assistant that analyzes administrative documents (emails, forms, letters, applications).

Read the following text and extract this information. Respond ONLY in valid JSON, no extra text, no markdown formatting:

{{
  "task_type": "One category: scholarship, fee_payment, job_application, government_form, email_reply, or other",
  "summary": "A short 1-2 sentence summary of what this document is about and what action is needed",
  "deadline": "The deadline as an actual calendar date (e.g. 'September 19, 2026'). If the text uses a relative term like 'this Friday', 'in 5 days', 'next week', or 'tomorrow', calculate the exact real date step by step using TODAY'S DATE given below — show your calculation only to yourself, output only the final date. If the document does not clearly state or imply a specific deadline, you MUST output exactly 'None found'. Never guess or invent a date that is not directly supported by the text.",
  "required_documents": ["list", "of", "documents or items mentioned as required"],
  "amount": "Any monetary amount mentioned (e.g. fee, stipend, salary), or 'None found' if there isn't one",
  "recipient_or_purpose": "Who this is addressed to, or the purpose/goal of the task",
  "key_details": "Any other important details not covered above (contact info, links, etc.)"
}}

TODAY'S DATE: {date.today().strftime('%A, %B %d, %Y')} (a {date.today().strftime('%A')})

When the text uses a term like "next Friday" or "this Friday", that means the closest upcoming Friday from today's date above (within the next 7 days) — not the Friday after that. Count the days carefully using today's day of the week.

IMPORTANT: If any field (deadline, amount, etc.) is not clearly stated or calculable from the text, output "None found" for it. Do not fabricate information that is not present in the text.

TEXT TO ANALYZE:
{text[:8000]}
"""

    raw_output = ""
    try:
        response = generate_with_retry(contents=prompt)
        raw_output = response.text.strip() if response and hasattr(response, "text") else ""

        # Extract JSON block robustly
        json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if json_match:
            raw_output = json_match.group(0)

        parsed = json.loads(raw_output)

        req_docs = parsed.get("required_documents", [])
        if not isinstance(req_docs, list):
            req_docs = [str(req_docs)] if req_docs else []

        return {
            "success": True,
            "task_type": str(parsed.get("task_type", "other")),
            "summary": str(parsed.get("summary", "")),
            "deadline": str(parsed.get("deadline", "None found")),
            "required_documents": [str(d) for d in req_docs if d],
            "amount": str(parsed.get("amount", "None found")),
            "recipient_or_purpose": str(parsed.get("recipient_or_purpose", "")),
            "key_details": str(parsed.get("key_details", "")),
        }

    except json.JSONDecodeError:
        return {"success": False, "error": "Could not parse AI response as JSON.", "raw": raw_output}
    except Exception as e:
        return {"success": False, "error": f"AI analysis failed: {str(e)}"}