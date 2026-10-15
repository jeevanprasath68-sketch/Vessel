from typing import Dict, Any, Optional
from core.llm_client import GeminiClient

REPAIR_AGENT_PROMPT = """
You are an Expert Automated Code Repair Agent and Debugger.
Your task is to analyze real test failure outputs, assertion errors, and stack traces, and provide a pinpoint fix to the application code (`app.py`).

Guidelines:
1. Examine the failure traceback carefully: identify whether it's a logic error, unexpected exception, missing edge case check, or type mismatch.
2. Fix `app.py` so that it satisfies all the test cases.
3. Keep changes minimal and focused on fixing the bug without breaking other functionality.
4. If and only if a test case in `test_app.py` has an objectively incorrect expectation or impossible condition, you may provide an updated `test_code`, but prefer fixing `app_code` first.
5. Return your response strictly as a JSON object:
{
  "explanation": "Clear explanation of the root cause and what changes were made to fix it.",
  "app_code": "# full updated Python code for app.py",
  "test_code": "# optional: only provide if test_app.py itself needed modification, otherwise null"
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

        updated_app_code = result.get("app_code", "").strip() or app_code
        updated_test_code = result.get("test_code")
        explanation = result.get("explanation", "Applied automated bug fix based on failure traceback.")

        return {
            "explanation": explanation,
            "app_code": updated_app_code,
            "test_code": updated_test_code if updated_test_code else test_code,
            "iteration": iteration
        }
