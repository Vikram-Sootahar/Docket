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
from datetime import date
from dotenv import load_dotenv
import google.generativeai as genai

# Load the API key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-3.6-flash")


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
  "deadline": "The deadline as an actual calendar date (e.g. 'September 19, 2026'). If the text uses a relative term like 'this Friday', 'in 5 days', 'next week', or 'tomorrow', calculate the real date using TODAY'S DATE given below. If no deadline is mentioned at all, use 'None found'.",
  "required_documents": ["list", "of", "documents or items mentioned as required"],
  "amount": "Any monetary amount mentioned (e.g. fee, stipend, salary), or 'None found' if there isn't one",
  "recipient_or_purpose": "Who this is addressed to, or the purpose/goal of the task",
  "key_details": "Any other important details not covered above (contact info, links, etc.)"
}}

TODAY'S DATE: {date.today().strftime('%B %d, %Y')}

TEXT TO ANALYZE:
{text[:8000]}
"""

    try:
        response = model.generate_content(prompt)
        raw_output = response.text.strip()

        if raw_output.startswith("```"):
            raw_output = raw_output.strip("`")
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
            raw_output = raw_output.strip()

        parsed = json.loads(raw_output)

        return {
            "success": True,
            "task_type": parsed.get("task_type", "other"),
            "summary": parsed.get("summary", ""),
            "deadline": parsed.get("deadline", "None found"),
            "required_documents": parsed.get("required_documents", []),
            "amount": parsed.get("amount", "None found"),
            "recipient_or_purpose": parsed.get("recipient_or_purpose", ""),
            "key_details": parsed.get("key_details", ""),
        }

    except json.JSONDecodeError:
        return {"success": False, "error": "Could not parse AI response as JSON.", "raw": raw_output}
    except Exception as e:
        return {"success": False, "error": f"AI analysis failed: {str(e)}"}