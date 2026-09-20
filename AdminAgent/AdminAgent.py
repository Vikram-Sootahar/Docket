"""AdminAgent - File Upload & Text Extraction with AI Reasoning."""

import reflex as rx
from pydantic import BaseModel
from file_readers import extract_text_from_file
from ai_reasoning import analyze_text
from ai_preparation import generate_reply_draft, save_draft_as_pdf, generate_financial_declaration, generate_application_form
from ai_chat import answer_question, answer_question_multi
from matching import match_documents, match_documents_rag, guess_category, get_latest_per_category
from rag_store import add_document as rag_add_document, remove_document as rag_remove_document
from datetime import datetime
from dashboard import build_dashboard_rows
from audit import create_log_entry
from command_router import route_command
from cv_parser import parse_cv_fields


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
    is_processing: bool = False
    library: list[LibraryItem] = []
    dashboard_rows: list[DashboardRow] = []
    audit_log: list[AuditLogEntry] = []
    command_input: str = ""
    command_result_message: str = ""

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
        self.results = []

        new_results = []
        for file in files:
            upload_data = await file.read()

            outfile = rx.get_upload_dir() / file.name
            with outfile.open("wb") as f:
                f.write(upload_data)

            extraction = extract_text_from_file(str(outfile))

            if not extraction["success"]:
                new_results.append(FileResult(
                    filename=file.name,
                    extraction_success=False,
                    error=extraction["error"],
                    analysis_success=False,
                ))
                continue

            analysis = analyze_text(extraction["text"])

            if analysis["success"]:
                new_results.append(FileResult(
                    filename=file.name,
                    extraction_success=True,
                    analysis_success=True,
                    original_text=extraction["text"],
                    task_type=analysis["task_type"],
                    summary=analysis["summary"],
                    deadline=analysis["deadline"],
                    required_documents=analysis["required_documents"],
                    amount=analysis["amount"],
                    recipient_or_purpose=analysis["recipient_or_purpose"],
                    key_details=analysis["key_details"],
                ))
            else:
                new_results.append(FileResult(
                    filename=file.name,
                    extraction_success=True,
                    error=analysis["error"],
                    analysis_success=False,
                ))

        self.results = new_results
        self.is_processing = False
        self.refresh_dashboard()

    async def handle_library_upload(self, files: list[rx.UploadFile]):
        if not files:
            return

        new_items = []
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.name
            with outfile.open("wb") as f:
                f.write(upload_data)

            extraction = extract_text_from_file(str(outfile))
            lib_text = extraction.get("text", "") if extraction.get("success") else ""
            category = guess_category(file.name)
            uploaded_at = datetime.now().isoformat()
            rag_add_document(file.name, lib_text, doc_type=category, uploaded_at=uploaded_at)
            print(f"[RAG] indexed {file.name}: {len(lib_text)} chars, category={category}")

            new_items.append(LibraryItem(
                filename=file.name,
                category=category,
                uploaded_at=uploaded_at,
            ))

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


