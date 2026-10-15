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
    """

    def __init__(self, timeout_seconds: int = 20, sandbox_base_dir: str = None):
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
            # Keep necessary PATH & System variables, but remove sensitive API keys
            restricted_env = os.environ.copy()
            for sensitive_key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SECRET_KEY"]:
                restricted_env.pop(sensitive_key, None)
            
            # Ensure Python can resolve modules in the sandbox directory
            restricted_env["PYTHONPATH"] = run_dir

            # 3. Execute pytest as a subprocess with a strict timeout
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

            # 4. Parse pytest output
            parsed = self._parse_pytest_output(all_output, exit_code)

            return {
                "success": exit_code == 0,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "full_output": all_output,
                "total_tests": parsed["total"],
                "passed_tests": parsed["passed"],
                "failed_tests": parsed["failed"],
                "error_tests": parsed["errors"],
                "failure_details": parsed["failure_details"],
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
                "failure_details": str(e),
                "run_dir": run_dir
            }
        finally:
            # We keep the directory for debugging or clean up if desired
            pass

    def cleanup_sandboxes(self):
        """Cleans up all temporary test execution sandboxes."""
        if os.path.exists(self.sandbox_base_dir):
            try:
                shutil.rmtree(self.sandbox_base_dir)
            except Exception:
                pass

    def _parse_pytest_output(self, output: str, exit_code: int) -> Dict[str, Any]:
        """Extracts passed, failed, errors count and detailed failure messages."""
        passed = 0
        failed = 0
        errors = 0

        # Look for pytest summary line like "1 passed, 1 failed in 0.05s"
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

        # Extract failure section (between FAILURES / ERRORS and summary)
        failure_details = ""
        fail_section = re.search(r"=+\s*(?:FAILURES|ERRORS)\s*=+(.*?)(?:=+\s*short test summary|\Z)", output, re.DOTALL)
        if fail_section:
            failure_details = fail_section.group(1).strip()
        elif exit_code != 0:
            failure_details = output

        total = passed + failed + errors
        if total == 0 and exit_code != 0:
            total = 1
            failed = 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "failure_details": failure_details
        }
