import sys
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        api_key = input("Enter your Google Gemini API Key: ").strip()

    if not api_key:
        print("[Error] No API key provided.")
        sys.exit(1)

    print(f"\n1. Testing Google Gemini API connection with key: {api_key[:6]}...{api_key[-4:]}")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        print("2. Querying available models via client.models.list()...")
        
        models = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", []) or []
            if "generateContent" in actions or not actions:
                clean_name = (m.name or "").replace("models/", "")
                if "gemini" in clean_name.lower():
                    models.append(clean_name)

        if models:
            print(f"\n[SUCCESS] Found {len(models)} model(s) supporting generateContent:")
            for m in models:
                print(f"  - {m}")
            
            # Test generation with the first model
            test_model = models[0]
            print(f"\n3. Testing generation with model: '{test_model}'...")
            res = client.models.generate_content(
                model=test_model,
                contents="Say 'Gemini is fully operational!' in one short sentence."
            )
            print(f"Response: {res.text.strip()}")
            print("\nAll systems GO! You can use this model in your Streamlit dashboard.")
        else:
            print("\n[WARNING] No Gemini models found supporting generateContent for this key.")
            print("Possible causes:")
            print("1. If using Google Cloud: Ensure 'Generative Language API' is enabled on this project:")
            print("   https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com")
            print("2. If using Google AI Studio: Create a free key directly at:")
            print("   https://aistudio.google.com/app/apikey")

    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("\nFix suggestions:")
        print("1. Ensure your API key is created from Google AI Studio: https://aistudio.google.com/app/apikey")
        print("2. In Google Cloud Console, ensure 'Generative Language API' is enabled.")

if __name__ == "__main__":
    main()
