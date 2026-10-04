# 📋 Docket — Every Form, Tracked. Every Deadline, Met.

**Docket** is an AI agent that reads your administrative documents — scholarship notices, job postings, government forms, fee invoices, emails — and turns them into tracked, actionable tasks. It doesn't just *summarize* what you need to do; it checks what you already have, drafts the paperwork, and hands you a finished document to approve.

**Live app:** https://docket-gray-ocean.reflex.run

> Built solo, end-to-end: document ingestion, AI reasoning, a RAG-based personal document library, draft/form generation, and a human-in-the-loop approval workflow.

---

## Table of Contents

- [The Problem](#the-problem)
- [What Docket Does](#what-docket-does)
- [How It Works](#how-it-works)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Challenges I Faced (and How I Solved Them)](#challenges-i-faced-and-how-i-solved-them)
- [Known Limitations](#known-limitations)
- [What's Next](#whats-next)
- [Screenshots](#screenshots)
- [Demo](#demo)
- [About This Project](#about-this-project)

---

## The Problem

Most "administrative life admin" — scholarship applications, job postings, government renewals, fee payments — arrives as unstructured documents: a PDF, a scanned form, an email, a flyer photographed on a phone. Each one has a different deadline, a different set of required documents, and no shared memory of what you've already submitted elsewhere.

The result: missed deadlines, resubmitted documents you already had ready, and forms filled out from scratch every single time.

Docket is built to close that loop — not just *read* the document, but *act* on it.

## What Docket Does

- **Reads anything you throw at it** — PDF, DOCX, images (with OCR), `.eml` emails, and Outlook `.msg` files, including batches of several files at once. Hyperlinks inside PDFs (such as a CV's GitHub and LinkedIn links) are captured too.
- **Extracts what matters** — task type, deadline, amount, eligibility, required documents, and a plain-language summary, using Gemini with a strict "don't invent facts" prompt.
- **Remembers your documents** — upload your CV, transcript, photo, and financial statements *once*; they're reused and matched against every new task automatically, and your library survives page reloads.
- **Keeps every visitor's library private** — each browser gets its own library, uploaded files, and search index, so people trying the app never see each other's documents.
- **Checks what's missing** — a RAG-powered matcher (ChromaDB with hybrid search + reranking) compares each task's requirements against your personal library and tells you exactly what's still needed.
- **Drafts the paperwork for you** — application replies, cover letters, filled application forms, and financial declarations, generated as downloadable PDFs.
- **Builds your CV by conversation** — a 7-question guided interview turns your answers into a structured, professionally formatted CV (never inventing facts you didn't state), which is then automatically added to your library and matched against your tasks.
- **Keeps a human in the loop** — every generated draft goes through an explicit **Approve / Edit / Reject** step before it's considered final. Nothing is "sent" without your sign-off.
- **Tracks everything on a dashboard** — all detected tasks, sorted by deadline urgency, with a live "X/Y requirements ready" status per task.
- **Understands natural language commands** — a Quick Command box and a conversational Assistant let you say *"generate a draft for the scholarship one"* or *"check documents for the govt form"* instead of hunting for the right button.
- **Answers questions by text or voice** — per-document chat with suggested quick questions (*Deadline? What's missing? Summarize*), multi-document chat once two or more tasks exist, and voice notes with a recording UI. Answers come back as text.
- **Logs everything** — an audit trail of every draft approved, rejected, or executed, with timestamps.

## How It Works

```
   ┌─────────────┐     ┌──────────────┐     ┌────────────────────┐
   │   Upload    │ ──▶ │   Extract    │ ──▶ │   AI Reasoning      │
   │ PDF/DOCX/   │     │ file_readers │     │ (Gemini + fallback  │
   │ image/email │     │ + OCR        │     │  chain, strict JSON)│
   └─────────────┘     └──────────────┘     └─────────┬───────────┘
                                                        ▼
   ┌─────────────┐     ┌──────────────┐     ┌────────────────────┐
   │  Approve /  │ ◀── │   Generate    │ ◀── │  Match against      │
   │ Edit/Reject │     │ draft / form  │     │  personal library    │
   │  → PDF      │     │ / cover letter│     │  (ChromaDB RAG)      │
   └──────┬──────┘     └──────────────┘     └────────────────────┘
          ▼
   ┌─────────────┐
   │  Audit Log   │
   │ (Approved/   │
   │  Rejected/   │
   │  Executed)   │
   └─────────────┘
```

Every uploaded document flows through the same pipeline: **extract → understand → match → prepare → approve**. The AI never has the final word — it prepares, the person decides.

## Tech Stack

| Layer | Technology |
|---|---|
| Full-stack framework | [Reflex](https://reflex.dev/) (Python — frontend + backend in one language) |
| AI reasoning | Google **Gemini API**, with a 3-model fallback chain and automatic retry to handle rate limits |
| Document understanding | RAG via **ChromaDB** — hybrid search + reranking against a personal document library |
| Document ingestion | `pypdf`, `python-docx`, `pytesseract` + Tesseract OCR engine (with a Gemini vision fallback), `extract-msg` (Outlook), built-in `email` module |
| Document/CV generation | `reportlab` (structured PDF generation for drafts, forms, and CVs) |
| State & persistence | Reflex state management, with a lightweight per-visitor JSON index for library persistence |
| Hosting | Reflex Cloud (small 1 GB VM) |
| Dev environment | WSL (Ubuntu) + VS Code, Python 3.12 |

## Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/Vikram-Sootahar/Docket.git
cd Docket

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Install the Tesseract OCR engine for local image OCR
sudo apt install tesseract-ocr      # Debian/Ubuntu/WSL
# or: brew install tesseract        # macOS
# Without it, Docket falls back to Gemini vision for reading images.

# 5. Add your Gemini API key
cp .env.example .env
# then edit .env and add your key, e.g.:
# GEMINI_API_KEY=your_key_here

# 6. Run the app
reflex run
```

The app will be available at `http://localhost:3000`.

**Optional (development):** set `DOCKET_DATA_DIR` to a folder outside the project (for example `export DOCKET_DATA_DIR=~/DocketData`) before `reflex run`. Uploaded files, the library index, and the vector database are then stored there instead of inside the project folder, which stops Reflex's hot-reload from restarting the backend on every upload. Leave it unset in production.

> **Note:** Tesseract is a separate system-level engine, not just a Python package — `pip install pytesseract` alone does not install it. See [Challenges](#challenges-i-faced-and-how-i-solved-them) below.

## Project Structure

```
Docket/
├── Docket/
│   └── Docket.py            # Main Reflex app: UI components, state, page routing
├── rxconfig.py              # Reflex configuration
├── ai_reasoning.py          # Document analysis — extracts task_type, deadline, amount, etc.
├── ai_preparation.py        # Draft, financial form, and application form generation
├── ai_chat.py               # Per-document and multi-document conversational Q&A
├── assistant.py             # Global assistant that can trigger actions from natural language
├── command_router.py        # Routes free-text "Quick Commands" to the right document/action
├── cv_builder.py            # 7-question CV interview flow + PDF rendering
├── cv_ai.py                 # Turns interview answers into a structured CV via Gemini
├── cv_parser.py             # Extracts structured fields from an uploaded CV
├── matching.py              # RAG-based matching of required documents against the library
├── rag_store.py             # ChromaDB indexing/search for the document library
├── file_readers.py          # Unified text extraction router (PDF/DOCX/image/email/msg)
├── dashboard.py             # Multi-task dashboard data builder
├── audit.py                 # Approval/rejection audit log entries
├── gemini_retry.py          # Gemini fallback chain with automatic retry
├── assets/                  # Static assets
├── .env.example             # Template for your API key
└── requirements.txt
```

## Challenges I Faced (and How I Solved Them)

This section is deliberately detailed — these are real bugs found through hands-on testing, not a polished afterthought.

- **Library data disappeared on every page refresh.** The document library lived only in in-memory app state, so a browser refresh wiped it clean even though the underlying vector database still had the documents indexed. **Fix:** added a lightweight JSON index that's written on every library change and loaded back in on page load, so the UI and the underlying data stay in sync.

- **Newly uploaded tasks silently replaced older ones.** Uploading a second document made the first one vanish from the task list. Root cause: the upload handler reset the results list to empty before processing each new batch, instead of appending to it. **Fix:** changed the handler to append new results to the existing list.

- **The Enter key in chat sometimes sent an incomplete message.** Typing quickly and hitting Enter immediately would occasionally send a truncated message, because the framework's state hadn't caught up with the last few keystrokes yet. **Fix:** on Enter, the app now reads the live value straight from the DOM input instead of relying on the (potentially stale) state variable.

- **The AI occasionally invented information it didn't have.** Early on, a document check flagged a requirement as "found" against an unrelated test file with only a 30% similarity match — technically true by score, but misleading in practice. Separately, the LLM sometimes filled in a plausible-but-wrong deadline for documents that didn't actually state one. **Fix:** tightened the extraction prompt with an explicit "never invent a date/field you cannot support with the text — output 'None found' instead," and cleaned up noisy test data from the matching library.

- **Relative date parsing ("next Friday", "by tomorrow") was inconsistent.** Given the exact same phrasing in two different documents, the model sometimes calculated the correct date and sometimes didn't — even after explicitly providing today's date and day of the week in the prompt. This turned out to be a genuine limitation of LLM-based date reasoning rather than a prompt-wording issue, and is documented below rather than silently hidden.

- **Image uploads failed with a cryptic error.** OCR requires the actual Tesseract engine installed at the OS level — the Python wrapper alone isn't enough, and a hosted container may not have it. **Fix:** images are now resized before OCR, and if Tesseract isn't installed, Docket falls back to Gemini vision instead of failing.

- **The backend kept restarting while files were uploaded.** In development, Reflex's hot-reload treats new files inside the project folder as code changes, so every upload and every vector-database write restarted the backend and the browser lost its connection mid-upload. **Fix:** user data (uploads, library index, vector database) can live outside the project folder via `DOCKET_DATA_DIR`, which resolved it in testing.

- **A document library shared by everyone is useless for a public demo.** Early versions had one library for the whole app. **Fix:** every browser now gets a random visitor ID, and its files, library index, and vector-database collection are kept separate, so no one sees anyone else's documents.

## Known Limitations

Being upfront about these rather than hiding them:

- **No login system.** Privacy is per browser, not per account: each browser gets its own private library through a visitor ID stored in the browser. Clearing site data or switching device starts an empty library.
- **Payment and email sending are simulated.** The "Simulate Process Payment" and "Simulate Send Email" actions demonstrate the intended execution step but don't connect to a real payment gateway or SMTP/Gmail integration in this version.
- **Relative date resolution can be inconsistent**, as described above — it's resolved via LLM reasoning rather than a deterministic date-parsing library.
- **The CV builder can occasionally omit a section** (e.g. Projects) even when the user provided that information in the interview — a known edge case still being monitored.
- **Scanned PDFs without a text layer aren't OCR'd yet** (photos and images are). Very long PDFs are read up to the first 30 pages.
- **The hosted demo is small.** It runs on a 1 GB VM and the Gemini free tier, so very large files or many simultaneous users can be slow. The upload limit is 50 MB per file, but files of a few MB work best.
- **Voice note playback may not work in the hosted demo.** The recorded audio bubble can show 0:00 and not play back, although the recording is still sent and answered.

## What's Next

- **Google Search grounding** — when a document doesn't state an official deadline or application link, have the agent search for and verify it against the real, official source rather than leaving it blank.
- **Deterministic relative-date parsing** — replace pure LLM date reasoning with a rules-based parser for "next Friday"/"in 2 weeks"-style phrases.
- **Multi-user accounts** with proper authentication.
- **OCR for scanned PDFs.**
- **Deeper RAG layers** — contextual chunking, query rewriting, and (time permitting) a GraphRAG-based knowledge layer.
- **Real payment and email integrations** in place of the current simulated actions.

## Screenshots
### Home

<img width="1920" height="1080" alt="Home page" src="https://github.com/user-attachments/assets/a5eb5839-8ea2-4cea-b85a-edfcd8b56de5" />

### Tasks dashboard

<img width="1920" height="1080" alt="Tasks dashboard" src="https://github.com/user-attachments/assets/de6a4f9e-ba76-493f-a58e-7f8b2cceefa6" />

### Approval flow

<img width="1920" height="1080" alt="Approval flow, draft email" src="https://github.com/user-attachments/assets/720c7e6e-158f-4697-9b71-30938ebc2e65" />

### Activity log

<img width="1920" height="1080" alt="Activity Log" src="https://github.com/user-attachments/assets/71706217-cf09-4fa8-a964-89f10902c377" />

### CV builder

<img width="1920" height="1080" alt="CV preview" src="https://github.com/user-attachments/assets/dc141e49-2eb8-4448-a18a-d27b834f22be" />


## Demo

Live app: https://docket-gray-ocean.reflex.run

Demo video: https://youtu.be/Zk2l6AmcV-c

## About This Project

Docket was designed, built, and debugged solo — from the document-ingestion pipeline through the RAG-based matching system to the approval workflow and UI. It was built as a hands-on exercise in practical AI engineering: prompt design that resists hallucination, retrieval-augmented matching, and a full human-in-the-loop execution loop, not just a document-summarizing chatbot.

If you're reviewing this as part of a hackathon judging or portfolio review: every feature listed above was tested end-to-end with real (and deliberately broken) test documents, and the [Challenges](#challenges-i-faced-and-how-i-solved-them) section reflects actual bugs found and fixed during that process, not a hypothetical list.
