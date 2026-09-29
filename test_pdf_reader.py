from pypdf import PdfReader
import os


def extract_pdf_text(file_path):
    """
    Takes a PDF file path and returns the extracted text.
    Returns a dict with either 'success' + 'text', or 'error' + message.
    """
    # Check file exists
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    # Check it's a PDF
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


# ---- Test run (only runs when this file is executed directly) ----
if __name__ == "__main__":
    pdf_path = "test_files/ITC508_Both_Papers_Answers.pdf"

    result = extract_pdf_text(pdf_path)

    if result["success"]:
        print("----- EXTRACTED TEXT -----")
        print(result["text"])
        print("----- END -----")
        print(f"\nTotal characters extracted: {len(result['text'])}")
    else:
        print(f"ERROR: {result['error']}")