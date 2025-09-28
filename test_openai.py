# Create test_openai.py
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

print("=== Testing OpenAI Connection ===")

try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    print("✅ OpenAI client created successfully")
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say 'Hello from VT Dining Bot!'"}],
        max_tokens=20
    )
    
    print("✅ OpenAI API call successful!")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ OpenAI error: {e}")
    print("Check your API key and account credits")