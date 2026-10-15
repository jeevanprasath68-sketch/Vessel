import difflib
from typing import Generator, Dict, Any, List
from core.llm_client import GeminiClient
from agents.architect_dev import ArchitectDeveloperAgent
from agents.testing_engine import TestingEngine
from agents.repair_agent import RepairAgent
from agents.reviewer_agent import ReviewerAgent

class MultiAgentOrchestrator:
    """
    Coordinates the 5-agent pipeline:
    1. Architect + Developer -> Generates initial app.py and test_app.py
    2. Testing Engine -> Runs pytest in isolated sandbox
    3. Repair Agent -> Iterative diagnostic repair on test failures
    4. Reviewer Agent -> Summarizes verified results & technical debt
    5. Dashboard (Consumer) -> Displays real-time updates and metrics
    """

    def __init__(self, gemini_client: GeminiClient, max_repairs: int = 3, timeout_seconds: int = 20):
        self.client = gemini_client
        self.max_repairs = max_repairs
        self.architect_dev = ArchitectDeveloperAgent(self.client)
        self.testing_engine = TestingEngine(timeout_seconds=timeout_seconds)
        self.repair_agent = RepairAgent(self.client)
        self.reviewer_agent = ReviewerAgent(self.client)

    def execute_stream(self, user_prompt: str) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Executes the full pipeline step-by-step, yielding progress events
        for real-time display in the Streamlit UI.
        """
        pipeline_state = {
            "prompt": user_prompt,
            "architecture_summary": "",
            "initial_app_code": "",
            "current_app_code": "",
            "test_code": "",
            "repair_history": [],
            "test_history": [],
            "latest_test_result": {},
            "review": {},
            "status": "RUNNING"
        }

        # Step 1: Architect + Developer
        yield {
            "event": "STAGE_START",
            "agent": "Architect + Developer",
            "message": "Analyzing prompt, designing architecture, and generating Python code with tests..."
        }

        arch_result = self.architect_dev.run(user_prompt)
        app_code = arch_result["app_code"]
        test_code = arch_result["test_code"]
        arch_summary = arch_result["architecture_summary"]

        pipeline_state["initial_app_code"] = app_code
        pipeline_state["current_app_code"] = app_code
        pipeline_state["test_code"] = test_code
        pipeline_state["architecture_summary"] = arch_summary

        yield {
            "event": "ARCHITECT_DONE",
            "agent": "Architect + Developer",
            "message": "Initial code and test suite successfully generated.",
            "data": {
                "architecture_summary": arch_summary,
                "app_code": app_code,
                "test_code": test_code
            }
        }

        # Step 2: Initial Test Run
        yield {
            "event": "STAGE_START",
            "agent": "Testing Engine",
            "message": "Executing pytest in sandboxed restricted environment..."
        }

        test_result = self.testing_engine.run_tests(app_code, test_code)
        pipeline_state["test_history"].append(test_result)
        pipeline_state["latest_test_result"] = test_result

        yield {
            "event": "TEST_RUN_DONE",
            "agent": "Testing Engine",
            "iteration": 0,
            "success": test_result["success"],
            "message": f"Tests executed: {test_result['passed_tests']} passed, {test_result['failed_tests']} failed.",
            "data": test_result
        }

        # Step 3: Repair Loop if tests failed
        repair_iteration = 0
        while not test_result["success"] and repair_iteration < self.max_repairs:
            repair_iteration += 1
            yield {
                "event": "STAGE_START",
                "agent": "Repair Agent",
                "iteration": repair_iteration,
                "message": f"Repair cycle #{repair_iteration}: Diagnosing failure traceback and patching code..."
            }

            previous_code = pipeline_state["current_app_code"]
            repair_result = self.repair_agent.repair(
                app_code=previous_code,
                test_code=pipeline_state["test_code"],
                failure_details=test_result.get("failure_details", ""),
                full_output=test_result.get("full_output", ""),
                iteration=repair_iteration
            )

            # Compute diff between iterations
            diff_lines = list(difflib.unified_diff(
                previous_code.splitlines(keepends=True),
                repair_result["app_code"].splitlines(keepends=True),
                fromfile=f"app.py (v{repair_iteration-1})",
                tofile=f"app.py (v{repair_iteration})"
            ))
            diff_text = "".join(diff_lines)

            repair_record = {
                "iteration": repair_iteration,
                "explanation": repair_result["explanation"],
                "diff": diff_text,
                "app_code": repair_result["app_code"]
            }
            pipeline_state["repair_history"].append(repair_record)
            pipeline_state["current_app_code"] = repair_result["app_code"]
            pipeline_state["test_code"] = repair_result["test_code"]

            yield {
                "event": "REPAIR_DONE",
                "agent": "Repair Agent",
                "iteration": repair_iteration,
                "message": f"Repair #{repair_iteration} applied: {repair_result['explanation']}",
                "data": repair_record
            }

            # Re-test in sandbox
            yield {
                "event": "STAGE_START",
                "agent": "Testing Engine",
                "iteration": repair_iteration,
                "message": f"Re-testing code after repair #{repair_iteration}..."
            }

            test_result = self.testing_engine.run_tests(
                pipeline_state["current_app_code"],
                pipeline_state["test_code"]
            )
            pipeline_state["test_history"].append(test_result)
            pipeline_state["latest_test_result"] = test_result

            yield {
                "event": "TEST_RUN_DONE",
                "agent": "Testing Engine",
                "iteration": repair_iteration,
                "success": test_result["success"],
                "message": f"Re-test results: {test_result['passed_tests']} passed, {test_result['failed_tests']} failed.",
                "data": test_result
            }

        # Step 4: Reviewer Agent
        yield {
            "event": "STAGE_START",
            "agent": "Reviewer Agent",
            "message": "Performing comprehensive code audit, quality check, and summarising verified results..."
        }

        review_result = self.reviewer_agent.review(
            user_prompt=user_prompt,
            app_code=pipeline_state["current_app_code"],
            test_code=pipeline_state["test_code"],
            test_result=pipeline_state["latest_test_result"],
            repair_history=pipeline_state["repair_history"]
        )
        pipeline_state["review"] = review_result
        pipeline_state["status"] = "COMPLETED"

        yield {
            "event": "REVIEW_DONE",
            "agent": "Reviewer Agent",
            "message": f"Review finalized. Overall status: {review_result['status']} ({review_result.get('overall_score', '')})",
            "data": review_result
        }

        yield {
            "event": "PIPELINE_COMPLETE",
            "message": "All 5 agents finished their execution.",
            "data": pipeline_state
        }

        return pipeline_state
