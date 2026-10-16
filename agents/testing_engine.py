import os
import sys
import re
import shutil
import tempfile
import subprocess
from typing import Dict, Any

class TestingEngine:
    """
    Agent 2: Executes real pytest tests against generated code in an isolated,
    timeout-restricted sandbox environment, parsing failures and tracebacks.
    Also handles self-healing auto-installation for missing third-party dependencies.
    """

    def __init__(self, timeout_seconds: int = 25, sandbox_base_dir: str = None):
        self.timeout_seconds = timeout_seconds
        self.sandbox_base_dir = sandbox_base_dir or os.path.join(os.getcwd(), ".sandbox")
        os.makedirs(self.sandbox_base_dir, exist_ok=True)

    def run_tests(self, app_code: str, test_code: str) -> Dict[str, Any]:
        """
        Executes pytest inside an isolated sandbox directory.
        Returns detailed execution metrics, outputs, and failure traces.
        """
        run_dir = tempfile.mkdtemp(prefix="run_", dir=self.sandbox_base_dir)
        try:
            # 1. Write the target files into the sandbox directory
            app_file = os.path.join(run_dir, "app.py")
            test_file = os.path.join(run_dir, "test_app.py")

            with open(app_file, "w", encoding="utf-8") as f:
                f.write(app_code)
            
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_code)

            # 2. Build a restricted environment
            restricted_env = os.environ.copy()
            for sensitive_key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SECRET_KEY"]:
                restricted_env.pop(sensitive_key, None)
            
            restricted_env["PYTHONPATH"] = run_dir

            # Ensure any required third-party dependencies are installed
            try:
                from core.dependency_manager import DependencyManager
                all_code = f"{app_code}\n{test_code}"
                for mod in DependencyManager.filter_third_party(DependencyManager.extract_imported_modules(all_code)):
                    DependencyManager.ensure_module_installed(mod)
            except Exception as e:
                print(f"[TestingEngine] Dependency pre-check notice: {e}")

            # 3. Execute pytest
            cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short", "test_app.py"]

            process = subprocess.run(
                cmd,
                cwd=run_dir,
                env=restricted_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds
            )

            stdout = process.stdout
            stderr = process.stderr
            exit_code = process.returncode
            all_output = f"{stdout}\n{stderr}".strip()

            # 4. Check for missing module and attempt self-healing installation
            missing_module_match = re.search(r"No module named ['\"]?([a-zA-Z0-9_\-]+)['\"]?", all_output)
            if missing_module_match and exit_code != 0:
                missing_pkg = missing_module_match.group(1).lower()
                # Don't try to pip install local 'app' or standard library
                if missing_pkg not in ["app", "test_app", "builtins", "math", "os", "sys"]:
                    try:
                        print(f"[TestingEngine] Detected missing dependency: '{missing_pkg}'. Attempting auto-installation...")
                        subprocess.run([sys.executable, "-m", "pip", "install", missing_pkg], timeout=45, capture_output=True)
                        # Re-run pytest after installation
                        process = subprocess.run(
                            cmd,
                            cwd=run_dir,
                            env=restricted_env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            timeout=self.timeout_seconds
                        )
                        stdout = process.stdout
                        stderr = process.stderr
                        exit_code = process.returncode
                        all_output = f"{stdout}\n{stderr}".strip()
                    except Exception as e:
                        print(f"[TestingEngine] Auto-install failed: {e}")

            # 5. Parse pytest output
            parsed = self._parse_pytest_output(all_output, exit_code)

            # A test run is ONLY successful if exit_code == 0 AND at least 1 test actually passed!
            is_truly_successful = (exit_code == 0) and (parsed["passed"] > 0) and (parsed["failed"] == 0)

            failure_details = parsed["failure_details"]
            if not is_truly_successful and not failure_details:
                if parsed.get("skipped", 0) > 0 and parsed["passed"] == 0:
                    failure_details = f"All {parsed['skipped']} test(s) were skipped! Code functionality could not be verified."
                elif parsed["total"] == 0:
                    failure_details = "Zero tests were discovered. Ensure unit test functions are prefixed with 'test_'."

            # 6. Streamlit UI Launch Smoke Test
            # Pytest tests the backend logic, but often does NOT execute main() or UI render blocks.
            # If unit tests pass and this is a Streamlit app, run a headless AppTest smoke test to verify
            # that main() and all UI render components execute without NameError, AttributeError, or syntax errors.
            if is_truly_successful and ("streamlit" in app_code.lower()):
                try:
                    smoke_runner_code = (
                        "import sys\n"
                        "from streamlit.testing.v1 import AppTest\n"
                        "try:\n"
                        "    at = AppTest.from_file('app.py')\n"
                        "    at.run(timeout=10)\n"
                        "    if at.exception:\n"
                        "        for exc in at.exception:\n"
                        "            val = getattr(exc, 'value', str(exc))\n"
                        "            st_lines = getattr(exc, 'stack_trace', [])\n"
                        "            st_str = ''.join(st_lines) if isinstance(st_lines, list) else str(st_lines)\n"
                        "            print(f'STREAMLIT_UI_CRASH: {val}\\n{st_str}')\n"
                        "        sys.exit(1)\n"
                        "except Exception as e:\n"
                        "    print(f'STREAMLIT_UI_CRASH: {e}')\n"
                        "    sys.exit(1)\n"
                    )
                    smoke_file = os.path.join(run_dir, "_smoke_test_runner.py")
                    with open(smoke_file, "w", encoding="utf-8") as sf:
                        sf.write(smoke_runner_code)

                    smoke_res = subprocess.run(
                        [sys.executable, "_smoke_test_runner.py"],
                        cwd=run_dir,
                        env=restricted_env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=15
                    )
                    if smoke_res.returncode != 0 or "STREAMLIT_UI_CRASH:" in smoke_res.stdout:
                        is_truly_successful = False
                        exit_code = smoke_res.returncode if smoke_res.returncode != 0 else 1
                        crash_info = (smoke_res.stdout + "\n" + smoke_res.stderr).strip()
                        failure_details = (
                            "Streamlit UI Launch Smoke Test Failed!\n"
                            "Unit tests passed, but the application crashed upon UI launch/rendering with the following runtime error:\n"
                            + crash_info + "\n\n"
                            "CRITICAL FIX INSTRUCTIONS:\n"
                            "1. If this is a NameError inside an HTML5/JavaScript component block (components.html / iframe), "
                            "you likely used a Python f-string with JS template literals `${var}`. Python evaluated `{var}` as Python code!\n"
                            "DO NOT use Python f-strings for JavaScript code containing `${...}`. Use standard strings with concatenation or escape as `${{...}}`.\n"
                            "2. Ensure all UI widgets, helper functions, and database calls inside main() are properly defined and initialized."
                        )
                        all_output += f"\n\n--- STREAMLIT UI SMOKE TEST FAILED ---\n{crash_info}"
                except subprocess.TimeoutExpired:
                    is_truly_successful = False
                    exit_code = 1
                    failure_details = "Streamlit UI Launch Smoke Test timed out after 15s. Check for infinite loops or blocking operations in UI initialization."
                    all_output += "\n\n--- STREAMLIT UI SMOKE TEST TIMED OUT ---"
                except Exception as e:
                    print(f"[TestingEngine] AppTest smoke test notice: {e}")

            return {
                "success": is_truly_successful,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "full_output": all_output,
                "total_tests": parsed["total"],
                "passed_tests": parsed["passed"],
                "failed_tests": parsed["failed"],
                "error_tests": parsed["errors"],
                "skipped_tests": parsed.get("skipped", 0),
                "failure_details": failure_details,
                "run_dir": run_dir
            }

        except subprocess.TimeoutExpired as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": e.stdout.decode() if isinstance(e.stdout, bytes) else str(e.stdout or ""),
                "stderr": f"Execution Timed Out after {self.timeout_seconds} seconds.",
                "full_output": f"ERROR: Subprocess timed out after {self.timeout_seconds}s.",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1,
                "error_tests": 1,
                "skipped_tests": 0,
                "failure_details": f"Subprocess timed out after {self.timeout_seconds}s (possible infinite loop or blocking I/O).",
                "run_dir": run_dir
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": str(e),
                "full_output": f"Execution Error: {str(e)}",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1,
                "error_tests": 1,
                "skipped_tests": 0,
                "failure_details": str(e),
                "run_dir": run_dir
            }

    def cleanup_sandboxes(self):
        """Cleans up all temporary test execution sandboxes."""
        if os.path.exists(self.sandbox_base_dir):
            try:
                shutil.rmtree(self.sandbox_base_dir)
            except Exception:
                pass

    def _parse_pytest_output(self, output: str, exit_code: int) -> Dict[str, Any]:
        """Extracts passed, failed, errors count, skipped count, and detailed failure messages."""
        passed = 0
        failed = 0
        errors = 0
        skipped = 0

        # Look for pytest summary line like "1 passed, 1 failed, 2 skipped in 0.05s"
        summary_match = re.search(r"=+\s*(.*?)\s*in\s*[\d\.]+s\s*=+", output)
        if summary_match:
            summary_str = summary_match.group(1)
            passed_m = re.search(r"(\d+)\s+passed", summary_str)
            if passed_m:
                passed = int(passed_m.group(1))
            failed_m = re.search(r"(\d+)\s+failed", summary_str)
            if failed_m:
                failed = int(failed_m.group(1))
            errors_m = re.search(r"(\d+)\s+error", summary_str)
            if errors_m:
                errors = int(errors_m.group(1))
            skipped_m = re.search(r"(\d+)\s+skipped", summary_str)
            if skipped_m:
                skipped = int(skipped_m.group(1))

        # Extract failure section (between FAILURES / ERRORS and summary)
        failure_details = ""
        fail_section = re.search(r"=+\s*(?:FAILURES|ERRORS)\s*=+(.*?)(?:=+\s*short test summary|\Z)", output, re.DOTALL)
        if fail_section:
            failure_details = fail_section.group(1).strip()
        elif exit_code != 0:
            failure_details = output

        total = passed + failed + errors
        if total == 0 and exit_code != 0 and skipped == 0:
            total = 1
            failed = 1
        elif total == 0 and skipped > 0:
            total = skipped

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "failure_details": failure_details
        }
