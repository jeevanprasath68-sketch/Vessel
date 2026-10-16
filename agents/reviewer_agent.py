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

    @staticmethod
    def calculate_quality_metrics(
        app_code: str,
        test_code: str,
        test_result: Dict[str, Any],
        repair_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculates a deterministic, objective software engineering quality score (0-10)
        based on test execution, self-repair friction, test suite depth, and code architecture.
        """
        # 1. Test Verification (Max 4.0 pts)
        passed = test_result.get("passed_tests", 0)
        total = test_result.get("total_tests", 0)
        success = test_result.get("success", False)

        if success and total > 0 and passed == total:
            test_pts = 4.0
        elif total > 0:
            test_pts = round((passed / total) * 4.0, 1)
        else:
            test_pts = 0.0

        # 2. Self-Repair Efficiency (Max 1.5 pts)
        repairs = len(repair_history)
        if repairs == 0:
            repair_pts = 1.5
        elif repairs == 1:
            repair_pts = 1.1
        elif repairs == 2:
            repair_pts = 0.7
        else:
            repair_pts = 0.3

        # 3. Test Suite Depth & Coverage (Max 2.0 pts)
        if total >= 6:
            count_pts = 1.0
        elif total >= 4:
            count_pts = 0.7
        elif total >= 2:
            count_pts = 0.4
        else:
            count_pts = 0.2

        has_raises = "pytest.raises" in test_code or "raises(" in test_code
        raises_pts = 0.5 if has_raises else 0.0

        test_code_lower = test_code.lower()
        has_edges = any(w in test_code_lower for w in ["empty", "invalid", "negative", "zero", "missing", "bound", "none"])
        edge_pts = 0.5 if has_edges else 0.0

        test_depth_pts = min(2.0, round(count_pts + raises_pts + edge_pts, 1))

        # 4. Code Architecture, Typing & Resilience (Max 2.5 pts)
        has_class = "class " in app_code
        oop_pts = 0.7 if has_class else 0.3

        has_typing = any(hint in app_code for hint in ["->", ": str", ": int", ": List", ": Dict", ": Optional", ": Any"])
        typing_pts = 0.6 if has_typing else 0.0

        has_error_handling = "try:" in app_code and "except" in app_code
        error_pts = 0.6 if has_error_handling else 0.0

        has_db_resilience = "pragma table_info" in app_code.lower() or "alter table" in app_code.lower() or "sqlite3" in app_code.lower()
        db_pts = 0.3 if has_db_resilience else 0.0

        has_docs = '"""' in app_code or "'''" in app_code or "# " in app_code
        doc_pts = 0.3 if has_docs else 0.0

        arch_pts = min(2.5, round(oop_pts + typing_pts + error_pts + db_pts + doc_pts, 1))

        total_score = round(test_pts + repair_pts + test_depth_pts + arch_pts, 1)
        total_score = max(1.0, min(10.0, total_score))

        return {
            "score": total_score,
            "overall_score": f"{total_score:.1f}/10",
            "breakdown": {
                "test_verification": f"{test_pts:.1f} / 4.0",
                "repair_efficiency": f"{repair_pts:.1f} / 1.5",
                "test_depth": f"{test_depth_pts:.1f} / 2.0",
                "code_architecture": f"{arch_pts:.1f} / 2.5"
            }
        }

    def review(
        self,
        user_prompt: str,
        app_code: str,
        test_code: str,
        test_result: Dict[str, Any],
        repair_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        # Compute objective engineering metrics first
        computed_metrics = self.calculate_quality_metrics(
            app_code=app_code,
            test_code=test_code,
            test_result=test_result,
            repair_history=repair_history
        )

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
            f"=== BENCHMARK QUALITY SCORE ===\n"
            f"Calculated Score: {computed_metrics['overall_score']}\n\n"
            "Provide the final executive review and summary according to the required JSON schema."
        )

        result = self.client.generate_json(prompt, system_instruction=REVIEWER_AGENT_PROMPT)

        status = result.get("status", "VERIFIED" if test_result.get("success") else "FAILED")
        summary = result.get("summary", "Automated multi-agent code review complete.")
        key_findings = result.get("key_findings", [])
        unresolved = result.get("unresolved_problems", [])
        recommendations = result.get("technical_debt_and_recommendations", [])

        # Use the computed deterministic score rather than an arbitrary static string
        return {
            "status": status,
            "overall_score": computed_metrics["overall_score"],
            "score_breakdown": computed_metrics["breakdown"],
            "summary": summary,
            "key_findings": key_findings,
            "unresolved_problems": unresolved,
            "technical_debt_and_recommendations": recommendations
        }
