import os
import json
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class GeminiClient:
    """
    Unified client for interacting with Google Gemini API with fallback support,
    automatic model resolution, and an offline mock simulation mode for quick local testing.
    """
    # Prioritized order of models that support generateContent
    DEFAULT_CANDIDATE_MODELS = [
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-flash-latest", mock_mode: bool = False):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.mock_mode = mock_mode or not bool(self.api_key)
        self._client = None
        self._legacy_genai = None

        if not self.mock_mode and self.api_key:
            self._init_gemini()

    def _init_gemini(self):
        """Attempts to initialize google.genai or fallback to google.generativeai."""
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        except Exception:
            try:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=self.api_key)
                self._legacy_genai = genai_legacy
            except Exception as e:
                print(f"[Warning] Could not initialize Gemini SDK ({e}). Falling back to mock mode.")
                self.mock_mode = True

    @classmethod
    def list_available_models(cls, api_key: str) -> List[str]:
        """
        Dynamically queries Google's API to fetch the list of models supported
        by this specific API key, sorted with proven active models first.
        """
        if not api_key:
            return []
        
        models_found = []

        # Attempt 1: Modern google.genai SDK
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            for m in client.models.list():
                actions = getattr(m, "supported_actions", None) or []
                name = m.name or ""
                clean_name = name.replace("models/", "")
                # Exclude TTS, preview-tts, embedding models
                if "tts" in clean_name.lower() or "embed" in clean_name.lower():
                    continue
                if "generateContent" in actions or not actions:
                    if clean_name and ("gemini" in clean_name.lower()):
                        models_found.append(clean_name)
        except Exception:
            pass

        # Attempt 2: Legacy google.generativeai SDK
        if not models_found:
            try:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=api_key)
                for m in genai_legacy.list_models():
                    methods = getattr(m, "supported_generation_methods", []) or []
                    if "generateContent" in methods:
                        clean_name = m.name.replace("models/", "")
                        if "tts" not in clean_name.lower() and "embed" not in clean_name.lower():
                            if "gemini" in clean_name.lower():
                                models_found.append(clean_name)
            except Exception:
                pass

        # Sort so that proven working aliases come first
        def model_priority(m_name: str) -> int:
            if m_name == "gemini-flash-latest":
                return 0
            if m_name == "gemini-pro-latest":
                return 1
            if "flash-latest" in m_name:
                return 2
            if "pro-latest" in m_name:
                return 3
            if "2.0-flash" in m_name:
                return 4
            return 10

        models_found.sort(key=model_priority)
        return models_found

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        """Generates text from Gemini with automatic retry across supported candidate models if 404 occurs."""
        if self.mock_mode or not self.api_key:
            return self._mock_response(prompt)

        # Candidates to try if requested model returns 404
        models_to_try = [self.model]
        for candidate in self.DEFAULT_CANDIDATE_MODELS:
            if candidate != self.model and candidate not in models_to_try:
                models_to_try.append(candidate)

        import time

        for attempt_model in models_to_try:
            # Try up to 2 times on the current model in case of a momentary spike
            for retry_attempt in range(2):
                try:
                    # 1. Try modern google.genai client
                    if self._client:
                        from google.genai import types
                        config_args = {}
                        if system_instruction:
                            config_args["system_instruction"] = system_instruction
                        if temperature is not None:
                            config_args["temperature"] = temperature

                        config = types.GenerateContentConfig(**config_args) if config_args else None
                        response = self._client.models.generate_content(
                            model=attempt_model,
                            contents=prompt,
                            config=config
                        )
                        # Succeeded! Update active model and return
                        self.model = attempt_model
                        return response.text or ""

                    # 2. Try legacy google.generativeai
                    elif self._legacy_genai:
                        model_instance = self._legacy_genai.GenerativeModel(
                            model_name=attempt_model,
                            system_instruction=system_instruction
                        )
                        response = model_instance.generate_content(
                            prompt,
                            generation_config={"temperature": temperature}
                        )
                        self.model = attempt_model
                        return response.text or ""

                except Exception as e:
                    err_str = str(e)
                    is_quota = any(code in err_str.lower() for code in ["429", "resource_exhausted", "quota"])
                    is_transient = any(code in err_str.lower() for code in ["503", "unavailable", "high demand", "overloaded", "deadline_exceeded"])
                    is_not_found = any(code in err_str.lower() for code in ["404", "not_found", "not found", "no longer available"])

                    if is_quota or is_not_found:
                        # Daily quota exhausted or model deprecated: switch immediately to next candidate model without wasting time
                        break
                    elif is_transient:
                        if retry_attempt == 0:
                            time.sleep(1.0)
                            continue
                        else:
                            break
                    else:
                        # Unrecoverable error (e.g. invalid credentials)
                        raise RuntimeError(f"Gemini API request failed: {err_str}")

        # If all candidates returned 404 or 503:
        raise RuntimeError(
            f"Google Gemini servers are temporarily experiencing high demand across all tested models.\n"
            f"Please wait 30 seconds and retry, or toggle '🧪 Offline Demo / Simulation Mode' in the sidebar to proceed immediately."
        )

    def generate_json(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """Requests generation and safely parses output as JSON."""
        full_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Your response MUST be valid, raw JSON ONLY. "
            "Do not wrap in markdown tags like ```json unless standard. "
            "Ensure all strings and quotes are properly escaped."
        )
        raw_text = self.generate_text(full_prompt, system_instruction=system_instruction, temperature=0.1)
        return self._extract_json(raw_text)

    def _extract_json(self, text: Optional[str]) -> Dict[str, Any]:
        """Robustly extracts JSON from an LLM response string."""
        if not text:
            return {"error": "Empty response from model"}
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            return {"raw_output": text, "error": "Failed to parse JSON"}

    def _mock_response(self, prompt: str) -> str:
        """Simulated agent responses for immediate offline demonstration."""
        prompt_lower = prompt.lower()
        mock_ui_snippet = (
            "\n\n# --- Streamlit Interactive User Interface ---\n"
            "try:\n"
            "    import streamlit as st\n"
            "    HAS_STREAMLIT = True\n"
            "except ImportError:\n"
            "    HAS_STREAMLIT = False\n\n"
            "def render_ui():\n"
            "    if not HAS_STREAMLIT:\n"
            "        return\n"
            "    st.set_page_config(page_title='Task Manager', page_icon='📋', layout='wide')\n"
            "    st.title('📋 Prioritized Task Manager')\n"
            "    st.caption('Organize and prioritize your daily tasks with status tracking.')\n\n"
            "    if 'task_manager' not in st.session_state:\n"
            "        st.session_state.task_manager = TaskManager()\n"
            "        st.session_state.task_manager.add_task('Initial project setup', priority=3)\n"
            "        st.session_state.task_manager.add_task('Review pull request', priority=5)\n\n"
            "    tm = st.session_state.task_manager\n\n"
            "    with st.sidebar:\n"
            "        st.header('➕ Add New Task')\n"
            "        with st.form('new_task_form', clear_on_submit=True):\n"
            "            new_title = st.text_input('Task Title', placeholder='e.g., Fix database indexing')\n"
            "            new_priority = st.slider('Priority Level', min_value=1, max_value=5, value=3, help='5 = Highest, 1 = Lowest')\n"
            "            submitted = st.form_submit_button('Add Task', use_container_width=True)\n"
            "            if submitted and new_title.strip():\n"
            "                tm.add_task(new_title.strip(), new_priority)\n"
            "                st.success('Task added successfully!')\n"
            "                st.rerun()\n\n"
            "    total = len(tm.tasks)\n"
            "    pending_tasks = tm.get_pending_tasks()\n"
            "    completed_count = total - len(pending_tasks)\n\n"
            "    m1, m2, m3 = st.columns(3)\n"
            "    m1.metric('Total Tasks', total)\n"
            "    m2.metric('Pending Tasks', len(pending_tasks))\n"
            "    m3.metric('Completed Tasks', completed_count)\n\n"
            "    st.subheader('📌 Pending Tasks (Prioritized)')\n"
            "    if not pending_tasks:\n"
            "        st.info('No pending tasks! All caught up 🎉')\n"
            "    else:\n"
            "        for t in pending_tasks:\n"
            "            c1, c2 = st.columns([5, 1])\n"
            "            with c1:\n"
            "                st.markdown(f'**#{t.task_id}**: {t.title} &nbsp;*(Priority: {t.priority}/5)*')\n"
            "            with c2:\n"
            "                if st.button('Mark Complete', key=f'complete_{t.task_id}'):\n"
            "                    tm.complete_task(t.task_id)\n"
            "                    st.rerun()\n\n"
            "if __name__ == '__main__':\n"
            "    render_ui()\n"
        )

        if "architect" in prompt_lower or "developer" in prompt_lower:
            return json.dumps({
                "architecture_summary": "Simulated In-Memory Task Manager with prioritization, Streamlit web UI, and status filtering.",
                "app_code": (
                    "class Task:\n"
                    "    def __init__(self, task_id: int, title: str, priority: int = 1):\n"
                    "        self.task_id = task_id\n"
                    "        self.title = title\n"
                    "        self.priority = priority\n"
                    "        self.completed = False\n\n"
                    "class TaskManager:\n"
                    "    def __init__(self):\n"
                    "        self.tasks = {}\n\n"
                    "    def add_task(self, title: str, priority: int = 1) -> Task:\n"
                    "        task_id = len(self.tasks) + 1\n"
                    "        task = Task(task_id, title, priority)\n"
                    "        self.tasks[task_id] = task\n"
                    "        return task\n\n"
                    "    def complete_task(self, task_id: int) -> bool:\n"
                    "        if task_id in self.tasks:\n"
                    "            self.tasks[task_id].completed = True\n"
                    "            return True\n"
                    "        return False\n\n"
                    "    def get_pending_tasks(self):\n"
                    "        # Intentional minor bug on first pass to trigger Repair Agent: returns wrong order\n"
                    "        pending = [t for t in self.tasks.values() if not t.completed]\n"
                    "        return sorted(pending, key=lambda x: x.priority, reverse=False)\n"
                    + mock_ui_snippet
                ),
                "test_code": (
                    "import pytest\n"
                    "from app import TaskManager\n\n"
                    "def test_add_task():\n"
                    "    tm = TaskManager()\n"
                    "    task = tm.add_task('Write tests', priority=2)\n"
                    "    assert task.task_id == 1\n"
                    "    assert task.title == 'Write tests'\n"
                    "    assert not task.completed\n\n"
                    "def test_complete_task():\n"
                    "    tm = TaskManager()\n"
                    "    task = tm.add_task('Fix bug')\n"
                    "    assert tm.complete_task(task.task_id) is True\n"
                    "    assert tm.complete_task(999) is False\n\n"
                    "def test_pending_tasks_priority():\n"
                    "    tm = TaskManager()\n"
                    "    tm.add_task('Low', priority=1)\n"
                    "    tm.add_task('High', priority=5)\n"
                    "    tm.add_task('Medium', priority=3)\n"
                    "    pending = tm.get_pending_tasks()\n"
                    "    # Test expects highest priority first (5, 3, 1)\n"
                    "    priorities = [t.priority for t in pending]\n"
                    "    assert priorities == [5, 3, 1]\n"
                )
            })
        elif "repair" in prompt_lower:
            return json.dumps({
                "explanation": "Fixed sorting order in get_pending_tasks to sort by priority descending (reverse=True).",
                "app_code": (
                    "class Task:\n"
                    "    def __init__(self, task_id: int, title: str, priority: int = 1):\n"
                    "        self.task_id = task_id\n"
                    "        self.title = title\n"
                    "        self.priority = priority\n"
                    "        self.completed = False\n\n"
                    "class TaskManager:\n"
                    "    def __init__(self):\n"
                    "        self.tasks = {}\n\n"
                    "    def add_task(self, title: str, priority: int = 1) -> Task:\n"
                    "        task_id = len(self.tasks) + 1\n"
                    "        task = Task(task_id, title, priority)\n"
                    "        self.tasks[task_id] = task\n"
                    "        return task\n\n"
                    "    def complete_task(self, task_id: int) -> bool:\n"
                    "        if task_id in self.tasks:\n"
                    "            self.tasks[task_id].completed = True\n"
                    "            return True\n"
                    "        return False\n\n"
                    "    def get_pending_tasks(self):\n"
                    "        # Fixed: now correctly sorts highest priority first\n"
                    "        pending = [t for t in self.tasks.values() if not t.completed]\n"
                    "        return sorted(pending, key=lambda x: x.priority, reverse=True)\n"
                    + mock_ui_snippet
                )
            })
        elif "review" in prompt_lower:
            return json.dumps({
                "status": "VERIFIED",
                "overall_score": "9.5/10",
                "summary": "The application meets all user requirements and all unit tests pass with 100% success rate after 1 automated repair cycle.",
                "key_findings": [
                    "Clean object-oriented design with Task and TaskManager classes.",
                    "Automated repair successfully resolved priority sorting discrepancy.",
                    "Isolated testing environment validated all core functional paths."
                ],
                "unresolved_problems": [],
                "technical_debt_and_recommendations": [
                    "Add persistent storage (SQLite or JSON file) for real-world usage.",
                    "Add concurrency locks if accessed in multi-threaded contexts."
                ]
            })
        return "Simulated Gemini Response."
