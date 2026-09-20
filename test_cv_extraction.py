from ai_preparation import extract_cv_fields

with open("test_cv.txt", "r", encoding="utf-8") as f:
    cv_text = f.read()

result = extract_cv_fields(cv_text)

print("----- EXTRACTED CV FIELDS -----")
if result["success"]:
    print(result["fields"])
else:
    print(f"ERROR: {result['error']}")

def preview_draft(draft_text: str, draft_type: str = "Document") -> None:
    """
    Displays a formatted preview of a draft before approval.
    Does not return anything — just prints a clean preview to the console.
    """
    separator = "=" * 60

    print(f"\n{separator}")
    print(f"PREVIEW: {draft_type}")
    print(separator)
    print(draft_text)
    print(separator)
    print("Status: Awaiting approval\n")