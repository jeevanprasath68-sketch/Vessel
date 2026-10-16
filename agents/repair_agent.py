from typing import Dict, Any, Optional
from core.llm_client import GeminiClient

REPAIR_AGENT_PROMPT = """
You are an Expert Automated Code Repair Agent and Debugger.
Your task is to analyze real test failure outputs, assertion errors, and stack traces, and provide a pinpoint fix to the application code (`app.py`).

Guidelines:
1. Examine the failure traceback carefully: identify whether it's a logic error, unexpected exception, missing edge case check, or type mismatch.
2. Fix `app.py` so that it satisfies all the test cases.
3. Keep changes focused on fixing the bug without breaking other functionality.
4. If a test case in `test_app.py` has an objectively incorrect expectation or syntax error, you may provide an updated `test_code`.
5. CRITICAL UI PRESERVATION: If `app.py` contains a Streamlit UI (`import streamlit as st`, widgets, pages), YOU MUST PRESERVE AND RETURN THE ENTIRE UI AT THE BOTTOM OF `app.py`. NEVER drop or omit the UI code when fixing logic!
6. DATABASE RESILIENCE: If the failure is `sqlite3.OperationalError` (e.g. missing column, no such table), ensure `app.py` performs safe schema migration (`PRAGMA table_info` and `ALTER TABLE ... ADD COLUMN`) and defensive try/except handling so existing database files don't crash the app.
7. JAVASCRIPT / EMBEDDED HTML NameError: If the failure is `NameError` occurring inside embedded JavaScript or HTML (e.g. `${var}` or `${obj.prop}` inside an f-string), convert the JavaScript template literal to standard string concatenation (e.g. `"Score: " + var`) or remove the `f` prefix from the string and use `.replace()`. Never allow Python f-strings to evaluate JS identifiers.
8. You MUST return your response strictly as a JSON object:
{
  "explanation": "Clear explanation of the root cause and what changes were made to fix it.",
  "app_code": "# full complete updated Python code for app.py (never return null)",
  "test_code": "# full complete pytest code for test_app.py (or null if unchanged)"
}
"""

class RepairAgent:
    """Agent 3: Analyzes actual failure tracebacks and repairs the application code."""

    def __init__(self, client: GeminiClient):
        self.client = client

    def repair(
        self,
        app_code: str,
        test_code: str,
        failure_details: str,
        full_output: str,
        iteration: int = 1
    ) -> Dict[str, Any]:
        prompt = (
            f"=== REPAIR ATTEMPT #{iteration} ===\n\n"
            f"--- Current app.py ---\n```python\n{app_code}\n```\n\n"
            f"--- test_app.py ---\n```python\n{test_code}\n```\n\n"
            f"--- Pytest Failure Output & Traceback ---\n```\n{failure_details or full_output}\n```\n\n"
            "Diagnose the error, fix the bugs in `app.py`, and return the complete corrected code in valid JSON format."
        )

        result = self.client.generate_json(prompt, system_instruction=REPAIR_AGENT_PROMPT)

        raw_app = result.get("app_code")
        if raw_app and isinstance(raw_app, str) and raw_app.strip():
            updated_app_code = raw_app.strip()
        else:
            updated_app_code = app_code

        raw_test = result.get("test_code")
        if raw_test and isinstance(raw_test, str) and raw_test.strip():
            updated_test_code = raw_test.strip()
        else:
            updated_test_code = test_code

        explanation = result.get("explanation")
        if not explanation or not isinstance(explanation, str):
            explanation = "Applied automated bug fix based on failure traceback."

        return {
            "explanation": str(explanation).strip(),
            "app_code": updated_app_code,
            "test_code": updated_test_code,
            "iteration": iteration
        }
