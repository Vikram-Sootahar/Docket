"""Docket - File Upload & Text Extraction with AI Reasoning."""

import asyncio
import json
from pathlib import Path
import reflex as rx
from pydantic import BaseModel
from file_readers import extract_text_from_file
from ai_reasoning import analyze_text
from ai_preparation import generate_reply_draft, save_draft_as_pdf, generate_financial_declaration, generate_application_form
from ai_chat import answer_question, answer_question_multi, answer_voice_question
from cv_builder import QUESTIONS as CV_QUESTIONS, build_cv_pdf, cv_to_text
from assistant import assistant_reply
from cv_ai import structure_cv
from reflex.config import get_config
from matching import match_documents, match_documents_rag, guess_category, get_latest_per_category
from rag_store import add_document as rag_add_document, remove_document as rag_remove_document
from datetime import datetime
from dashboard import build_dashboard_rows
from audit import create_log_entry
from command_router import route_command
from cv_parser import parse_cv_fields

LIBRARY_INDEX = Path("library_index.json")

CREAM = "#FAF6EC"
CREAM_DARK = "#F0E6CE"
INK = "#1A1A1A"
MUTED = "#6B6B63"
BORDER = "#E4DCC8"
ACCENT = "#D9CBA0"
DANGER = "#B03A2E"
DARK_BTN = "#1A1A1A"
FONT_SERIF = "Georgia, 'Times New Roman', serif"


class LibraryItem(BaseModel):
    """A document the user has uploaded to their personal library."""
    filename: str = ""
    category: str = ""
    uploaded_at: str = ""
    is_latest: bool = True

class DashboardRow(BaseModel):
    """A single row in the task dashboard."""
    filename: str = ""
    task_type: str = ""
    deadline: str = ""
    urgency_label: str = ""
    completion_percent: int = 0
    completion_text: str = ""
    missing: list[str] = []

class AuditLogEntry(BaseModel):
    """A single audit log entry - records an approve/reject action."""
    filename: str = ""
    action: str = ""
    task_type: str = ""
    timestamp: str = ""

class FileResult(BaseModel):
    """Structured result for one uploaded file."""
    filename: str = ""
    extraction_success: bool = False
    error: str = ""
    analysis_success: bool = False
    original_text: str = ""
    task_type: str = ""
    summary: str = ""
    deadline: str = ""
    required_documents: list[str] = []
    amount: str = ""
    recipient_or_purpose: str = ""
    key_details: str = ""
    draft_text: str = ""
    draft_generated: bool = False
    draft_status: str = "none"
    is_editing: bool = False
    chat_history: list[dict] = []
    chat_input: str = ""
    document_matches: list[dict] = []

