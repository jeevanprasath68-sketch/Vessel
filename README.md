# 🤖 Autonomous Multi-AI Agent App Builder

A 5-agent autonomous engineering system powered by **Google Gemini** that generates, tests in a restricted sandbox, iteratively repairs, and reviews Python applications from natural language prompts.

---

## 🌟 The 5 Agents

| Agent | Role | Responsibility |
|---|---|---|
| **1. Architect + Developer** | Planner & Coder | Designs architecture, writes `app.py` and produces an exhaustive `pytest` suite in `test_app.py`. |
| **2. Testing Engine** | Sandboxed Execution | Executes real tests against generated code in an isolated directory with strict timeouts to prevent infinite loops. |
| **3. Repair Agent** | Automated Debugger | Uses real failure stack traces, exit codes, and assertion errors to diagnose and patch bugs iteratively. |
| **4. Reviewer Agent** | QA Lead & Auditor | Analyzes the final code, verifies test pass rates, generates an executive summary, and highlights technical debt. |
| **5. Streamlit Dashboard** | Orchestration & UI | Live interactive interface displaying agent statuses, real-time pytest terminal logs, code diffs, and zip export. |

---

## 🚀 Quickstart in VS Code

### 1. Prerequisites
- Python 3.10+
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey) *(optional: an offline simulation mode is also included)*

### 2. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Configure API Key
Create or update your `.env` file:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```
*(You can also enter your API key directly in the Streamlit UI sidebar).*

### 4. Launch Streamlit Dashboard
```powershell
.\.venv\Scripts\streamlit run streamlit_app.py
```

---

## 🧪 Key Features
- **Sandbox Security**: Strips sensitive environment variables and restricts execution to isolated temporary directories with configurable timeouts.
- **Unified Diff Viewer**: Visualizes exact code modifications made by the Repair Agent between iterations.
- **Offline Demo / Simulation Mode**: Allows instant testing of the entire 5-agent pipeline even without an API key or internet access.
- **One-Click Export**: Downloads the verified `app.py`, `test_app.py`, and `REVIEW_REPORT.md` bundled in a zip file.
