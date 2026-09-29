"""
ai_preparation.py

Takes the analysis from ai_reasoning.py and generates a usable draft
(currently: a reply email). Uses Gemini to write the draft text.
"""

import os
import json
import re
import html
from gemini_retry import generate_with_retry
from dotenv import load_dotenv
from google import genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_reply_draft(original_text: str, analysis: dict) -> dict:
    """
    Generates a draft reply based on the original document text and its analysis.
    Returns: {"success": True, "draft": "..."} or {"success": False, "error": "..."}
    """
    if not original_text or not original_text.strip():
        return {"success": False, "error": "No original text provided."}

    analysis = analysis or {}
    prompt = f"""You are an assistant helping a user draft a reply to the following message.

ORIGINAL MESSAGE:
{original_text[:4000]}

CONTEXT (extracted analysis of the message):
- Type: {analysis.get('task_type', 'unknown')}
- Summary: {analysis.get('summary', '')}
- What's needed: {analysis.get('recipient_or_purpose', '')}

Write a polite, professional draft reply that addresses what is being asked. Keep it concise (3-6 sentences). Do not invent specific facts (dates, names, numbers) that were not in the original message or context — if something like availability or a specific answer is needed from the user, leave a clear placeholder like [YOUR ANSWER HERE].

Respond with ONLY the draft reply text, nothing else — no subject line, no explanation, no markdown formatting.
"""

    try:
        response = generate_with_retry(contents=prompt)
        draft = response.text.strip() if response and hasattr(response, "text") else ""

        if not draft:
            return {"success": False, "error": "AI returned an empty draft."}

        return {"success": True, "draft": draft}

    except Exception as e:
        return {"success": False, "error": f"Draft generation failed: {str(e)}"}


def generate_cover_letter(cv_text: str, job_text: str, job_analysis: dict) -> dict:
    """
    Generates a tailored cover letter based on the user's CV and a job posting.
    Returns: {"success": True, "draft": "..."} or {"success": False, "error": "..."}
    """
    if not cv_text or not cv_text.strip():
        return {"success": False, "error": "No CV text provided."}
    if not job_text or not job_text.strip():
        return {"success": False, "error": "No job posting text provided."}

    job_analysis = job_analysis or {}
    req_docs = job_analysis.get("required_documents", [])
    if isinstance(req_docs, list):
        req_str = ", ".join(str(d) for d in req_docs)
    else:
        req_str = str(req_docs)

    prompt = f"""You are an assistant helping a user write a tailored cover letter for a job application.

CANDIDATE'S CV/BACKGROUND:
{cv_text[:3000]}

JOB POSTING:
{job_text[:3000]}

CONTEXT (extracted analysis of the job posting):
- Role/Purpose: {job_analysis.get('recipient_or_purpose', '')}
- Requirements: {req_str}

Write a professional, tailored cover letter (4-6 short paragraphs) that:
1. Connects the candidate's actual background/skills (from the CV above) to the job requirements
2. Only uses facts that are actually present in the CV — do not invent experience, skills, or achievements not listed
3. Is enthusiastic but professional in tone
4. Ends with a call to action

Respond with ONLY the cover letter text, nothing else — no subject line, no explanation, no markdown formatting.
"""

    try:
        response = generate_with_retry(contents=prompt)
        draft = response.text.strip() if response and hasattr(response, "text") else ""

        if not draft:
            return {"success": False, "error": "AI returned an empty cover letter."}

        return {"success": True, "draft": draft}

    except Exception as e:
        return {"success": False, "error": f"Cover letter generation failed: {str(e)}"}


def save_draft_as_pdf(draft_text: str, output_path: str) -> dict:
    """
    Saves a draft text as a formatted PDF file using ReportLab.
    Returns: {"success": True, "path": "..."} or {"success": False, "error": "..."}
    """
    if not draft_text or not draft_text.strip():
        return {"success": False, "error": "No draft text provided."}

    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        paragraphs = draft_text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if para:
                # Escape XML special characters to prevent ReportLab parsing crash
                para_escaped = html.escape(para).replace("\n", "<br/>")
                story.append(Paragraph(para_escaped, styles["Normal"]))
                story.append(Spacer(1, 12))

        doc.build(story)
        return {"success": True, "path": output_path}

    except Exception as e:
        return {"success": False, "error": f"PDF generation failed: {str(e)}"}


def extract_cv_fields(cv_text: str) -> dict:
    """
    Extracts structured fields from a CV using Gemini, for use in application forms.
    Returns: {"success": True, "fields": {...}} or {"success": False, "error": "..."}
    """
    if not cv_text or not cv_text.strip():
        return {"success": False, "error": "No CV text provided."}

    prompt = f"""Extract the following fields from this CV. Only use information actually present in the CV — do not invent anything. If a field is not found, use null.

CV TEXT:
{cv_text[:4000]}

Return ONLY a valid JSON object with these exact keys:
{{
  "full_name": "",
  "email": "",
  "phone": "",
  "education": "",
  "skills": [],
  "experience": ""
}}

Respond with ONLY the JSON object, nothing else — no markdown formatting, no explanation.
"""

    raw_text = ""
    try:
        response = generate_with_retry(contents=prompt)
        raw_text = (response.text if response and hasattr(response, "text") else "").strip()

        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(0)

        fields = json.loads(raw_text)
        return {"success": True, "fields": fields}

    except json.JSONDecodeError:
        return {"success": False, "error": "AI did not return valid JSON.", "raw": raw_text}
    except Exception as e:
        return {"success": False, "error": f"CV field extraction failed: {str(e)}"}