class State(rx.State):
    """The app state."""

    results: list[FileResult] = []
    multi_chat_history: list[dict] = []
    multi_chat_input: str = ""
    recording_index: int = -1
    cv_step: int = -1
    cv_answers: dict[str, str] = {}
    cv_input: str = ""
    cv_message: str = ""
    cv_notice: str = ""
    cv_pdf_name: str = ""
    cv_pdf_url: str = ""
    cv_data: dict = {}
    assistant_history: list[dict] = []
    assistant_input: str = ""
    assistant_typing: bool = False
    assistant_recording: bool = False
    is_processing: bool = False
    library: list[LibraryItem] = []
    dashboard_rows: list[DashboardRow] = []
    audit_log: list[AuditLogEntry] = []
    command_input: str = ""
    command_result_message: str = ""

    def reset_draft(self, index: int):
        self.results[index].draft_generated = False
        self.results[index].draft_text = ""
        self.results = self.results

    def send_assistant_with_text(self, text: str):
        self.assistant_input = text or ""
        return State.send_assistant_message

    def refresh_dashboard(self):
        tasks = [
            {
                "filename": r.filename,
                "task_type": r.task_type,
                "deadline": r.deadline,
                "document_matches": r.document_matches,
            }
            for r in self.results
            if r.extraction_success and r.analysis_success
        ]
        raw_rows = build_dashboard_rows(tasks)
        self.dashboard_rows = [DashboardRow(**row) for row in raw_rows]

    def update_command_input(self, value: str):
        self.command_input = value

    def run_command(self):
        command = self.command_input.strip()
        if not command:
            return

        documents = [
            {"filename": r.filename, "task_type": r.task_type}
            for r in self.results
            if r.extraction_success and r.analysis_success
        ]

        result = route_command(command, documents)

        if not result["success"]:
            self.command_result_message = f"Sorry, I couldn't understand that: {result['error']}"
            return

        filename = result["filename"]
        action = result["action"]

        index = None
        for i, r in enumerate(self.results):
            if r.filename == filename:
                index = i
                break

        if index is None:
            self.command_result_message = "Could not find that document."
            return

        if action == "generate_draft":
            self.generate_draft(index)
            self.command_result_message = f"Generated draft for {filename}."
        elif action == "check_documents":
            self.check_required_documents(index)
            self.command_result_message = f"Checked documents for {filename}."
        elif action == "approve":
            self.approve_draft(index)
            self.command_result_message = f"Approved draft for {filename}."
        elif action == "reject":
            self.reject_draft(index)
            self.command_result_message = f"Rejected draft for {filename}."
        elif action == "summarize":
            self.ask_quick_question(index, "Summarize this document in 2 sentences.")
            self.command_result_message = f"Summarized {filename} in the chat below."
        else:
            self.command_result_message = "Unknown action."

        self.command_input = ""

    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return

        self.is_processing = True

        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        new_results = []
        for file in files:
            try:
                upload_data = await file.read()

                outfile = upload_dir / file.name
                with outfile.open("wb") as f:
                    f.write(upload_data)

                extraction = await asyncio.to_thread(extract_text_from_file, str(outfile))

                if not extraction.get("success"):
                    new_results.append(FileResult(
                        filename=file.name,
                        extraction_success=False,
                        error=extraction.get("error", "Unknown extraction error"),
                        analysis_success=False,
                    ))
                    continue

                analysis = await asyncio.to_thread(analyze_text, extraction["text"])

                if analysis.get("success"):
                    new_results.append(FileResult(
                        filename=file.name,
                        extraction_success=True,
                        analysis_success=True,
                        original_text=extraction["text"],
                        task_type=analysis.get("task_type", ""),
                        summary=analysis.get("summary", ""),
                        deadline=analysis.get("deadline", ""),
                        required_documents=analysis.get("required_documents", []),
                        amount=analysis.get("amount", ""),
                        recipient_or_purpose=analysis.get("recipient_or_purpose", ""),
                        key_details=analysis.get("key_details", ""),
                    ))
                else:
                    new_results.append(FileResult(
                        filename=file.name,
                        extraction_success=True,
                        error=analysis.get("error", "Unknown analysis error"),
                        analysis_success=False,
                    ))
            except Exception as e:
                print(f"[Upload Error] {file.name}: {e}")
                new_results.append(FileResult(
                    filename=file.name,
                    extraction_success=False,
                    error=str(e),
                    analysis_success=False,
                ))

        self.results = self.results + new_results
        self.is_processing = False
        self.refresh_dashboard()

    def _save_library_index(self):
        data = [
            {"filename": i.filename, "category": i.category, "uploaded_at": i.uploaded_at}
            for i in self.library
        ]
        try:
            LIBRARY_INDEX.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Library Save Error] {e}")

    def load_library(self):
        if not LIBRARY_INDEX.exists():
            return
        try:
            data = json.loads(LIBRARY_INDEX.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Library Load Error] {e}")
            return
        with_latest = get_latest_per_category(data)
        self.library = [
            LibraryItem(
                filename=d["filename"],
                category=d["category"],
                uploaded_at=d["uploaded_at"],
                is_latest=d["is_latest"],
            )
            for d in with_latest
        ]

    async def handle_library_upload(self, files: list[rx.UploadFile]):
        if not files:
            return

        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        new_items = []
        for file in files:
            try:
                upload_data = await file.read()
                outfile = upload_dir / file.name
                with outfile.open("wb") as f:
                    f.write(upload_data)

                extraction = await asyncio.to_thread(extract_text_from_file, str(outfile))
                lib_text = extraction.get("text", "") if extraction.get("success") else ""
                category = guess_category(file.name)
                uploaded_at = datetime.now().isoformat()

                if lib_text:
                    await asyncio.to_thread(
                        rag_add_document, file.name, lib_text, doc_type=category, uploaded_at=uploaded_at
                    )
                    print(f"[RAG] indexed {file.name}: {len(lib_text)} chars, category={category}")
                else:
                    print(f"[RAG] Warning: No text extracted for {file.name}")

                new_items.append(LibraryItem(
                    filename=file.name,
                    category=category,
                    uploaded_at=uploaded_at,
                ))
            except Exception as e:
                print(f"[Library Upload Error] {file.name}: {e}")

        combined = self.library + new_items

        combined_as_dicts = [
            {"filename": i.filename, "category": i.category, "uploaded_at": i.uploaded_at}
            for i in combined
        ]
        with_latest = get_latest_per_category(combined_as_dicts)

        self.library = [
            LibraryItem(
                filename=d["filename"],
                category=d["category"],
                uploaded_at=d["uploaded_at"],
                is_latest=d["is_latest"],
            )
            for d in with_latest
        ]
        self._save_library_index()

    def remove_library_item(self, filename: str):
        rag_remove_document(filename)
        remaining = [item for item in self.library if item.filename != filename]

        remaining_as_dicts = [
            {"filename": i.filename, "category": i.category, "uploaded_at": i.uploaded_at}
            for i in remaining
        ]
        with_latest = get_latest_per_category(remaining_as_dicts)

        self.library = [
            LibraryItem(
                filename=d["filename"],
                category=d["category"],
                uploaded_at=d["uploaded_at"],
                is_latest=d["is_latest"],
            )
            for d in with_latest
        ]
        self._save_library_index()

    def check_required_documents(self, index: int):
        item = self.results[index]

        library_as_dicts = [
            {"filename": lib.filename, "category": lib.category, "uploaded_at": lib.uploaded_at}
            for lib in self.library
        ]

        matches = match_documents_rag(item.required_documents, library_as_dicts)

        self.results[index].document_matches = matches
        self.results = self.results
        self.refresh_dashboard()

    def generate_draft(self, index: int):
        item = self.results[index]

        analysis = {
            "task_type": item.task_type,
            "summary": item.summary,
            "deadline": item.deadline,
            "required_documents": item.required_documents,
            "recipient_or_purpose": item.recipient_or_purpose,
            "key_details": item.key_details,
        }

        result = generate_reply_draft(item.original_text, analysis)

        if result["success"]:
            self.results[index].draft_text = result["draft"]
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"
        else:
            self.results[index].draft_text = f"ERROR: {result['error']}"
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"

        self.results = self.results

    def generate_financial_form(self, index: int):
        item = self.results[index]

        analysis = {
            "task_type": item.task_type,
            "summary": item.summary,
            "deadline": item.deadline,
            "required_documents": item.required_documents,
            "amount": item.amount,
            "recipient_or_purpose": item.recipient_or_purpose,
            "key_details": item.key_details,
        }

        result = generate_financial_declaration(analysis)

        if result["success"]:
            self.results[index].draft_text = result["draft"]
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"
        else:
            self.results[index].draft_text = "Could not generate the financial declaration form."
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"

        self.results = self.results

    def generate_application_form_draft(self, index: int):
        item = self.results[index]

        latest_cv = None
        for lib_item in self.library:
            if lib_item.category == "CV/Resume" and lib_item.is_latest:
                latest_cv = lib_item
                break

        if latest_cv is None:
            self.results[index].draft_text = "No CV found in your library. Please add a CV first."
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"
            self.results = self.results
            return

        cv_path = rx.get_upload_dir() / latest_cv.filename
        cv_extraction = extract_text_from_file(str(cv_path))

        if not cv_extraction["success"]:
            self.results[index].draft_text = "Could not read your CV file to extract details."
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"
            self.results = self.results
            return

        cv_fields = parse_cv_fields(cv_extraction["text"])

        job_analysis = {
            "task_type": item.task_type,
            "summary": item.summary,
            "deadline": item.deadline,
            "required_documents": item.required_documents,
            "recipient_or_purpose": item.recipient_or_purpose,
        }

        result = generate_application_form(cv_fields, job_analysis)

        if result["success"]:
            self.results[index].draft_text = result["draft"]
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"
        else:
            self.results[index].draft_text = "Could not generate the application form."
            self.results[index].draft_generated = True
            self.results[index].draft_status = "pending"

        self.results = self.results

    def toggle_edit(self, index: int):
        self.results[index].is_editing = not self.results[index].is_editing
        self.results = self.results

    def update_draft_text(self, index: int, value: str):
        self.results[index].draft_text = value
        self.results = self.results

    def approve_draft(self, index: int):
        item = self.results[index]
        output_path = f"{item.filename}_draft.pdf"

        pdf_result = save_draft_as_pdf(item.draft_text, output_path)

        if pdf_result["success"]:
            self.results[index].draft_status = "approved"
            self.audit_log = [AuditLogEntry(**create_log_entry(item.filename, "Approved", item.task_type))] + self.audit_log
        else:
            self.results[index].draft_status = "pending"

        self.results[index].is_editing = False
        self.results = self.results

    def reject_draft(self, index: int):
        item = self.results[index]
        self.results[index].draft_status = "rejected"
        self.results[index].is_editing = False
        self.results = self.results
        self.audit_log = [AuditLogEntry(**create_log_entry(item.filename, "Rejected", item.task_type))] + self.audit_log

    def mark_as_executed(self, index: int):
        item = self.results[index]
        self.results[index].draft_status = "executed"
        self.results = self.results
        self.audit_log = [AuditLogEntry(**create_log_entry(item.filename, "Executed", item.task_type))] + self.audit_log

    def simulate_send_email(self, index: int):
        item = self.results[index]
        self.results[index].draft_status = "executed"
        self.results = self.results
        self.audit_log = [AuditLogEntry(**create_log_entry(
            item.filename, "Email Sent (Simulated)", item.task_type
        ))] + self.audit_log

    def simulate_process_payment(self, index: int):
        item = self.results[index]
        self.results[index].draft_status = "executed"
        self.results = self.results
        self.audit_log = [AuditLogEntry(**create_log_entry(
            item.filename, "Payment Processed (Simulated)", item.task_type
        ))] + self.audit_log

    def update_chat_input(self, index: int, value: str):
        self.results[index].chat_input = value
        self.results = self.results

    def ask_question(self, index: int):
        item = self.results[index]
        question = item.chat_input.strip()

        if not question:
            return

        result = answer_question(item.original_text, question, item.chat_history)

        if result["success"]:
            answer = result["answer"]
        else:
            error_text = result["error"]
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                answer = "I've hit my usage limit for now. Please wait a minute and try asking again."
            else:
                answer = "Sorry, I couldn't answer that question right now. Please try again."

        self.results[index].chat_history.append({"question": question, "answer": answer})
        self.results[index].chat_input = ""
        self.results = self.results

    def ask_quick_question(self, index: int, question: str):
        item = self.results[index]

        result = answer_question(item.original_text, question, item.chat_history)

        if result["success"]:
            answer = result["answer"]
        else:
            error_text = result["error"]
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                answer = "I've hit my usage limit for now. Please wait a minute and try asking again."
            else:
                answer = "Sorry, I couldn't answer that question right now. Please try again."

        self.results[index].chat_history.append({"question": question, "answer": answer})
        self.results = self.results

    def start_recording_ui(self, index: int):
        self.recording_index = index

    def cancel_recording_ui(self):
        self.recording_index = -1

    def handle_voice_note(self, b64_audio: str):
        import base64
        import uuid

        index = self.recording_index
        self.recording_index = -1
        if index < 0 or not b64_audio:
            return

        wav_bytes = base64.b64decode(b64_audio)
        filename = f"voice_{uuid.uuid4().hex[:10]}.wav"
        outfile = rx.get_upload_dir() / filename
        with outfile.open("wb") as f:
            f.write(wav_bytes)
        from reflex.config import get_config
        audio_url = f"{get_config().api_url}/_upload/{filename}"
        print("[VOICE] audio_url:", audio_url)
        secs = max(1, round((len(wav_bytes) - 44) / 32000))

        item = self.results[index]
        history_before = list(item.chat_history)
        self.results[index].chat_history.append(
            {"question": "", "answer": "Listening to your voice note...", "audio_url": audio_url, "secs": secs}
        )
        self.results = self.results
        yield

        result = answer_voice_question(item.original_text, wav_bytes, history_before)

        if result["success"]:
            answer = result["answer"]
        else:
            error_text = result["error"]
            print("[VOICE ERROR]", error_text)
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                answer = "I've hit my usage limit for now. Please wait a minute and try again."
            else:
                answer = "Sorry, I couldn't understand that voice note. Please try again."

        self.results[index].chat_history[-1]["answer"] = answer
        self.results = self.results

    @rx.var
    def cv_question_text(self) -> str:
        if 0 <= self.cv_step < len(CV_QUESTIONS):
            return CV_QUESTIONS[self.cv_step]["prompt"]
        return ""

    @rx.var
    def cv_progress_text(self) -> str:
        return f"Question {self.cv_step + 1} of {len(CV_QUESTIONS)}"

    def start_cv_builder(self):
        self.cv_answers = {}
        self.cv_input = ""
        self.cv_message = ""
        self.cv_notice = ""
        self.cv_pdf_name = ""
        self.cv_pdf_url = ""
        self.cv_data = {}
        self.cv_step = 0

    def close_cv_builder(self):
        self.cv_step = -1
        self.cv_message = ""

    def update_cv_input(self, value: str):
        self.cv_input = value

    def submit_cv_answer(self, skip: bool):
        if self.cv_step < 0 or self.cv_step >= len(CV_QUESTIONS):
            return
        key = CV_QUESTIONS[self.cv_step]["key"]
        answer = "skip" if skip else self.cv_input.strip()
        if not answer:
            self.cv_message = "Please type an answer, or press Skip."
            return
        self.cv_answers[key] = answer
        self.cv_input = ""
        self.cv_message = ""
        self.cv_step += 1
        if self.cv_step >= len(CV_QUESTIONS):
            self.cv_message = "Writing your CV..."
            return State.generate_cv

    def generate_cv(self):
        self.cv_message = "Writing your CV..."
        yield

        result = structure_cv(dict(self.cv_answers))
        if not result["success"]:
            error_text = result["error"]
            print("[CV ERROR]", error_text)
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                self.cv_message = "I've hit my usage limit for now. Please wait a minute and press Try again."
            else:
                self.cv_message = "Sorry, I couldn't write the CV right now. Please press Try again."
            return

        cv = result["cv"]
        filename = f"CV_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        outfile = rx.get_upload_dir() / filename
        pdf = build_cv_pdf(cv, str(outfile))
        if not pdf["success"]:
            print("[CV PDF ERROR]", pdf["error"])
            self.cv_message = "Sorry, I couldn't create the PDF. Please press Try again."
            return

        self.cv_data = cv
        self.cv_pdf_name = filename
        self.cv_pdf_url = f"{get_config().api_url}/_upload/{filename}"
        self.cv_message = ""

    def approve_cv(self):
        if not self.cv_pdf_name:
            return
        filename = self.cv_pdf_name
        uploaded_at = datetime.now().isoformat()
        rag_add_document(filename, cv_to_text(self.cv_data), doc_type="CV/Resume", uploaded_at=uploaded_at)

        combined = self.library + [
            LibraryItem(filename=filename, category="CV/Resume", uploaded_at=uploaded_at)
        ]
        combined_as_dicts = [
            {"filename": i.filename, "category": i.category, "uploaded_at": i.uploaded_at}
            for i in combined
        ]
        with_latest = get_latest_per_category(combined_as_dicts)
        self.library = [
            LibraryItem(
                filename=d["filename"],
                category=d["category"],
                uploaded_at=d["uploaded_at"],
                is_latest=d["is_latest"],
            )
            for d in with_latest
        ]

        for i, r in enumerate(self.results):
            if r.required_documents and r.document_matches:
                self.check_required_documents(i)

        self.cv_step = -1
        self.cv_message = ""
        self.cv_notice = f"{filename} was added to your library."

    def build_assistant_context(self) -> str:
        lines = [f"TODAY: {datetime.now().strftime('%Y-%m-%d')}", "TASKS:"]
        if not self.dashboard_rows:
            lines.append("(no documents uploaded yet)")
        else:
            for row in self.dashboard_rows:
                missing = ", ".join(row.missing) if row.missing else "none"
                lines.append(
                    f"- {row.filename} | type: {row.task_type} | deadline: {row.deadline} | "
                    f"status: {row.completion_text} | missing: {missing}"
                )
        lines.append("LIBRARY:")
        if not self.library:
            lines.append("(empty)")
        else:
            for item in self.library:
                tag = " (latest)" if item.is_latest else ""
                lines.append(f"- {item.filename} ({item.category}){tag}")
        return "\n".join(lines)

    def _run_assistant_action(self, action: str, filename: str):
        if action == "start_cv_builder":
            self.start_cv_builder()
            return
        if action in ("check_documents", "generate_draft"):
            for i, r in enumerate(self.results):
                if r.filename == filename:
                    if action == "check_documents":
                        self.check_required_documents(i)
                    else:
                        self.generate_draft(i)
                    return

    def update_assistant_input(self, value: str):
        self.assistant_input = value

    def send_assistant_message(self):
        text = self.assistant_input.strip()
        if not text:
            return

        self.assistant_history.append({"role": "user", "text": text})
        self.assistant_input = ""
        self.assistant_typing = True
        yield

        context = self.build_assistant_context()
        filenames = [r.filename for r in self.results]
        result = assistant_reply(text, context, self.assistant_history[:-1], filenames)

        self.assistant_typing = False
        if result["success"]:
            self.assistant_history.append({"role": "assistant", "text": result["reply"]})
            self._run_assistant_action(result["action"], result["filename"])
        else:
            error_text = result["error"]
            print("[ASSISTANT ERROR]", error_text)
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                msg = "I've hit my usage limit for now. Please wait a minute and try again."
            else:
                msg = "Sorry, something went wrong. Please try again."
            self.assistant_history.append({"role": "assistant", "text": msg})

    def start_assistant_recording(self):
        self.assistant_recording = True

    def cancel_assistant_recording(self):
        self.assistant_recording = False

    def handle_assistant_voice_note(self, b64_audio: str):
        import base64
        import uuid

        self.assistant_recording = False
        if not b64_audio:
            return

        wav_bytes = base64.b64decode(b64_audio)
        filename = f"voice_{uuid.uuid4().hex[:10]}.wav"
        outfile = rx.get_upload_dir() / filename
        with outfile.open("wb") as f:
            f.write(wav_bytes)
        audio_url = f"{get_config().api_url}/_upload/{filename}"
        secs = max(1, round((len(wav_bytes) - 44) / 32000))

        self.assistant_history.append({"role": "user", "text": "", "audio_url": audio_url, "secs": secs})
        self.assistant_typing = True
        yield

        context = self.build_assistant_context()
        filenames = [r.filename for r in self.results]
        result = assistant_reply("", context, self.assistant_history[:-1], filenames, audio_bytes=wav_bytes)

        self.assistant_typing = False
        if result["success"]:
            self.assistant_history.append({"role": "assistant", "text": result["reply"]})
            self._run_assistant_action(result["action"], result["filename"])
        else:
            error_text = result["error"]
            print("[ASSISTANT ERROR]", error_text)
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                msg = "I've hit my usage limit for now. Please wait a minute and try again."
            else:
                msg = "Sorry, I couldn't understand that voice note. Please try again."
            self.assistant_history.append({"role": "assistant", "text": msg})

    def update_multi_chat_input(self, value: str):
        self.multi_chat_input = value

    def ask_multi_question(self):
        question = self.multi_chat_input.strip()
        if not question:
            return

        documents = [
            {"filename": r.filename, "text": r.original_text}
            for r in self.results
            if r.extraction_success and r.analysis_success
        ]

        if not documents:
            return

        result = answer_question_multi(documents, question, self.multi_chat_history)

        if result["success"]:
            answer = result["answer"]
        else:
            error_text = result["error"]
            if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                answer = "I've hit my usage limit for now. Please wait a minute and try asking again."
            else:
                answer = "Sorry, I couldn't answer that question right now. Please try again."

        self.multi_chat_history.append({"question": question, "answer": answer})
        self.multi_chat_input = ""


