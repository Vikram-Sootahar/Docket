import email
from email import policy
import os


def extract_eml_text(file_path):
    """
    Takes an .eml file path and returns sender, subject, and body text.
    Returns a dict with either 'success' + data, or 'error' + message.
    """
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

        # Get the plain text body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_content()
        else:
            body = msg.get_content()

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


# ---- Test run ----
if __name__ == "__main__":
    eml_path = "test_files/test_email.eml"

    result = extract_eml_text(eml_path)

    if result["success"]:
        print("----- EMAIL INFO -----")
        print(f"From: {result['sender']}")
        print(f"Subject: {result['subject']}")
        print(f"Date: {result['date']}")
        print("----- BODY TEXT -----")
        print(result["text"])
        print("----- END -----")
        print(f"\nTotal characters extracted: {len(result['text'])}")
    else:
        print(f"ERROR: {result['error']}")