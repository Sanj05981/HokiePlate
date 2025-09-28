# Create test_env.py
from dotenv import load_dotenv
import os

load_dotenv()

print("=== Environment Variable Check ===")
print(f"OpenAI API Key loaded: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
print(f"Admin API Key loaded: {'Yes' if os.getenv('ADMIN_API_KEY') else 'No'}")
print(f"OpenAI key format correct: {os.getenv('OPENAI_API_KEY', '').startswith('sk-')}")
print(f"OpenAI key length: {len(os.getenv('OPENAI_API_KEY', ''))}")