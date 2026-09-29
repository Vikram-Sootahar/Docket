from ai_preparation import generate_financial_declaration, save_draft_as_pdf, preview_draft, review_draft

sample_data = {
    "name": "Vikram Sootahar",
    "cnic": "41304-1234567-1",
    "amount": "PKR 50,000",
    "purpose": "Semester tuition fee payment",
    "date": "16 September 2026",
    "place": "Tandojam"
}
result = generate_financial_declaration(sample_data)

print("----- FINANCIAL DECLARATION -----")
if result["success"]:
    review_result = review_draft(result["text"], "Financial Declaration")

    if review_result["status"] == "approved":
        pdf_result = save_draft_as_pdf(review_result["text"], "test_financial_declaration_output.pdf")
        print(pdf_result)
    else:
        print("Draft was rejected. No PDF generated.")
else:
    print(f"ERROR: {result['error']}")