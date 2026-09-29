from docx import Document
import os


def extract_docx_text(file_path):
    """
    Takes a .docx file path and returns the extracted text.
    Returns a dict with either 'success' + 'text', or 'error' + message.
    """
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


# ---- Test run ----
if __name__ == "__main__":
    docx_path = "test_files/Cover_Letter.docx"   # <-- yahan apni file ka naam daalo

    result = extract_docx_text(docx_path)

    if result["success"]:
        print("----- EXTRACTED TEXT -----")
        print(result["text"])
        print("----- END -----")
        print(f"\nTotal characters extracted: {len(result['text'])}")
    else:
        print(f"ERROR: {result['error']}")