def draft_section(item: FileResult, index: int) -> rx.Component:
    return rx.vstack(
        rx.divider(),

        rx.cond(
            item.draft_generated,
            rx.vstack(
                rx.cond(
                    item.is_editing,
                    rx.text_area(
                        value=item.draft_text,
                        on_change=lambda value: State.update_draft_text(index, value),
                        width="100%",
                        rows="8",
                    ),
                    rx.box(
                        rx.text(item.draft_text, white_space="pre-wrap"),
                        padding="1em",
                        border="1px solid #ddd",
                        border_radius="8px",
                        width="100%",
                    ),
                ),

                rx.cond(
                    item.draft_status == "executed",
                    rx.callout("Task completed and executed.", icon="check_check", color_scheme="green"),
                    rx.cond(
                        item.draft_status == "approved",
                        rx.vstack(
                            rx.callout("Draft approved and saved as PDF.", icon="check", color_scheme="green"),
                            rx.cond(
                                (item.task_type == "fee_payment") | (item.task_type == "financial_declaration"),
                                rx.vstack(
                                    rx.button(
                                        "Simulate Process Payment",
                                        on_click=lambda: State.simulate_process_payment(index),
                                        color_scheme="purple",
                                    ),
                                    rx.text(
                                        "In the full version, this would connect to a real payment gateway.",
                                        size="1",
                                        color="gray",
                                    ),
                                    spacing="1",
                                    align="start",
                                ),
                                rx.cond(
                                    item.task_type == "email_reply",
                                    rx.vstack(
                                        rx.button(
                                            "Simulate Send Email",
                                            on_click=lambda: State.simulate_send_email(index),
                                            color_scheme="purple",
                                        ),
                                        rx.text(
                                            "In the full version, this would send the email via Gmail/SMTP integration.",
                                            size="1",
                                            color="gray",
                                        ),
                                        spacing="1",
                                        align="start",
                                    ),
                                    rx.button(
                                        "Mark as Executed",
                                        on_click=lambda: State.mark_as_executed(index),
                                        color_scheme="purple",
                                    ),
                                ),
                            ),
                            spacing="2",
                            align="start",
                            width="100%",
                        ),
                        rx.cond(
                            item.draft_status == "rejected",
                            rx.callout("Draft rejected.", icon="x", color_scheme="red"),
                            rx.cond(
                                item.draft_text.startswith("No CV found"),
                                rx.vstack(
                                    rx.text(
                                        "Add a CV to your library first, then try again.",
                                        size="1",
                                        color="gray",
                                    ),
                                    rx.button(
                                        "Try again",
                                        on_click=lambda: State.reset_draft(index),
                                        size="1",
                                        variant="soft",
                                    ),
                                    spacing="2",
                                    align="start",
                                ),
                                rx.hstack(
                                    rx.button("Approve", on_click=lambda: State.approve_draft(index), color_scheme="green"),
                                    rx.button(
                                        rx.cond(item.is_editing, "Done Editing", "Edit"),
                                        on_click=lambda: State.toggle_edit(index),
                                        color_scheme="blue",
                                    ),
                                    rx.button("Reject", on_click=lambda: State.reject_draft(index), color_scheme="red"),
                                    spacing="3",
                                ),
                            ),
                        ),
                    ),
                ),
                width="100%",
                align="start",
                spacing="3",
            ),
            rx.hstack(
                rx.button(
                    "Generate Draft",
                    on_click=lambda: State.generate_draft(index),
                ),
                rx.button(
                    "Generate Financial Form",
                    on_click=lambda: State.generate_financial_form(index),
                    color_scheme="purple",
                ),
                rx.button(
                    "Fill Application Form",
                    on_click=lambda: State.generate_application_form_draft(index),
                    color_scheme="orange",
                ),
                spacing="3",
            ),
        ),
        width="100%",
        align="start",
    )


