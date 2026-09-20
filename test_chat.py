from ai_chat import answer_question

with open("test_job_posting.txt", "r", encoding="utf-8") as f:
    document_text = f.read()

history = []

# First question
q1 = "What is the deadline for this job application?"
result1 = answer_question(document_text, q1, history)
print("----- Q1 -----")
print(result1["answer"])

history.append({"question": q1, "answer": result1["answer"]})

# Follow-up question
q2 = "What documents do I need to send along with it?"
result2 = answer_question(document_text, q2, history)
print("\n----- Q2 (follow-up) -----")
if result2["success"]:
    print(result2["answer"])
else:
    print(f"ERROR: {result2['error']}")