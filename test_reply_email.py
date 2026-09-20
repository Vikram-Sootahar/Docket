from ai_reasoning import analyze_text

with open("test_reply_email.txt", "r", encoding="utf-8") as f:
    text = f.read()

result = analyze_text(text)

print("----- ANALYSIS RESULT -----")
for key, value in result.items():
    print(f"{key}: {value}")