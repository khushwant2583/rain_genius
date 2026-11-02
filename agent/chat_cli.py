"""CLI entry point: python -m agent.chat_cli"""
import uuid
from agent.graph import chat

thread_id = str(uuid.uuid4())
print("Rajasthan Rainwater Harvesting & Water Advisor (type 'quit' to exit)")
print("English and Roman Hinglish supported. This is a decision-support prototype, not a government service.\n")
try:
    while True:
        text = input("You: ").strip()
        if text.lower() in {"quit", "exit"}: break
        if not text: continue
        result = chat(text, thread_id)
        print("Advisor:", result.get("reply", "Sorry, I could not prepare a response."), "\n")
except (KeyboardInterrupt, EOFError):
    print("\nGoodbye.")
