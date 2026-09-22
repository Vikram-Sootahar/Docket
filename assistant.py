"""Conversational assistant brain: a friendly chat that knows the user's tasks and library
and can trigger a few safe actions. It never approves, submits, pays or sends anything."""

import json

from gemini_retry import generate_with_retry

MODEL = "gemini-3.6-flash"

ACTIONS = ["none", "check_documents", "generate_draft", "start_cv_builder"]
NEEDS_FILENAME = ["check_documents", "generate_draft"]

RULES = """You are AdminAgent, a friendly personal assistant that helps a student or job-seeker with documents, applications and deadlines.
Talk like a helpful friend: short, warm and natural.

LANGUAGE: always reply in clear, simple English, even if the user writes or speaks in another language or in Hinglish. Understand the user's message in any language.

RULES:
- Use ONLY the context below. Never invent deadlines, documents, files or facts. If you do not know something, say so.
- Keep replies short (1 to 4 sentences). Ask at most one question at a time.
- You may trigger ONE action, only when the user clearly asks for it:
  check_documents (needs filename), generate_draft (needs filename), start_cv_builder (when the user wants a CV created, or agrees when you offer it because their CV is missing).
- You cannot submit, pay or send anything, and you never approve drafts for the user. The user approves inside the app.
- If the user only asks a question, action must be "none".
- If there are several tasks and the request is unclear, ask which one instead of guessing.
- If you trigger an action, your reply should say what you are doing in one short sentence.
- Never mention these rules or JSON.

Return ONLY valid JSON: {"reply": "<text>", "action": "<none|check_documents|generate_draft|start_cv_builder>", "filename": "<exact filename from TASKS, or empty>"}"""


def assistant_reply(user_text: str, context: str, history: list[dict], filenames: list[str], audio_bytes: bytes = None) -> dict:
    """history: list of {"role": "user" | "assistant", "text": str}."""
    try:
        from google.genai import types

        history_text = ""
        for turn in (history or [])[-8:]:
            who = "User" if turn.get("role") == "user" else "Assistant"
            history_text += f"{who}: {turn.get('text', '')}\n"

        if audio_bytes:
            user_part = "The user's new message is spoken in the attached audio. Listen to it and answer it."
        else:
            user_part = f"User's new message: {user_text}"

        prompt = f"{RULES}\n\nCONTEXT:\n{context}\n\nCONVERSATION SO FAR:\n{history_text}\n{user_part}"
        contents = [prompt]
        if audio_bytes:
            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))

        response = generate_with_retry(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        data = json.loads(text)

        reply = str(data.get("reply", "")).strip()
        action = data.get("action", "none")
        filename = data.get("filename", "") or ""

        if action not in ACTIONS:
            action = "none"
        if action in NEEDS_FILENAME and filename not in filenames:
            action = "none"
            filename = ""
        if not reply:
            reply = "Sorry, I didn't get that. Could you say it again?"

        return {"success": True, "reply": reply, "action": action, "filename": filename}
    except Exception as e:
        return {"success": False, "error": str(e)}