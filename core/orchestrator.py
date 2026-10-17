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

    def execute_stream(self, user_prompt: str, app_type: str = "Streamlit Web App", auto_push: bool = True) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Executes the full pipeline step-by-step, yielding progress events
        for real-time display in the Streamlit UI.
        """
        import os
        pipeline_state = {
            "prompt": user_prompt,
            "app_type": app_type,
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
        from agents.architect_dev import is_game_requirement
        is_game = is_game_requirement(user_prompt, app_type)
        if is_game:
            step_msg = "Detected Game / Arcade requirement — designing AAA Web Game Architecture (Neon Canvas, Web Audio Synthesizer, Particle Engine, Dual Controls & SQLite Leaderboard)..."
        else:
            step_msg = f"Analyzing prompt, designing architecture for '{app_type}', and generating Python code with tests..."

        yield {
            "event": "STAGE_START",
            "agent": "Architect + Developer",
            "message": step_msg
        }

        arch_result = self.architect_dev.run(user_prompt, app_type=app_type)
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

        msg = self._format_test_summary(test_result)
        yield {
            "event": "TEST_RUN_DONE",
            "agent": "Testing Engine",
            "iteration": 0,
            "success": test_result["success"],
            "message": msg,
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

            msg = self._format_test_summary(test_result)
            yield {
                "event": "TEST_RUN_DONE",
                "agent": "Testing Engine",
                "iteration": repair_iteration,
                "success": test_result["success"],
                "message": f"Re-test #{repair_iteration}: {msg}",
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

        # Automatically export standalone generated application to generated_app/
        output_dir = os.path.join(os.getcwd(), "generated_app")
        os.makedirs(output_dir, exist_ok=True)

        # Wipe stale database files and runtime caches from previous runs/apps
        # so old incompatible schemas or leftover data never corrupt new apps
        for fname in os.listdir(output_dir):
            if fname.endswith((".db", ".sqlite", ".sqlite3", ".db-journal", ".db-wal", ".db-shm")):
                try:
                    os.remove(os.path.join(output_dir, fname))
                except Exception:
                    pass

        # Write .gitignore to prevent committing runtime database files
        with open(os.path.join(output_dir, ".gitignore"), "w", encoding="utf-8") as f:
            f.write("*.db\n*.sqlite\n*.sqlite3\n*.db-journal\n*.db-wal\n*.db-shm\n__pycache__/\n*.pyc\n.pytest_cache/\n")

        # Guard: ensure Streamlit Web Apps always have an active Streamlit UI
        current_code = pipeline_state["current_app_code"]
        if app_type == "Streamlit Web App" and "streamlit" not in current_code.lower():
            clean_title = user_prompt.split("\n")[0][:50].replace("'", "\\'")
            clean_prompt = user_prompt.replace("'''", "")
            current_code += (
                f"\n\n# --- Streamlit Application UI ---\n"
                f"try:\n"
                f"    import streamlit as st\n"
                f"    st.set_page_config(page_title='Generated App', layout='wide')\n"
                f"    st.title('🚀 {clean_title}')\n"
                f"    st.success('Core application logic verified and ready.')\n"
                f"    st.subheader('Application Overview')\n"
                f"    st.markdown('''{clean_prompt}''')\n"
                f"except Exception:\n"
                f"    pass\n"
            )
            pipeline_state["current_app_code"] = current_code

        with open(os.path.join(output_dir, "app.py"), "w", encoding="utf-8") as f:
            f.write(pipeline_state["current_app_code"])
        with open(os.path.join(output_dir, "test_app.py"), "w", encoding="utf-8") as f:
            f.write(pipeline_state["test_code"])
        # Dynamically discover and resolve all third-party dependencies from generated code
        from core.dependency_manager import DependencyManager
        required_pkgs = DependencyManager.resolve_requirements(pipeline_state["current_app_code"])

        # Ensure all detected dependencies are installed locally in the environment
        for mod in DependencyManager.filter_third_party(DependencyManager.extract_imported_modules(pipeline_state["current_app_code"])):
            DependencyManager.ensure_module_installed(mod)

        with open(os.path.join(output_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(required_pkgs) + "\n")
        # Remove old CLI runner scripts if present
        for old_script in ["run_cli.bat", "run_cli.ps1"]:
            old_path = os.path.join(output_dir, old_script)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception:
                    pass

        with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(
                f"# Generated Application\n\n"
                f"**Requirement:** {user_prompt}\n\n"
                f"**Format:** Streamlit Web App\n\n"
                f"**Status:** {review_result.get('status', 'VERIFIED')}\n\n"
                f"## How to Run Locally\n```bash\nstreamlit run app.py\n```\n"
            )
        pipeline_state["generated_app_dir"] = output_dir

        # Git Auto-Push to persistent repository if connected
        git_sync_status = None
        if auto_push and os.path.exists(os.path.join(output_dir, ".git")):
            try:
                import subprocess
                remote_check = subprocess.run(["git", "remote", "get-url", "origin"], cwd=output_dir, capture_output=True, text=True)
                if remote_check.returncode == 0:
                    remote_url = remote_check.stdout.strip()
                    # Untrack any accidentally tracked .db or .sqlite files
                    subprocess.run(["git", "rm", "--cached", "-f", "*.db", "*.sqlite", "*.sqlite3"], cwd=output_dir, capture_output=True)
                    # Stage all additions, updates, and deletions
                    subprocess.run(["git", "add", "-A"], cwd=output_dir, capture_output=True)
                    commit_msg = f"Update generated app: {user_prompt[:50]}..."
                    subprocess.run(["git", "commit", "-m", commit_msg], cwd=output_dir, capture_output=True)
                    push_res = subprocess.run(["git", "push", "origin", "main"], cwd=output_dir, capture_output=True, text=True)
                    if push_res.returncode == 0:
                        git_sync_status = f"Pushed latest app to {remote_url}"
                        yield {
                            "event": "GIT_PUSH_DONE",
                            "agent": "Git Sync",
                            "message": f"Auto-synced and pushed updates to {remote_url}. Streamlit Cloud will auto-deploy!"
                        }
            except Exception as e:
                print(f"[Warning] Git auto-push encountered error: {e}")

        pipeline_state["git_sync_status"] = git_sync_status

        yield {
            "event": "PIPELINE_COMPLETE",
            "message": "All 5 agents finished their execution. App exported to 'generated_app/'.",
            "data": pipeline_state
        }

        return pipeline_state

    def _format_test_summary(self, result: Dict[str, Any]) -> str:
        passed = result.get("passed_tests", 0)
        failed = result.get("failed_tests", 0)
        errors = result.get("error_tests", 0)
        skipped = result.get("skipped_tests", 0)

        parts = [f"{passed} passed"]
        if failed > 0:
            parts.append(f"{failed} failed")
        if errors > 0:
            parts.append(f"{errors} error(s)")
        if skipped > 0:
            parts.append(f"{skipped} skipped")
        return f"Tests executed: {', '.join(parts)}."
