from typing import Dict, Any
from core.llm_client import GeminiClient

ARCHITECT_DEV_PROMPT = """
You are a Principal Software Architect and Senior Python Developer.
Your job is to read the user's application requirement and produce a self-contained, high-quality Python module along with an exhaustive pytest test suite.

Rules:
1. Write clean, idiomatic, typed Python 3 code.
2. The application code must be self-contained in a single file called `app.py`. Do not require external web servers unless explicitly requested. Use Python standard library or standard data structures where possible.
3. The test suite must be compatible with `pytest` and import the functionality directly from `app` (e.g., `from app import ...`).
4. Include at least 4-6 diverse unit tests covering:
   - Happy paths / basic functionality
   - Edge cases (empty inputs, bounds, negative numbers, etc.)
   - Error handling / expected exceptions (using `pytest.raises`)
5. You MUST return your response strictly as a JSON object with this exact structure:
{
  "architecture_summary": "Brief 2-3 sentence overview of the design patterns and components.",
  "app_code": "# full Python code for app.py",
  "test_code": "# full pytest code for test_app.py"
}
"""

class ArchitectDeveloperAgent:
    """Agent 1: Generates architecture, application code (app.py), and test suite (test_app.py)."""
    
    def __init__(self, client: GeminiClient):
        self.client = client

    def run(self, user_prompt: str) -> Dict[str, Any]:
        prompt = (
            f"User Requirement:\n\"\"\"{user_prompt}\"\"\"\n\n"
            "Generate the architecture plan, the application code (`app.py`), and the pytest test suite (`test_app.py`)."
        )
        result = self.client.generate_json(prompt, system_instruction=ARCHITECT_DEV_PROMPT)
        
        # Validation and fallbacks
        if "app_code" not in result or "test_code" not in result:
            # Handle potential unparsed or malformed response
            raise ValueError(f"ArchitectDeveloperAgent failed to generate expected structure: {result}")
            
        return {
            "architecture_summary": result.get("architecture_summary", "Python application and test suite generated."),
            "app_code": result.get("app_code", "").strip(),
            "test_code": result.get("test_code", "").strip()
        }
