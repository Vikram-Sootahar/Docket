from ai_reasoning import analyze_text
from ai_preparation import generate_cover_letter, save_draft_as_pdf, preview_draft

# Step 1: Read the CV and job posting
with open("test_cv.txt", "r", encoding="utf-8") as f:
    cv_text = f.read()

with open("test_job_posting.txt", "r", encoding="utf-8") as f:
    job_text = f.read()

# Step 2: Analyze the job posting
job_analysis = analyze_text(job_text)
print("----- JOB ANALYSIS -----")
print(job_analysis)

# Step 3: Generate the cover letter
result = generate_cover_letter(cv_text, job_text, job_analysis)
print("\n----- COVER LETTER -----")
if result["success"]:
    print(result["draft"])
    preview_draft(result["draft"], "Cover Letter")
else:
    print(f"ERROR: {result['error']}")

if result["success"]:
    pdf_result = save_draft_as_pdf(result["draft"], "test_cover_letter_output.pdf")
    print(pdf_result)