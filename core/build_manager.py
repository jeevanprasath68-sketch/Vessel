import threading
import time
from typing import Optional, Dict, Any, List
from core.llm_client import GeminiClient
from core.orchestrator import MultiAgentOrchestrator

class BuildManager:
    """
    Singleton Background Build Manager:
    Runs the multi-agent pipeline in a detached background thread so that
    switching between sidebar navigation menus (e.g. API Key Settings,
    GitHub Repository, App Builder) never interrupts or kills ongoing development.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.is_running: bool = False
        self.current_prompt: str = ""
        self.progress: int = 0
        self.status_message: str = "Idle"
        self.current_agent: str = "Idle"
        self.events: List[Dict[str, Any]] = []
        self.final_state: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.traceback: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def get_instance(cls) -> "BuildManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start_build(
        self,
        user_prompt: str,
        api_key: str,
        model: str,
        max_repairs: int = 3,
        timeout_sec: int = 20,
        app_type: str = "Streamlit Web App"
    ) -> bool:
        with self._lock:
            if self.is_running and self._thread and self._thread.is_alive():
                return False  # Already in progress

            self.is_running = True
            self.current_prompt = user_prompt
            self.progress = 5
            self.status_message = "Initializing multi-agent pipeline..."
            self.current_agent = "Orchestrator"
            self.events = []
            self.final_state = None
            self.error = None
            self.traceback = None

            self._thread = threading.Thread(
                target=self._worker,
                args=(user_prompt, api_key, model, max_repairs, timeout_sec, app_type),
                daemon=True
            )
            self._thread.start()
            return True

    def _worker(
        self,
        user_prompt: str,
        api_key: str,
        model: str,
        max_repairs: int,
        timeout_sec: int,
        app_type: str
    ):
        try:
            gemini_client = GeminiClient(
                api_key=api_key.strip(),
                model=model,
                mock_mode=False
            )
            orchestrator = MultiAgentOrchestrator(
                gemini_client=gemini_client,
                max_repairs=max_repairs,
                timeout_seconds=timeout_sec
            )

            for event in orchestrator.execute_stream(user_prompt, app_type=app_type, auto_push=True):
                event_type = event.get("event")
                agent = event.get("agent", "Orchestrator")
                message = event.get("message", "")

                with self._lock:
                    self.current_agent = agent
                    self.events.append({
                        "timestamp": time.strftime("%H:%M:%S"),
                        "event": event_type,
                        "agent": agent,
                        "message": message,
                        "data": event.get("data")
                    })

                    if event_type == "STAGE_START":
                        self.status_message = f"[{agent.upper()}] {message}"
                    elif event_type == "ARCHITECT_DONE":
                        self.progress = 30
                        self.status_message = "[ARCHITECT] Code & test suite generated."
                    elif event_type == "TEST_RUN_DONE":
                        self.progress = 55
                        success = event.get("success", False)
                        if success:
                            self.status_message = f"[TEST RUN] {event.get('message', 'Tests verified.')}"
                        else:
                            self.status_message = "[TEST RUN] Test failures detected. Handing to Repair Agent."
                    elif event_type == "REPAIR_DONE":
                        self.progress = 70
                        self.status_message = f"[REPAIR] {message}"
                    elif event_type == "REVIEW_DONE":
                        self.progress = 90
                        self.status_message = "[REVIEW] QA audit finalized."
                    elif event_type == "GIT_PUSH_DONE":
                        self.status_message = "[DEPLOY] Synced to remote GitHub repository."
                    elif event_type == "PIPELINE_COMPLETE":
                        self.progress = 100
                        self.status_message = "PIPELINE COMPLETE // APPLICATION DEPLOYED"
                        self.final_state = event.get("data")

        except Exception as e:
            import traceback
            with self._lock:
                self.error = str(e)
                self.traceback = traceback.format_exc()
                self.status_message = f"Execution failure: {e}"
        finally:
            with self._lock:
                self.is_running = False

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_running": self.is_running,
                "current_prompt": self.current_prompt,
                "progress": self.progress,
                "status_message": self.status_message,
                "current_agent": self.current_agent,
                "events": list(self.events),
                "final_state": self.final_state,
                "error": self.error,
                "traceback": self.traceback
            }

    def reset(self):
        with self._lock:
            if not self.is_running:
                self.events = []
                self.final_state = None
                self.error = None
                self.traceback = None
                self.progress = 0
                self.status_message = "Idle"
                self.current_agent = "Idle"

