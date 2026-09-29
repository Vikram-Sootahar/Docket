import extract_msg
import os


def extract_msg_text(file_path):
    """
    Takes a .msg file path and returns sender, subject, date, and body text.
    Returns a dict with either 'success' + data, or 'error' + message.
    """
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


# ---- Test run ----
if __name__ == "__main__":
    msg_path = "test_files/test_message.msg"

    result = extract_msg_text(msg_path)

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