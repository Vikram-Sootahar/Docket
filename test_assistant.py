from assistant import assistant_reply

context = """TODAY: 2026-09-21
TASKS:
- test_scholarship_task.docx | type: scholarship | deadline: October 15, 2026 | status: 0/5 ready | missing: CV, Transcript, Passport-size Photo, Bank Statement (last 3 months), National ID / Passport copy
LIBRARY:
(empty)"""

filenames = ["test_scholarship_task.docx"]
history = []

messages = [
    "hi",
    "scholarship ke liye mujhe kya kya chahiye?",
    "mera cv nahi hai, bana do",
    "documents check kar do",
    "what is the capital of France?",
]

for m in messages:
    result = assistant_reply(m, context, history, filenames)
    print(">>", m)
    print(result)
    print()
    if result["success"]:
        history.append({"role": "user", "text": m})
        history.append({"role": "assistant", "text": result["reply"]})