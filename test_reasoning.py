from file_readers import extract_text_from_file
from ai_reasoning import analyze_text

file_path = "test_files/test_image.jpg"

extraction_result = extract_text_from_file(file_path)

if not extraction_result["success"]:
    print(f"Extraction failed: {extraction_result['error']}")
else:
    print("✅ Text extracted successfully.\n")

    analysis = analyze_text(extraction_result["text"])

    if analysis["success"]:
        print("----- AI ANALYSIS -----")
        print(f"Task Type: {analysis['task_type']}")
        print(f"Summary: {analysis['summary']}")
        print(f"Deadline: {analysis['deadline']}")
        print(f"Required Documents: {analysis['required_documents']}")
        print(f"Amount: {analysis['amount']}")
        print(f"Recipient/Purpose: {analysis['recipient_or_purpose']}")
        print(f"Key Details: {analysis['key_details']}")
    else:
        print(f"❌ Analysis failed: {analysis['error']}")