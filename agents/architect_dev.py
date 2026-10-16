from typing import Dict, Any, Optional
from core.llm_client import GeminiClient

ARCHITECT_DEV_PROMPT = """
You are a Principal Software Architect and Senior Python Developer specializing in Streamlit Web Applications.
Your job is to read the user's application requirement and produce a self-contained, high-quality, production-ready Streamlit web application in `app.py` along with an exhaustive pytest test suite in `test_app.py`.

Rules:
1. Write clean, idiomatic, typed Python 3 code in `app.py`.
2. Architecture requirements:
   - Implement clean, testable business logic classes and functions (e.g. data engines, models, solvers, validators, algorithms) at the top of `app.py`.
   - Build a comprehensive, beautiful Streamlit web interface in `app.py` using `import streamlit as st`:
     a. CRITICAL - NEVER PRODUCE A BLANK APP: The Streamlit UI code MUST EXECUTE whenever `streamlit run app.py` is invoked. Place UI calls at the module level or inside `def main():` / `def render_ui():`, and ALWAYS CALL IT AT THE VERY BOTTOM OF `app.py` (e.g. `if __name__ == '__main__': main()`).
     b. Include rich visual components: page title (`st.set_page_config`, `st.title`), form inputs (`st.form`, `st.text_input`, `st.selectbox`, `st.number_input`, `st.date_input`), action buttons (`st.button`), KPIs (`st.metric`), cards or tables (`st.dataframe`), search/filter tools, and status feedback (`st.success`, `st.error`).
     c. Ensure business logic functions and classes can be cleanly imported into `test_app.py` without executing the Streamlit browser runtime.
3. The test suite (`test_app.py`) must import and test the core logic functions/classes directly from `app` (e.g., `from app import DataEngine, Calculator, ...`) without needing the UI runner.
4. Database & Storage Resilience (CRITICAL):
   - If using SQLite or persistent databases:
     a. Never allow `sqlite3.OperationalError` due to missing columns or outdated tables. In `_init_db()`, inspect existing tables (using `PRAGMA table_info(table_name)`) and automatically add any missing columns via `ALTER TABLE ... ADD COLUMN` so upgrading an existing database file never crashes.
     b. Provide a "Reset Database / Clear All Data" control in the Streamlit UI (e.g. inside a sidebar expander) so users can wipe stale test data anytime with a single click.
     c. Wrap queries touching columns in defensive error handling and call `_init_db()` to self-heal schema if missing columns or tables are detected.
5. Games & Embedded HTML/JavaScript Safety (CRITICAL):
   - When embedding HTML, CSS, or JavaScript in Python (e.g. using `components.html(...)` or `st.components.v1.html` for games/canvas):
     a. NEVER use Python f-strings with unescaped JavaScript template literals (like `${var}` or `${obj.prop}`)! Python f-strings will try to evaluate `{var}` as Python variables, instantly crashing with `NameError: name '...' is not defined`.
     b. ALWAYS use standard JavaScript string concatenation (e.g. `"Score: " + score + " - Player: " + player.name`), OR use a standard string without `f` and use `.replace("__PARAM__", str(param))`.
6. Include at least 4-6 diverse unit tests covering:
   - Happy paths / basic functionality
   - Edge cases (bounds, invalid inputs, empty structures)
   - Error handling / expected exceptions (using `pytest.raises`)
7. You MUST return your response strictly as a JSON object with this exact structure:
{
  "architecture_summary": "Brief 2-3 sentence overview of the design patterns and components.",
  "app_code": "# full Python code for app.py",
  "test_code": "# full pytest code for test_app.py"
}
"""

class ArchitectDeveloperAgent:
    """Agent 1: Generates architecture, application code (app.py), and test suite (test_app.py)."""
    
    def __init__(self, client: GeminiClient):
        self.client = client

    def run(self, user_prompt: str, app_type: str = "Streamlit Web App") -> Dict[str, Any]:
        prompt = (
            f"User Requirement:\n\"\"\"{user_prompt}\"\"\"\n\n"
            "Generate the architecture plan, the complete Streamlit web application (`app.py`), and the pytest test suite (`test_app.py`)."
        )
        result = self.client.generate_json(prompt, system_instruction=ARCHITECT_DEV_PROMPT)
        
        raw_app = result.get("app_code")
        raw_test = result.get("test_code")
        if not raw_app or not raw_test:
            raise ValueError(f"ArchitectDeveloperAgent generated incomplete structure: {result}")
            
        return {
            "architecture_summary": str(result.get("architecture_summary") or "Python application and test suite generated."),
            "app_code": str(raw_app).strip(),
            "test_code": str(raw_test).strip()
        }
