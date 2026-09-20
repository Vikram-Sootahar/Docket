from file_readers import extract_text_from_file

# Test all 5 file types using the single master function
files_to_test = [
    "test_files/ITC508_Both_Papers_Answers.pdf",
    "test_files/Cover_Letter.docx",
    "test_files/test_image.jpg",
    "test_files/test_email.eml",
    "test_files/test_message.msg",
]

for file_path in files_to_test:
    print(f"\n=== Testing: {file_path} ===")
    result = extract_text_from_file(file_path)

    if result["success"]:
        print(f"✅ SUCCESS — {len(result['text'])} characters extracted")
    else:
        print(f"❌ FAILED — {result['error']}")