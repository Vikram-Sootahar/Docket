"""Natural-language command routing - understands user commands and maps them to actions."""
import os
import json
import re
from gemini_retry import generate_with_retry

VALID_ACTIONS = ["generate_draft", "check_documents", "approve", "reject", "summarize"]


def route_command(command_text: str, documents: list[dict]) -> dict:
    """
    documents: list of {"filename": str, "task_type": str}
    Returns: {"success": bool, "filename": str, "action": str, "error": str}
    """
    if not documents:
        return {"success": False, "filename": "", "action": "", "error": "No documents available."}

    doc_list_text = "\n".join(
        f"- {d.get('filename', '')} (type: {d.get('task_type', 'other')})"
        for d in documents if isinstance(d, dict) and d.get("filename")
    )

    if not doc_list_text.strip():
        return {"success": False, "filename": "", "action": "", "error": "No valid documents to route."}

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

    raw_text = ""
    try:
        response = generate_with_retry(contents=prompt)
        raw_text = (response.text if response and hasattr(response, "text") else "").strip()

        # Extract JSON block robustly
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(0)

        parsed = json.loads(raw_text)

        filename = str(parsed.get("filename", "") or "").strip()
        action = str(parsed.get("action", "") or "").strip()

        valid_filenames = [d.get("filename", "") for d in documents if isinstance(d, dict)]
        if filename not in valid_filenames:
            return {"success": False, "filename": "", "action": "", "error": "Could not match command to a known document."}

        if action not in VALID_ACTIONS:
            return {"success": False, "filename": "", "action": "", "error": "Could not understand the requested action."}

        return {"success": True, "filename": filename, "action": action, "error": ""}

    except Exception as e:
        return {"success": False, "filename": "", "action": "", "error": str(e)}