def chat_bubble(turn: dict) -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.text(turn["question"]),
            padding="0.75em",
            border_radius="8px",
            background="#DCF0FF",
            align_self="flex-end",
            max_width="85%",
        ),
        rx.hstack(
            rx.box(
                rx.text(turn["answer"]),
                padding="0.75em",
                border_radius="8px",
                background="#F0F0F0",
                max_width="85%",
            ),
            rx.button(
                "🔊",
                on_click=rx.call_script(
                    f"""
                    (function() {{
                        const text = {turn["answer"]};
                        window.speechSynthesis.cancel();
                        const utter = new SpeechSynthesisUtterance(text);
                        utter.lang = 'en-US';
                        window.speechSynthesis.speak(utter);
                    }})()
                    """
                ),
                size="1",
                variant="ghost",
            ),
            align_self="flex-start",
            spacing="1",
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
            rx.button(
                "🎤",
                on_click=rx.call_script(
                    f"""
                    (function() {{
                        const input = document.getElementById('chat-input-{index}');
                        if (!input) return;
                        const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
                        if (!Rec) {{
                            alert('Voice input not supported in this browser.');
                            return;
                        }}
                        const rec = new Rec();
                        rec.lang = 'en-US';
                        rec.onresult = function(e) {{
                            const text = e.results[0][0].transcript;
                            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeSetter.call(input, text);
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }};
                        rec.start();
                    }})()
                    """
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

def library_item_row(lib_item: LibraryItem) -> rx.Component:
    return rx.hstack(
        rx.badge(lib_item.category, color_scheme="purple"),
        rx.text(lib_item.filename),
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
            color_scheme="red",
        ),
        width="100%",
        padding="0.5em",
    )


def library_section() -> rx.Component:
    return rx.vstack(
        rx.heading("My Document Library", size="5"),
        rx.text(
            "Upload your CV, transcript, photo, or financial documents once — they'll be reused to check against every task's requirements.",
            size="2",
            color="gray",
        ),

        rx.upload(
            rx.vstack(
                rx.button("Add to Library", type="button"),
                rx.text("or drag and drop files here"),
            ),
            id="library_upload",
            multiple=True,
            border="2px dashed #ccc",
            padding="1.5em",
            border_radius="10px",
        ),

        rx.button(
            "Save to Library",
            on_click=State.handle_library_upload(rx.upload_files(upload_id="library_upload")),
        ),

        rx.foreach(State.library, library_item_row),

        width="100%",
        align="start",
        spacing="3",
        padding="1.5em",
        border="1px solid #ddd",
        border_radius="10px",
        margin_bottom="1em",
    )

def dashboard_row(row: DashboardRow) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(row.filename, weight="bold"),
                rx.badge(row.task_type, color_scheme="blue", size="1"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.text(row.deadline, size="2", color="gray"),
                rx.badge(
                    row.urgency_label,
                    color_scheme=rx.cond(
                        (row.urgency_label == "Overdue") | (row.urgency_label == "Due today"),
                        "red",
                        "orange",
                    ),
                    size="1",
                ),
                align="end",
                spacing="1",
            ),
            width="100%",
        ),
        rx.hstack(
            rx.text(row.completion_text, size="2", weight="medium"),
            rx.progress(value=row.completion_percent, width="60%"),
            width="100%",
            spacing="3",
            align="center",
        ),
        rx.cond(
            row.missing.length() > 0,
            rx.vstack(
                rx.text("Still missing:", size="2", weight="bold", color="red"),
                rx.foreach(
                    row.missing,
                    lambda m: rx.text(f"• {m}", size="2", color="red"),
                ),
                align="start",
                spacing="1",
                margin_top="0.5em",
            ),
        ),
        width="100%",
        padding="1em",
        border="1px solid #ddd",
        border_radius="8px",
        margin_bottom="0.75em",
        cursor="pointer",
        on_click=rx.call_script(
            f"""
            (function() {{
                const target = document.getElementById("doc-{row.filename}");
                if (target) {{
                    target.scrollIntoView({{ behavior: "smooth", block: "start" }});
                }}
            }})()
            """
        ),
        _hover={"background": "#f5f5f5"},
    )

def dashboard_section() -> rx.Component:
    return rx.cond(
        State.dashboard_rows.length() > 0,
        rx.vstack(
            rx.heading("Task Dashboard", size="5"),
            rx.text(
                "All detected tasks, sorted by deadline urgency.",
                size="2",
                color="gray",
            ),
            rx.foreach(State.dashboard_rows, dashboard_row),
            width="100%",
            align="start",
            spacing="3",
            padding="1.5em",
            border="1px solid #ddd",
            border_radius="10px",
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

def result_card(item: FileResult, index: int) -> rx.Component:
    return rx.box(
        rx.text(item.filename, weight="bold", size="4"),

        rx.cond(
            item.extraction_success & item.analysis_success,
            rx.vstack(
                rx.badge(item.task_type, color_scheme="blue"),
                rx.text(item.summary),
                rx.hstack(
                    rx.text("Deadline:", weight="bold"),
                    rx.text(item.deadline),
                ),
                rx.hstack(
                    rx.text("Amount:", weight="bold"),
                    rx.text(item.amount),
                ),
                rx.hstack(
                    rx.text("For:", weight="bold"),
                    rx.text(item.recipient_or_purpose),
                ),
                rx.text("Required documents:", weight="bold"),
                rx.foreach(
                    item.required_documents,
                    lambda doc: rx.text(f"• {doc}"),
                ),
                rx.text("Other details:", weight="bold"),
                rx.text(item.key_details),

                draft_section(item, index),
                requirements_section(item, index),
                chat_section(item, index),

                align="start",
                spacing="2",
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
        border="1px solid #ddd",
        border_radius="10px",
        margin_bottom="1em",
        id=f"doc-{item.filename}",
    )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("AdminAgent — Understand Your Documents", size="7"),
            rx.text(
                "Upload emails, PDFs, forms, or images. AI will extract and analyze what needs to be done.",
                size="4",
                color="gray",
            ),

            library_section(),
            dashboard_section(),
            command_bar_section(),

            rx.upload(
                rx.vstack(
                    rx.button("Select Files", type="button"),
                    rx.text("or drag and drop files here"),
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
                border="2px dashed #ccc",
                padding="3em",
                border_radius="10px",
            ),

            rx.button(
                "Upload & Analyze",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
                loading=State.is_processing,
            ),

            rx.foreach(
                State.results,
                lambda item, i: result_card(item, i),
            ),

            rx.cond(
                State.results.length() >= 2,
                multi_chat_section(),
            ),

            audit_log_section(),

            spacing="5",
            justify="center",
            align="center",
            min_height="85vh",
            padding="2em",
            width="100%",
            max_width="800px",
        ),
    )


app = rx.App()
app.add_page(index)