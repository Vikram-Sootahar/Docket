from file_readers import extract_text_from_file
from ai_reasoning import analyze_text
from ai_preparation import generate_reply_draft

# Step 1: Read the original email
with open("test_reply_email.txt", "r", encoding="utf-8") as f:
    original_text = f.read()

# Step 2: Analyze it
analysis = analyze_text(original_text)
print("----- ANALYSIS -----")
print(analysis)

# Step 3: Generate a draft reply based on the analysis
draft_result = generate_reply_draft(original_text, analysis)
print("\n----- DRAFT REPLY -----")
if draft_result["success"]:
    print(draft_result["draft"])
else:
    print(f"ERROR: {draft_result['error']}")