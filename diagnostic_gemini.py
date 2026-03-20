import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Loaded API Key: {api_key[:10]}...{api_key[-5:]}" if api_key else "NO KEY FOUND")

try:
    genai.configure(api_key=api_key)
    print("Testing connection...")
    models = genai.list_models()
    print("Success! Available models:")
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
            break
except Exception as e:
    print(f"Error connecting to Gemini: {e}")
