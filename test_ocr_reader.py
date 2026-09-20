import pytesseract
from PIL import Image
import os

# Tell pytesseract where Tesseract is installed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_image_text(file_path):
    """
    Takes an image file path and returns the extracted text using OCR.
    Returns a dict with either 'success' + 'text', or 'error' + message.
    """
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


# ---- Test run ----
if __name__ == "__main__":
    image_path = "test_files/test_image.jpg"   # <-- yahan apni image ka naam daalo

    result = extract_image_text(image_path)

    if result["success"]:
        print("----- EXTRACTED TEXT -----")
        print(result["text"])
        print("----- END -----")
        print(f"\nTotal characters extracted: {len(result['text'])}")
    else:
        print(f"ERROR: {result['error']}")