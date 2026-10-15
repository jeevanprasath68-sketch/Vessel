import json
from typing import Dict, Any, List
from core.llm_client import GeminiClient

REVIEWER_AGENT_PROMPT = """
You are a Principal Software Quality Assurance Lead and Code Reviewer.
Your role is to summarize the verified results, evaluate code quality, and highlight any unresolved problems or technical debt.

Review Criteria:
1. Verification Status: Whether all unit tests passed and the user requirement was satisfied.
2. Robustness & Design: Python best practices, exception handling, data structures.
3. Test Coverage: Are critical edge cases tested and verified?
4. Unresolved Problems: Explicitly list any remaining test failures or edge cases not handled.
5. Technical Debt & Recommendations: Concrete next steps for production deployment.

Return your evaluation strictly as JSON:
{
  "status": "VERIFIED" | "PARTIAL" | "FAILED",
  "overall_score": "e.g. 9.0/10",
  "summary": "Executive summary of the verified results and application state.",
  "key_findings": ["Point 1", "Point 2", "..."],
  "unresolved_problems": ["Unresolved issue 1", "..."],
  "technical_debt_and_recommendations": ["Recommendation 1", "..."]
}
"""

class ReviewerAgent:
    """Agent 4: Reviews the final application, test results, and repair history."""

    def __init__(self, client: GeminiClient):
        self.client = client

    def review(
        self,
        user_prompt: str,
        app_code: str,
        test_code: str,
        test_result: Dict[str, Any],
        repair_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        prompt = (
            f"=== INITIAL USER SPECIFICATION ===\n{user_prompt}\n\n"
            f"=== FINAL APPLICATION CODE (app.py) ===\n```python\n{app_code}\n```\n\n"
            f"=== TEST SUITE (test_app.py) ===\n```python\n{test_code}\n```\n\n"
            f"=== TEST RUN OUTCOME ===\n"
            f"- Exit Code: {test_result.get('exit_code')}\n"
            f"- Tests Passed: {test_result.get('passed_tests', 0)}/{test_result.get('total_tests', 0)}\n"
            f"- Tests Failed: {test_result.get('failed_tests', 0)}\n"
            f"- Tests Success: {test_result.get('success', False)}\n\n"
            f"=== REPAIR HISTORY ({len(repair_history)} iteration(s)) ===\n"
            f"{json.dumps(repair_history, indent=2)}\n\n"
            "Provide the final executive review and summary according to the required JSON schema."
        )

        result = self.client.generate_json(prompt, system_instruction=REVIEWER_AGENT_PROMPT)

        # Fallback values if JSON keys were missing
        status = result.get("status", "VERIFIED" if test_result.get("success") else "FAILED")
        score = result.get("overall_score", "8.5/10" if test_result.get("success") else "5.0/10")
        summary = result.get("summary", "Review complete.")
        key_findings = result.get("key_findings", [])
        unresolved = result.get("unresolved_problems", [])
        recommendations = result.get("technical_debt_and_recommendations", [])

        return {
            "status": status,
            "overall_score": score,
            "summary": summary,
            "key_findings": key_findings,
            "unresolved_problems": unresolved,
            "technical_debt_and_recommendations": recommendations
        }