VOICE_START_JS = """
(async function () {
  try {
    if (window.__voice) {
      clearInterval(window.__voice.timer);
      window.__voice.stream.getTracks().forEach(function (t) { t.stop(); });
      window.__voice = null;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    const v = { stream: stream, rec: rec, chunks: [], start: Date.now(), timer: null };
    window.__voice = v;
    rec.ondataavailable = function (e) {
      if (e.data && e.data.size > 0) { v.chunks.push(e.data); }
    };
    rec.start();
    v.timer = setInterval(function () {
      const secs = Math.floor((Date.now() - v.start) / 1000);
      const el = document.getElementById('rec-timer');
      if (el) {
        el.textContent = Math.floor(secs / 60) + ':' + String(secs % 60).padStart(2, '0');
      }
      if (secs >= 20 && rec.state === 'recording') { rec.stop(); }
    }, 250);
  } catch (err) {
    alert('Microphone access was blocked or is not available.');
  }
})()
"""

VOICE_CANCEL_JS = """
(function () {
  const v = window.__voice;
  if (!v) { return; }
  clearInterval(v.timer);
  try {
    v.rec.onstop = null;
    if (v.rec.state === 'recording') { v.rec.stop(); }
  } catch (e) {}
  v.stream.getTracks().forEach(function (t) { t.stop(); });
  window.__voice = null;
})()
"""

