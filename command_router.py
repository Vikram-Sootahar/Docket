"""Natural-language command routing - understands user commands and maps them to actions."""

import os
import json
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

VALID_ACTIONS = ["generate_draft", "check_documents", "approve", "reject", "summarize"]


def route_command(command_text: str, documents: list[dict]) -> dict:
    """
    documents: list of {"filename": str, "task_type": str}
    Returns: {"success": bool, "filename": str, "action": str, "error": str}
    """
    if not documents:
        return {"success": False, "filename": "", "action": "", "error": "No documents available."}

    doc_list_text = "\n".join(
        f"- {d['filename']} (type: {d['task_type']})" for d in documents
    )

    prompt = f"""You are a command router for a document management app.
Available documents:
{doc_list_text}

Available actions: {", ".join(VALID_ACTIONS)}
- generate_draft: create a reply/draft for the document
- check_documents: check which required documents are available
- approve: approve the current draft
- reject: reject the current draft
- summarize: summarize the document

User command: "{command_text}"

Based on the user's command, pick the SINGLE most relevant filename from the list above, and the SINGLE most relevant action from the list above.

Respond ONLY with valid JSON, no extra text, no markdown, in this exact format:
{{"filename": "<exact filename from the list>", "action": "<one of the actions>"}}
"""

    try:
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        filename = parsed.get("filename", "")
        action = parsed.get("action", "")

        valid_filenames = [d["filename"] for d in documents]
        if filename not in valid_filenames:
            return {"success": False, "filename": "", "action": "", "error": "Could not match command to a known document."}

        if action not in VALID_ACTIONS:
            return {"success": False, "filename": "", "action": "", "error": "Could not understand the requested action."}

        return {"success": True, "filename": filename, "action": action, "error": ""}

    except Exception as e:
        return {"success": False, "filename": "", "action": "", "error": str(e)}