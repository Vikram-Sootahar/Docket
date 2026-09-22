"""
ai_chat.py

Lets the user ask free-form questions about an uploaded document.
The AI answers using only the document's extracted text as context,
and remembers the conversation so far for follow-up questions.
"""

import os
from dotenv import load_dotenv
from google import genai
from gemini_retry import generate_with_retry

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def answer_question(document_text: str, question: str, history: list[dict] = None) -> dict:
    """
    Answers a user's question about a document, using the document text as context
    plus any prior Q&A in this conversation.

    history: list of {"question": "...", "answer": "..."} from earlier turns.

    Returns: {"success": True, "answer": "..."} or {"success": False, "error": "..."}
    """
    if not document_text or not document_text.strip():
        return {"success": False, "error": "No document text provided."}
    if not question or not question.strip():
        return {"success": False, "error": "No question provided."}

    history = history or []

    conversation_so_far = ""
    for turn in history:
        conversation_so_far += f"Q: {turn['question']}\nA: {turn['answer']}\n\n"

    prompt = f"""You are an assistant answering questions about a specific document. Only use information from the document below to answer. If the answer is not in the document, say so clearly — do not invent information.

DOCUMENT TEXT:
{document_text[:6000]}

CONVERSATION SO FAR:
{conversation_so_far if conversation_so_far else "(no prior questions)"}

NEW QUESTION:
{question}

Respond with a clear, concise answer (2-4 sentences). No markdown formatting.
"""

    try:
        response = generate_with_retry(
            model="gemini-3.6-flash",
            contents=prompt
        )
        answer = response.text.strip()

        if not answer:
            return {"success": False, "error": "AI returned an empty answer."}

        return {"success": True, "answer": answer}

    except Exception as e:
        return {"success": False, "error": f"Chat answer failed: {str(e)}"}

def answer_question_multi(documents: list[dict], question: str, history: list[dict] = None) -> dict:
    """
    Answers a user's question using MULTIPLE documents as combined context.

    documents: list of {"filename": "...", "text": "..."} for each uploaded file.
    history: list of {"question": "...", "answer": "..."} from earlier turns.

    Returns: {"success": True, "answer": "..."} or {"success": False, "error": "..."}
    """
    if not documents:
        return {"success": False, "error": "No documents provided."}
    if not question or not question.strip():
        return {"success": False, "error": "No question provided."}

    history = history or []

    conversation_so_far = ""
    for turn in history:
        conversation_so_far += f"Q: {turn['question']}\nA: {turn['answer']}\n\n"

    documents_text = ""
    for doc in documents:
        documents_text += f"--- Document: {doc['filename']} ---\n{doc['text'][:4000]}\n\n"

    prompt = f"""You are an assistant answering questions using MULTIPLE documents as context. Compare, combine, or reference specific documents by name as needed to answer accurately. If the answer is not found in any document, say so clearly — do not invent information.

DOCUMENTS:
{documents_text}

CONVERSATION SO FAR:
{conversation_so_far if conversation_so_far else "(no prior questions)"}

NEW QUESTION:
{question}

Respond with a clear, concise answer (2-5 sentences). Mention which document(s) you're referencing when relevant. No markdown formatting.
"""

    try:
        response = generate_with_retry(
            model="gemini-3.6-flash",
            contents=prompt
        )
        answer = response.text.strip()

        if not answer:
            return {"success": False, "error": "AI returned an empty answer."}

        return {"success": True, "answer": answer}

    except Exception as e:
        return {"success": False, "error": f"Multi-document chat answer failed: {str(e)}"}

def answer_voice_question(document_text: str, audio_bytes: bytes, history: list[dict] = None) -> dict:
    """Answer a question spoken in a WAV voice note. Replies in text."""
    try:
        from google.genai import types

        history_text = ""
        for turn in (history or [])[-6:]:
            q = turn.get("question") or "(voice note)"
            history_text += f"User: {q}\nAssistant: {turn.get('answer', '')}\n"

        prompt = (
            "You are AdminAgent, a helpful assistant that answers questions about a document.\n"
            "The user's question is spoken in the attached audio. Listen to it and answer using the document below.\n"
            "If the audio is silent, unclear or not a question, reply briefly asking them to try again.\n"
            "Reply in plain text, short and direct, always in English, even if the user spoke another language.\n\n"
            "If the user speaks Hindi, Urdu or Hinglish, reply in Roman script (Hinglish / Roman Urdu), never in Devanagari or Arabic script.\n\n"
            f"DOCUMENT:\n{document_text}\n\n"
            f"CONVERSATION SO FAR:\n{history_text}"
        )

        response = generate_with_retry(
            model="gemini-3.6-flash",
            contents=[prompt, types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")],
        )
        return {"success": True, "answer": response.text.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}