VOICE_SEND_JS = """
new Promise(function (resolve) {
  const v = window.__voice;
  if (!v) { resolve(''); return; }
  clearInterval(v.timer);

  function finish() {
    v.stream.getTracks().forEach(function (t) { t.stop(); });
    window.__voice = null;
    const blob = new Blob(v.chunks, { type: v.rec.mimeType || 'audio/webm' });
    blob.arrayBuffer().then(function (buf) {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      return ctx.decodeAudioData(buf).then(function (decoded) {
        ctx.close();
        const rate = 16000;
        const length = Math.max(1, Math.ceil(decoded.duration * rate));
        const off = new OfflineAudioContext(1, length, rate);
        const src = off.createBufferSource();
        src.buffer = decoded;
        src.connect(off.destination);
        src.start(0);
        return off.startRendering();
      });
    }).then(function (rendered) {
      const samples = rendered.getChannelData(0);
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);
      function str(o, s) { for (let i = 0; i < s.length; i++) { view.setUint8(o + i, s.charCodeAt(i)); } }
      str(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE');
      str(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
      view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
      str(36, 'data'); view.setUint32(40, samples.length * 2, true);
      let pos = 44;
      for (let i = 0; i < samples.length; i++, pos += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(pos, s < 0 ? s * 32768 : s * 32767, true);
      }
      const bytes = new Uint8Array(buffer);
      let binary = '';
      for (let i = 0; i < bytes.length; i += 32768) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
      }
      resolve(btoa(binary));
    }).catch(function () { resolve(''); });
  }

  if (v.rec.state === 'recording') {
    v.rec.onstop = finish;
    v.rec.stop();
  } else {
    finish();
  }
})
"""


def chat_bubble(turn: dict) -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.cond(
                turn["audio_url"],
                rx.el.audio(src=turn["audio_url"], controls=True),
                rx.text(turn["question"]),
            ),
            padding="0.75em",
            border_radius="8px",
            background="#DCF0FF",
            align_self="flex-end",
            max_width="85%",
        ),
        rx.box(
            rx.text(turn["answer"]),
            padding="0.75em",
            border_radius="8px",
            background="#F0F0F0",
            align_self="flex-start",
            max_width="85%",
        ),
        width="100%",
        spacing="2",
        margin_bottom="0.75em",
    )

def chat_section(item: FileResult, index: int) -> rx.Component:
    return rx.vstack(
        rx.divider(),
        rx.text("Ask a question about this document:", weight="bold"),

        rx.hstack(
            rx.button(
                "Deadline?",
                on_click=lambda: State.ask_quick_question(index, "What is the deadline?"),
                size="1",
                variant="soft",
            ),
            rx.button(
                "What's missing?",
                on_click=lambda: State.ask_quick_question(index, "What is missing or still needed to complete this?"),
                size="1",
                variant="soft",
            ),
            rx.button(
                "Summarize",
                on_click=lambda: State.ask_quick_question(index, "Summarize this document in 2 sentences."),
                size="1",
                variant="soft",
            ),
            spacing="2",
        ),

        rx.foreach(
            item.chat_history,
            chat_bubble,
        ),

        rx.hstack(
            rx.input(
                id=f"chat-input-{index}",
                value=item.chat_input,
                on_change=lambda value: State.update_chat_input(index, value),
                placeholder="e.g. What is the deadline?",
                width="100%",
            ),
            rx.cond(
                State.recording_index == index,
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="50%", background="red"),
                    rx.text("0:00", id="rec-timer", width="3em"),
                    rx.button(
                        rx.icon("x"),
                        on_click=[State.cancel_recording_ui, rx.call_script(VOICE_CANCEL_JS)],
                        color_scheme="gray",
                        variant="soft",
                    ),
                    rx.button(
                    rx.icon("check"),
                        on_click=rx.call_script(VOICE_SEND_JS, callback=State.handle_voice_note),
                        color_scheme="green",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.button(
                    rx.icon("mic"),
                    on_click=[State.start_recording_ui(index), rx.call_script(VOICE_START_JS)],
                ),
            ),
            rx.button("Send", on_click=lambda: State.ask_question(index)),
            width="100%",
            spacing="2",
        ),

        width="100%",
        align="start",
        spacing="2",
    )

