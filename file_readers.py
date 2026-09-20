"""
file_readers.py

Reusable functions to extract text from different file types:
PDF, DOCX, Images (OCR), EML (email), and MSG (Outlook email).

Each function returns a dict:
  {"success": True, "text": "...", ...}   on success
  {"success": False, "error": "..."}      on failure
"""

import os
from pypdf import PdfReader
from docx import Document
import pytesseract
import shutil
from PIL import Image
import email
from email import policy
import extract_msg
from bs4 import BeautifulSoup


# Tell pytesseract where Tesseract is installed
_tesseract_path = shutil.which("tesseract")
if _tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path
elif os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_pdf_text(file_path):
    """Takes a PDF file path and returns the extracted text."""
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    if not file_path.lower().endswith(".pdf"):
        return {"success": False, "error": "File is not a PDF."}

    try:
        reader = PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text

        if not full_text.strip():
            return {"success": False, "error": "PDF has no extractable text (may be scanned/image-based)."}

        return {"success": True, "text": full_text}

    except Exception as e:
        return {"success": False, "error": f"Could not read PDF: {str(e)}"}


def extract_docx_text(file_path):
    """Takes a .docx file path and returns the extracted text."""
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    if not file_path.lower().endswith(".docx"):
        return {"success": False, "error": "File is not a .docx file."}

    try:
        doc = Document(file_path)
        full_text = ""
        for para in doc.paragraphs:
            full_text += para.text + "\n"

        if not full_text.strip():
            return {"success": False, "error": "Document has no extractable text."}

        return {"success": True, "text": full_text}

    except Exception as e:
        return {"success": False, "error": f"Could not read .docx file: {str(e)}"}


def extract_image_text(file_path):
    """Takes an image file path and returns the extracted text using OCR."""
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    valid_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")
    if not file_path.lower().endswith(valid_extensions):
        return {"success": False, "error": "File is not a supported image format."}

    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)

        if not text.strip():
            return {"success": False, "error": "No text could be extracted from the image."}

        return {"success": True, "text": text}

    except Exception as e:
        return {"success": False, "error": f"Could not read image: {str(e)}"}


def extract_eml_text(file_path):
    """Takes an .eml file path and returns sender, subject, date, and body text."""
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    if not file_path.lower().endswith(".eml"):
        return {"success": False, "error": "File is not an .eml file."}

    try:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)

        sender = msg.get("From", "Unknown")
        subject = msg.get("Subject", "No Subject")
        date = msg.get("Date", "Unknown")

        body = ""
        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_content()
                elif part.get_content_type() == "text/html":
                    html_body += part.get_content()
        else:
            if msg.get_content_type() == "text/html":
                html_body = msg.get_content()
            else:
                body = msg.get_content()

        if not body.strip() and html_body.strip():
            soup = BeautifulSoup(html_body, "html.parser")
            body = soup.get_text(separator="\n")

        if not body.strip():
            return {"success": False, "error": "No text content found in email."}

        return {
            "success": True,
            "sender": sender,
            "subject": subject,
            "date": date,
            "text": body
        }

    except Exception as e:
        return {"success": False, "error": f"Could not read .eml file: {str(e)}"}


def extract_msg_text(file_path):
    """Takes a .msg file path and returns sender, subject, date, and body text."""
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    if not file_path.lower().endswith(".msg"):
        return {"success": False, "error": "File is not a .msg file."}

    try:
        msg = extract_msg.Message(file_path)

        sender = msg.sender or "Unknown"
        subject = msg.subject or "No Subject"
        date = msg.date or "Unknown"
        body = msg.body or ""

        msg.close()

        if not body.strip():
            return {"success": False, "error": "No text content found in email."}

        return {
            "success": True,
            "sender": sender,
            "subject": subject,
            "date": date,
            "text": body
        }

    except Exception as e:
        return {"success": False, "error": f"Could not read .msg file: {str(e)}"}


def extract_text_from_file(file_path):
    """
    Master function — automatically detects file type from extension
    and calls the right extraction function.
    """
    ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""

    if ext == "pdf":
        return extract_pdf_text(file_path)
    elif ext == "docx":
        return extract_docx_text(file_path)
    elif ext in ("png", "jpg", "jpeg", "bmp", "tiff"):
        return extract_image_text(file_path)
    elif ext == "eml":
        return extract_eml_text(file_path)
    elif ext == "msg":
        return extract_msg_text(file_path)
    else:
        return {"success": False, "error": f"Unsupported file type: .{ext}"}