def preview_draft(draft_text: str, draft_type: str = "Document") -> None:
    """
    Displays a formatted preview of a draft before approval.
    Does not return anything — just prints a clean preview to the console.
    """
    separator = "=" * 60

    print(f"\n{separator}")
    print(f"PREVIEW: {draft_type}")
    print(separator)
    print(draft_text)
    print(separator)
    print("Status: Awaiting approval\n")


def review_draft(draft_text: str, draft_type: str = "Document") -> dict:
    """
    Shows a preview of the draft and lets the user approve, edit, or reject it.
    Returns: {"status": "approved", "text": "..."} or {"status": "rejected"}
    """
    current_text = draft_text

    while True:
        preview_draft(current_text, draft_type)

        choice = input("Approve, Edit, or Reject this draft? (A/E/R): ").strip().lower()

        if choice == "a":
            return {"status": "approved", "text": current_text}

        elif choice == "e":
            print("\nEnter your edited version below (paste full text, then press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            current_text = "\n".join(lines)

        elif choice == "r":
            return {"status": "rejected"}

        else:
            print("Invalid choice. Please type A, E, or R.\n")


def generate_financial_declaration(analysis: dict, declarant_name: str = "[YOUR NAME]") -> dict:
    """
    Generates a financial declaration form using template logic.
    Handles both direct data dicts and task analysis dicts.
    Returns: {"success": bool, "draft": str, "error": str}
    """
    try:
        analysis = analysis or {}

        # If direct data dict passed (with CNIC)
        if "cnic" in analysis or "place" in analysis:
            name = analysis.get("name") or declarant_name
            cnic = analysis.get("cnic", "[CNIC NOT PROVIDED]")
            amount = analysis.get("amount", "[AMOUNT NOT SPECIFIED]")
            purpose = analysis.get("purpose") or analysis.get("recipient_or_purpose", "[PURPOSE NOT SPECIFIED]")
            date_str = analysis.get("date", "[TODAY'S DATE]")
            place = analysis.get("place", "[LOCATION]")

            form_text = f"""FINANCIAL DECLARATION

I, {name}, holder of CNIC No. {cnic}, hereby declare that the amount of {amount} is being submitted/utilized for the purpose of: {purpose}.

I affirm that the above information is true and correct to the best of my knowledge, and I take full responsibility for its accuracy.

Place: {place}
Date: {date_str}

Signature: _______________________
{name}"""
        else:
            task_type = analysis.get("task_type", "N/A")
            summary = analysis.get("summary", "N/A")
            deadline = analysis.get("deadline", "N/A")
            amount = analysis.get("amount", "N/A")
            recipient = analysis.get("recipient_or_purpose", "N/A")
            required_documents = analysis.get("required_documents", [])
            key_details = analysis.get("key_details", "N/A")

            docs_list = "\n".join(f"  - {doc}" for doc in required_documents) if required_documents else "  - None specified"

            form_text = f"""FINANCIAL / GENERIC DECLARATION FORM
{"=" * 45}

Declarant Name: {declarant_name}
Date of Declaration: [TODAY'S DATE]

Purpose / Task Type: {task_type}

Summary of Request:
{summary}

Financial Details:
  Amount Involved: {amount}
  Deadline: {deadline}

Recipient / Purpose:
  {recipient}

Supporting Documents Attached:
{docs_list}

Additional Notes:
  {key_details}

Declaration:
I, {declarant_name}, hereby declare that the information provided above is true and
accurate to the best of my knowledge, and I am submitting this in relation to the
above-mentioned purpose.

Signature: ___________________________
Date: ___________________________
"""

        return {"success": True, "draft": form_text, "error": ""}

    except Exception as e:
        return {"success": False, "draft": "", "error": str(e)}


def generate_application_form(cv_fields: dict, job_analysis: dict) -> dict:
    """
    Fills a generic job application form using parsed CV fields and job document analysis.
    No AI call - pure template fill logic.
    """
    try:
        cv_fields = cv_fields or {}
        job_analysis = job_analysis or {}

        name = cv_fields.get("full_name") or cv_fields.get("name", "[NAME NOT FOUND]")
        email_val = cv_fields.get("email", "[EMAIL NOT FOUND]")
        phone_val = cv_fields.get("phone", "[PHONE NOT FOUND]")
        linkedin = cv_fields.get("linkedin", "[LINKEDIN NOT FOUND]")
        github = cv_fields.get("github", "[GITHUB NOT FOUND]")

        job_type = job_analysis.get("task_type", "N/A")
        summary = job_analysis.get("summary", "N/A")
        deadline = job_analysis.get("deadline", "N/A")
        recipient = job_analysis.get("recipient_or_purpose", "N/A")
        required_documents = job_analysis.get("required_documents", [])

        docs_list = "\n".join(f"  - {doc}" for doc in required_documents) if required_documents else "  - None specified"

        form_text = f"""JOB / PROGRAM APPLICATION FORM
{"=" * 45}

Applicant Information (auto-filled from your CV):
  Full Name:   {name}
  Email:       {email_val}
  Phone:       {phone_val}
  LinkedIn:    {linkedin}
  GitHub:      {github}

Application For: {job_type}
Position / Purpose: {recipient}

Summary of Opportunity:
{summary}

Submission Deadline: {deadline}

Documents to Submit:
{docs_list}

Applicant Declaration:
I confirm that the information above is accurate and reflects my current CV.

Signature: ___________________________
Date: ___________________________
"""
        return {"success": True, "draft": form_text, "error": ""}

    except Exception as e:
        return {"success": False, "draft": "", "error": str(e)}