def match_badge(match: dict) -> rx.Component:
    return rx.hstack(
        rx.cond(
            match["status"] == "matched",
            rx.icon("check", color="green"),
            rx.icon("x", color="red"),
        ),
        rx.text(match["document"], weight="medium"),
        rx.spacer(),
        rx.cond(
            match["status"] == "matched",
            rx.text(f"Found: {match['matched_file']} ({match['confidence']}% match)", size="2", color="gray"),
            rx.text("Missing — not in your library", size="2", color="red"),
        ),
        width="100%",
        padding="0.5em",
        border="1px solid #eee",
        border_radius="6px",
    )


def requirements_section(item: FileResult, index: int) -> rx.Component:
    return rx.vstack(
        rx.divider(),
        rx.cond(
            item.required_documents.length() > 0,
            rx.vstack(
                rx.button(
                    "Check My Documents",
                    on_click=lambda: State.check_required_documents(index),
                    size="2",
                ),
                rx.cond(
                    item.document_matches.length() > 0,
                    rx.vstack(
                        rx.foreach(item.document_matches, match_badge),
                        width="100%",
                        spacing="2",
                    ),
                ),
                width="100%",
                align="start",
                spacing="2",
            ),
        ),
        width="100%",
        align="start",
    )


def multi_chat_section() -> rx.Component:
    return rx.vstack(
        rx.divider(),
        rx.heading("Ask about all uploaded documents together", size="4"),

        rx.foreach(
            State.multi_chat_history,
            chat_bubble,
        ),

        rx.hstack(
            rx.input(
                value=State.multi_chat_input,
                on_change=State.update_multi_chat_input,
                placeholder="e.g. Does my CV match this job posting?",
                width="100%",
            ),
            rx.button("Send", on_click=State.ask_multi_question),
            width="100%",
            spacing="2",
        ),

        width="100%",
        align="start",
        spacing="2",
        padding="1.5em",
        border="1px solid #ddd",
        border_radius="10px",
        margin_top="1em",
    )

def library_item_row(lib_item) -> rx.Component:
    return rx.hstack(
        rx.badge(lib_item.category, color_scheme="gray", variant="soft"),
        rx.text(lib_item.filename, color=INK),
        rx.cond(
            lib_item.is_latest,
            rx.badge("Latest", color_scheme="green", size="1"),
            rx.badge("Older version", color_scheme="gray", size="1"),
        ),
        rx.spacer(),
        rx.button(
            "Remove",
            on_click=lambda: State.remove_library_item(lib_item.filename),
            size="1",
            variant="ghost",
            color=DANGER,
        ),
        width="100%",
        padding="0.6em 0.75em",
        background=CREAM,
        border_radius="8px",
    )

def cv_builder_section() -> rx.Component:
    question_panel = rx.vstack(
        rx.text(State.cv_progress_text, size="2", color="gray"),
        rx.text(State.cv_question_text, weight="bold"),
        rx.text_area(
            value=State.cv_input,
            on_change=State.update_cv_input,
            placeholder="Type your answer here...",
            width="100%",
            rows="4",
        ),
        rx.cond(State.cv_message != "", rx.text(State.cv_message, color="red", size="2")),
        rx.hstack(
            rx.button("Next", on_click=State.submit_cv_answer(False)),
            rx.cond(
                State.cv_step >= 2,
                rx.button("Skip", on_click=State.submit_cv_answer(True), variant="soft", color_scheme="gray"),
            ),
            rx.button("Cancel", on_click=State.close_cv_builder, variant="ghost", color_scheme="red"),
            spacing="2",
        ),
        spacing="2",
        width="100%",
        align="start",
    )

    preview_panel = rx.vstack(
        rx.text("Your CV is ready. Please review it, then approve.", weight="bold"),
        rx.el.iframe(src=State.cv_pdf_url, width="100%", height="520px"),
        rx.hstack(
            rx.button("Approve & Save to Library", on_click=State.approve_cv, color_scheme="green"),
            rx.link("Open in new tab", href=State.cv_pdf_url, is_external=True),
            rx.button("Start over", on_click=State.start_cv_builder, variant="soft", color_scheme="gray"),
            rx.button("Discard", on_click=State.close_cv_builder, variant="ghost", color_scheme="red"),
            spacing="3",
            align="center",
        ),
        spacing="2",
        width="100%",
        align="start",
    )

    working_panel = rx.vstack(
        rx.text(State.cv_message),
        rx.cond(
            State.cv_message == "Writing your CV...",
            rx.spinner(),
            rx.hstack(
                rx.button("Try again", on_click=State.generate_cv),
                rx.button("Cancel", on_click=State.close_cv_builder, variant="ghost", color_scheme="red"),
                spacing="2",
            ),
        ),
        spacing="2",
        width="100%",
        align="start",
    )

    return rx.vstack(
        rx.cond(
            State.cv_step < 0,
            rx.vstack(
                rx.button(
                    "Create my CV with AI",
                    on_click=State.start_cv_builder,
                    color_scheme="green",
                    variant="soft",
                ),
                rx.cond(
                    State.cv_notice != "",
                    rx.callout(State.cv_notice, icon="check", color_scheme="green"),
                ),
                align="start",
                spacing="2",
                width="100%",
            ),
            rx.box(
                rx.cond(
                    State.cv_step < len(CV_QUESTIONS),
                    question_panel,
                    rx.cond(State.cv_pdf_url != "", preview_panel, working_panel),
                ),
                padding="1em",
                border="1px solid #E5E7EB",
                border_radius="8px",
                width="100%",
            ),
        ),
        width="100%",
        align="start",
    )

def assistant_bubble(turn: dict) -> rx.Component:
    return rx.cond(
        turn["role"] == "user",
        rx.box(
            rx.cond(
                turn["audio_url"],
                rx.el.audio(src=turn["audio_url"], controls=True),
                rx.text(turn["text"]),
            ),
            padding="0.6em 0.9em",
            border_radius="10px",
            background="#DCF0FF",
            align_self="flex-end",
            max_width="80%",
        ),
        rx.box(
            rx.text(turn["text"]),
            padding="0.6em 0.9em",
            border_radius="10px",
            background="#F0F0F0",
            align_self="flex-start",
            max_width="80%",
        ),
    )


def assistant_section() -> rx.Component:
    return rx.vstack(
        rx.heading("Assistant", size="5", font_family=FONT_SERIF, color=INK),
        rx.text(
            "Ask about your tasks, or tell it what to do next.",
            size="2",
            color=MUTED,
        ),
        rx.hstack(
            rx.button(
                "check documents for the scholarship",
                on_click=lambda: State.update_assistant_input("check documents for the scholarship"),
                size="1",
                variant="surface",
                border_radius="16px",
            ),
            rx.button(
                "create my CV",
                on_click=lambda: State.update_assistant_input("create my CV"),
                size="1",
                variant="surface",
                border_radius="16px",
            ),
            rx.button(
                "what's missing?",
                on_click=lambda: State.update_assistant_input("what's missing?"),
                size="1",
                variant="surface",
                border_radius="16px",
            ),
            spacing="2",
            wrap="wrap",
        ),
        rx.box(
            rx.vstack(
                rx.foreach(State.assistant_history, assistant_bubble),
                rx.cond(
                    State.assistant_typing,
                    rx.hstack(
                        rx.spinner(size="1"),
                        rx.text("Thinking...", size="2", color=MUTED),
                        spacing="2",
                    ),
                ),
                spacing="2",
                width="100%",
                align="start",
            ),
            width="100%",
            max_height="360px",
            overflow_y="auto",
            padding="0.5em",
        ),
        rx.hstack(
            rx.input(
                id="assistant-input",
                value=State.assistant_input,
                on_change=State.update_assistant_input,
                placeholder="Ask anything",
                width="100%",
                background=CREAM,
                border=f"1px solid {BORDER}",
                on_key_down=lambda k: rx.cond(
                    k == "Enter", 
                    rx.call_script(
                        "document.getElementById('assistant-input').value",
                        callback=State.send_assistant_with_text,
                    ),
                    rx.console_log(""),
                ),
            ),
            rx.cond(
                State.assistant_recording,
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="50%", background="red"),
                    rx.text("0:00", id="assistant-rec-timer", width="3em"),
                    rx.button(
                        rx.icon("x"),
                        on_click=[State.cancel_assistant_recording, rx.call_script(VOICE_CANCEL_JS)],
                        color_scheme="gray",
                        variant="soft",
                    ),
                    rx.button(
                        rx.icon("check"),
                        on_click=rx.call_script(VOICE_SEND_JS, callback=State.handle_assistant_voice_note),
                        color_scheme="green",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.button(
                    rx.icon("mic"),
                    on_click=[State.start_assistant_recording, rx.call_script(VOICE_START_JS)],
                    variant="surface",
                ),
            ),
            rx.button(
                "Send",
                on_click=State.send_assistant_message,
                background=DARK_BTN,
                color="white",
                border_radius="6px",
            ),
            width="100%",
            spacing="2",
        ),
        width="100%",
        align="start",
        spacing="3",
        padding="1.5em",
        background="white",
        border=f"1px solid {BORDER}",
        border_radius="12px",
    )


def library_section() -> rx.Component:
    return rx.vstack(
        rx.heading("Your document library", size="5", font_family=FONT_SERIF, color=INK),
        rx.text(
            "Upload your CV, transcript, photo, or financial documents once — "
            "they'll be reused to check against every task's requirements.",
            size="2",
            color=MUTED,
        ),
 
        rx.upload(
            rx.vstack(
                rx.text("+ Add to library", weight="medium", color=INK),
                rx.text("or drop a file here", size="2", color=MUTED),
                spacing="1",
                align="center",
            ),
            id="library_upload",
            multiple=True,
            border=f"1.5px dashed {BORDER}",
            padding="1.5em",
            border_radius="10px",
            background="white",
        ),
 
        rx.button(
            "Save to library",
            on_click=State.handle_library_upload(rx.upload_files(upload_id="library_upload")),
            background=DARK_BTN,
            color="white",
            border_radius="6px",
        ),
 
        rx.foreach(State.library, library_item_row),
 
        width="100%",
        align="start",
        spacing="3",
        padding="1.5em",
        background="white",
        border=f"1px solid {BORDER}",
        border_radius="12px",
        margin_bottom="1em",
    )

def dashboard_row(row) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(row.filename, weight="medium", color=INK),
                rx.text(f"{row.task_type} · {row.completion_text}", size="2", color=MUTED),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.text(
                    row.urgency_label,
                    size="2",
                    weight="medium",
                    color=rx.cond(
                        (row.urgency_label == "Overdue") | (row.urgency_label == "Due today"),
                        DANGER,
                        "#946200",
                    ),
                ),
                rx.text(row.deadline, size="1", color=MUTED),
                align="end",
                spacing="1",
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            row.missing.length() > 0,
            rx.hstack(
                rx.text("Missing:", size="1", color=MUTED),
                rx.foreach(
                    row.missing,
                    lambda m: rx.badge(m, color_scheme="red", variant="soft", size="1"),
                ),
                spacing="2",
                wrap="wrap",
                margin_top="0.5em",
            ),
        ),
        width="100%",
        padding="1em 0",
        border_bottom=f"1px solid {BORDER}",
    )


def dashboard_section() -> rx.Component:
    return rx.cond(
        State.dashboard_rows.length() > 0,
        rx.vstack(
            rx.heading("Your tasks", size="5", font_family=FONT_SERIF, color=INK),
            rx.text(
                "All detected tasks, sorted by deadline urgency.",
                size="2",
                color=MUTED,
            ),
            rx.vstack(
                rx.foreach(State.dashboard_rows, dashboard_row),
                width="100%",
                spacing="0",
            ),
            width="100%",
            align="start",
            spacing="3",
            padding="1.5em",
            background="white",
            border=f"1px solid {BORDER}",
            border_radius="12px",
            margin_bottom="1em",
        ),
    )

def command_bar_section() -> rx.Component:
    return rx.cond(
        State.results.length() > 0,
        rx.vstack(
            rx.heading("Quick Command", size="5"),
            rx.text(
                'Try: "generate a draft for the scholarship one" or "check documents for the govt form"',
                size="2",
                color="gray",
            ),
            rx.hstack(
                rx.input(
                    value=State.command_input,
                    on_change=State.update_command_input,
                    placeholder="e.g. generate the draft for the fee invoice",
                    width="100%",
                ),
                rx.button("Run", on_click=State.run_command),
                width="100%",
                spacing="2",
            ),
            rx.cond(
                State.command_result_message != "",
                rx.callout(State.command_result_message, icon="check", color_scheme="blue"),
            ),
            width="100%",
            align="start",
            spacing="3",
            padding="1.5em",
            border="1px solid #ddd",
            border_radius="10px",
            margin_bottom="1em",
        ),
    )

def audit_log_row(entry: AuditLogEntry) -> rx.Component:
    return rx.hstack(
        rx.badge(
            entry.action,
            color_scheme=rx.cond(entry.action == "Approved", "green", "red"),
            size="1",
        ),
        rx.text(entry.filename, weight="medium"),
        rx.spacer(),
        rx.text(entry.timestamp, size="2", color="gray"),
        width="100%",
        padding="0.5em",
        border_bottom="1px solid #eee",
    )


def audit_log_section() -> rx.Component:
    return rx.cond(
        State.audit_log.length() > 0,
        rx.vstack(
            rx.heading("Activity Log", size="5"),
            rx.text(
                "A record of every draft you've approved or rejected.",
                size="2",
                color="gray",
            ),
            rx.foreach(State.audit_log, audit_log_row),
            width="100%",
            align="start",
            spacing="3",
            padding="1.5em",
            border="1px solid #ddd",
            border_radius="10px",
            margin_bottom="1em",
        ),
    )

def result_card(item, index: int) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(item.filename, size="1", color=MUTED),
                rx.heading(item.summary, size="5", font_family=FONT_SERIF, color=INK),
                rx.badge(item.task_type, color_scheme="gray", variant="soft"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.badge(
                "deadline tracked",
                color_scheme="amber",
                variant="soft",
                border_radius="16px",
            ),
            width="100%",
            align="start",
        ),
 
        rx.cond(
            item.extraction_success & item.analysis_success,
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.text("deadline", size="1", color=MUTED),
                        rx.text(item.deadline, weight="medium", color=INK),
                        align="start",
                        spacing="0",
                    ),
                    rx.vstack(
                        rx.text("amount", size="1", color=MUTED),
                        rx.text(item.amount, weight="medium", color=INK),
                        align="start",
                        spacing="0",
                    ),
                    spacing="6",
                ),
                rx.vstack(
                    rx.text("eligible for", size="1", color=MUTED),
                    rx.text(item.recipient_or_purpose, color=INK),
                    align="start",
                    spacing="0",
                ),
                rx.hstack(
                    rx.foreach(
                        item.required_documents,
                        lambda doc: rx.badge(doc, color_scheme="gray", variant="surface"),
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.text(item.key_details, size="2", color=MUTED),
 
                draft_section(item, index),
                requirements_section(item, index),
                chat_section(item, index),
 
                align="start",
                spacing="3",
                width="100%",
            ),
            rx.callout(
                item.error,
                icon="triangle_alert",
                color_scheme="red",
            ),
        ),
 
        width="100%",
        padding="1.5em",
        background="white",
        border=f"1px solid {BORDER}",
        border_radius="12px",
        margin_bottom="1em",
        id=f"doc-{item.filename}",
    )


def nav_tab(label: str, icon: str, target: str, active: bool = False) -> rx.Component:
    return rx.hstack(
        rx.icon(icon, size=16, color=INK if active else MUTED),
        rx.text(
            label,
            size="2",
            weight="medium" if active else "regular",
            color=INK if active else MUTED,
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="0.5em 0.75em",
        border_radius="6px",
        background=CREAM_DARK if active else "white",
        border=f"1px solid {CREAM_DARK if active else 'rgba(0,0,0,0.12)'}",
        box_shadow="0 1px 0 rgba(0,0,0,0.04)",
        cursor="pointer",
        _hover={"background": CREAM_DARK},
        transition="background 0.15s ease",
        on_click=rx.call_script(
            f"document.getElementById('{target}')"
            f"?.scrollIntoView({{behavior: 'smooth', block: 'start'}})"
        ),
    )


def sidebar() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("layout-dashboard", size=18, color=INK),
            rx.text("Docket", weight="bold", font_family=FONT_SERIF, size="4"),
            spacing="2",
            align="center",
            padding="0.25em",
        ),
        rx.vstack(
            nav_tab("Home", "layout-dashboard", "home", active=True),
            nav_tab("Assistant", "message-circle", "assistant"),
            nav_tab("Tasks", "list-checks", "tasks"),
            nav_tab("Library", "folder", "library"),
            spacing="2",
            align="start",
            width="100%",
        ),
        spacing="4",
        align="start",
        width="190px",
        min_width="190px",
        padding="1.25em",
        background=CREAM,
        height="100%",
    )


def index() -> rx.Component:
    return rx.box(
        rx.color_mode.button(position="top-right"),
        rx.hstack(
            sidebar(),
            rx.vstack(
                rx.box(
                    rx.vstack(
                        rx.heading(
                            "Every form, tracked. Every deadline, met.",
                            size="8",
                            font_family=FONT_SERIF,
                            color=INK,
                        ),
                        rx.text(
                            "Upload a document once. Docket reads it, pulls out "
                            "what's required, and checks it against what's already in your library.",
                            size="4",
                            color=MUTED,
                        ),
                        spacing="5",
                        align="start",
                    ),
                    id="home",
                    width="100%",
                ),

                rx.foreach(
                    State.results,
                    lambda item, i: result_card(item, i),
                ),

                rx.upload(
                    rx.vstack(
                        rx.text("Select files", weight="medium", color=INK),
                        rx.text("or drag and drop files here", size="2", color=MUTED),
                        spacing="1",
                        align="center",
                    ),
                    id="upload1",
                    multiple=True,
                    accept={
                        "application/pdf": [".pdf"],
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                        "image/png": [".png"],
                        "image/jpeg": [".jpg", ".jpeg"],
                        "message/rfc822": [".eml"],
                        "application/vnd.ms-outlook": [".msg"],
                    },
                    border=f"1.5px dashed {BORDER}",
                    padding="2.5em",
                    border_radius="12px",
                    background="white",
                ),

                rx.button(
                    "Upload & analyze",
                    on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
                    loading=State.is_processing,
                    background=DARK_BTN,
                    color="white",
                    border_radius="6px",
                ),

                rx.box(library_section(), id="library", width="100%"),
                rx.box(assistant_section(), id="assistant", width="100%"),
                cv_builder_section(),
                rx.box(dashboard_section(), id="tasks", width="100%"),
                command_bar_section(),

                rx.cond(
                    State.results.length() >= 2,
                    multi_chat_section(),
                ),

                audit_log_section(),

                spacing="5",
                align="start",
                width="100%",
                max_width="800px",
                padding="2.5em",
            ),
            spacing="0",
            align="start",
            width="100%",
        ),
        width="100%",
        min_height="100vh",
        background=CREAM,
    )

app = rx.App()
app.add_page(index, title="Docket", on_load=State.load_library)