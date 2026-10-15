import os
import io
import zipfile
import time
import streamlit as st
from dotenv import load_dotenv

from core.llm_client import GeminiClient
from core.orchestrator import MultiAgentOrchestrator

# Load local .env if present
load_dotenv()

st.set_page_config(
    page_title="Multi-AI Agent App Builder",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .agent-card {
        padding: 16px;
        border-radius: 10px;
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        margin-bottom: 12px;
    }
    .badge-success {
        background-color: #28a745;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-failure {
        background-color: #dc3545;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-warning {
        background-color: #ffc107;
        color: black;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .terminal-box {
        background-color: #1e1e1e;
        color: #d4d4d4;
        font-family: 'Consolas', 'Courier New', monospace;
        padding: 14px;
        border-radius: 8px;
        overflow-x: auto;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR CONFIG -----------------
with st.sidebar:
    st.title("⚙️ Agent Settings")
    
    env_key = os.getenv("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "Google Gemini API Key",
        value=env_key,
        type="password",
        help="Get your free key at https://aistudio.google.com/app/apikey"
    )

    # Dynamic Model Discovery Button
    col_detect, col_info = st.columns([1, 1])
    detected_models = st.session_state.get("detected_models", [])
    
    if st.button("🔍 Auto-Detect Models for Key", use_container_width=True):
        if not api_key_input:
            st.error("Please enter your API Key first to scan available models.")
        else:
            with st.spinner("Querying Google Gemini API for authorized models..."):
                found = GeminiClient.list_available_models(api_key_input)
                if found:
                    st.session_state["detected_models"] = found
                    detected_models = found
                    st.success(f"Found {len(found)} active model(s)!")
                else:
                    st.warning("No models found via ListModels. Make sure 'Generative Language API' is enabled on your key or try a direct key from Google AI Studio.")

    # Base list of contemporary Gemini models (latest alias models prioritized)
    standard_models = [
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-flash-lite-latest",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "Custom Model..."
    ]

    available_choices = detected_models if detected_models else standard_models
    if "Custom Model..." not in available_choices:
        available_choices.append("Custom Model...")

    model_choice = st.selectbox(
        "Gemini Model",
        options=available_choices,
        index=0,
        help="Google recommends 'gemini-flash-latest' as the primary high-speed model."
    )

    custom_model = ""
    if model_choice == "Custom Model...":
        custom_model = st.text_input("Enter exact model name (e.g. gemini-2.0-flash):")

    effective_model = custom_model.strip() if custom_model.strip() else model_choice

    max_repairs = st.slider("Max Repair Loops", min_value=1, max_value=5, value=3)
    timeout_sec = st.slider("Test Timeout (seconds)", min_value=5, max_value=40, value=20)
    
    mock_mode = st.checkbox(
        "🧪 Offline Demo / Simulation Mode",
        value=False if api_key_input else True,
        help="Simulate the 5-agent pipeline with an automatic bug-repair cycle without calling external APIs."
    )

    st.markdown("---")
    st.subheader("💡 Sample Prompts")
    
    sample_prompts = {
        "Banking Account Engine": "Build a BankAccount class with deposit, withdraw with an overdraft limit of $500, transfer to other accounts, and a full transaction ledger with timestamps.",
        "Markdown Table Parser": "Build a lightweight Markdown parser that converts Markdown tables and bold/italic text into clean semantic HTML5 strings.",
        "LRU Cache with TTL": "Create a thread-safe LRU Cache class with max size capacity and time-to-live (TTL) expiration per key.",
        "Key-Value Store with Transactions": "Create an in-memory Key-Value store that supports nested atomic transactions with BEGIN, COMMIT, and ROLLBACK operations."
    }

    for name, prompt_text in sample_prompts.items():
        if st.button(f"📌 {name}", use_container_width=True):
            st.session_state["prompt_input"] = prompt_text

    st.markdown("---")
    st.caption("5-Agent Autonomous App Builder • Powered by Google Gemini")

# ----------------- MAIN CONTENT -----------------
st.title("🤖 Autonomous Multi-AI Agent App Builder")
st.markdown("An autonomous 5-agent engineering team that plans, writes, tests in a sandbox, fixes errors, and reviews Python applications.")

# Visual 5-Agent Architecture Header
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.info("**1. Architect & Dev**\n\nPlans & writes `app.py` and `test_app.py`")
with col2:
    st.info("**2. Testing Engine**\n\nRuns isolated `pytest` in sandbox")
with col3:
    st.info("**3. Repair Agent**\n\nDiagnoses tracebacks & patches bugs")
with col4:
    st.info("**4. Reviewer Agent**\n\nAudits results & flags tech debt")
with col5:
    st.info("**5. Live Dashboard**\n\nReal-time monitoring & exports")

st.markdown("---")

# Prompt Input
default_prompt = st.session_state.get(
    "prompt_input",
    "Build a BankAccount system with deposit, withdraw with an overdraft limit, transfer to other accounts, and transaction history."
)

user_prompt = st.text_area(
    "Enter your application requirement:",
    value=default_prompt,
    height=110,
    help="Describe what you want the Python application to do."
)

start_button = st.button("🚀 Run 5-Agent Pipeline", type="primary", use_container_width=True)

# ----------------- EXECUTION LOGIC -----------------
if start_button:
    if not user_prompt.strip():
        st.error("Please provide an application prompt to begin.")
        st.stop()

    if not mock_mode and not api_key_input:
        st.warning("⚠️ No Gemini API Key provided. Switching automatically to Demo / Simulation Mode.")
        mock_mode = True

    # Initialize Client & Orchestrator
    gemini_client = GeminiClient(
        api_key=api_key_input,
        model=effective_model,
        mock_mode=mock_mode
    )
    orchestrator = MultiAgentOrchestrator(
        gemini_client=gemini_client,
        max_repairs=max_repairs,
        timeout_seconds=timeout_sec
    )

    st.subheader("⚡ Live Pipeline Execution")
    progress_bar = st.progress(5)
    status_box = st.empty()
    activity_log = st.container()

    final_state = None
    step_events = []

    try:
        for event in orchestrator.execute_stream(user_prompt):
            step_events.append(event)
            event_type = event.get("event")
            agent = event.get("agent", "Orchestrator")
            message = event.get("message", "")

            if event_type == "STAGE_START":
                status_box.markdown(f"**Current Agent:** `{agent}` — *{message}*")
                with activity_log:
                    st.write(f"🔄 **[{agent}]**: {message}")

            elif event_type == "ARCHITECT_DONE":
                progress_bar.progress(30)
                with activity_log:
                    st.success(f"✅ **[{agent}]**: Generated initial application code and test suite.")

            elif event_type == "TEST_RUN_DONE":
                progress_bar.progress(55)
                success = event.get("success", False)
                data = event.get("data", {})
                passed = data.get("passed_tests", 0)
                failed = data.get("failed_tests", 0)
                if success:
                    with activity_log:
                        st.success(f"✅ **[{agent}]**: All {passed} test(s) passed successfully!")
                else:
                    with activity_log:
                        st.warning(f"⚠️ **[{agent}]**: Tests failed ({passed} passed, {failed} failed). Handing off to Repair Agent.")

            elif event_type == "REPAIR_DONE":
                progress_bar.progress(70)
                with activity_log:
                    st.info(f"🔧 **[{agent}]**: {message}")

            elif event_type == "REVIEW_DONE":
                progress_bar.progress(90)
                with activity_log:
                    st.success(f"📋 **[{agent}]**: Executive review generated.")

            elif event_type == "PIPELINE_COMPLETE":
                progress_bar.progress(100)
                status_box.markdown("✨ **Multi-Agent Pipeline Finished Successfully!**")
                final_state = event.get("data")

    except Exception as e:
        st.error(f"Execution Error: {str(e)}")
        st.stop()

    if final_state:
        st.session_state["last_run_state"] = final_state

# ----------------- RESULTS TABS -----------------
if "last_run_state" in st.session_state:
    state = st.session_state["last_run_state"]
    review = state.get("review", {})
    latest_test = state.get("latest_test_result", {})
    repairs = state.get("repair_history", [])

    st.markdown("---")
    st.header("📊 Results & Artifacts")

    tab_review, tab_code, tab_tests, tab_repairs, tab_export = st.tabs([
        "📋 Reviewer Summary",
        "💻 Application Code (app.py)",
        "🧪 Test Suite & Engine Logs",
        f"🔧 Repair History ({len(repairs)})",
        "📦 Export Project"
    ])

    # TAB 1: Reviewer Summary
    with tab_review:
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        status_val = review.get("status", "VERIFIED")
        with col_stat1:
            st.metric("Status", status_val)
        with col_stat2:
            st.metric("Quality Score", review.get("overall_score", "N/A"))
        with col_stat3:
            st.metric("Tests Passed", f"{latest_test.get('passed_tests', 0)}/{latest_test.get('total_tests', 0)}")
        with col_stat4:
            st.metric("Repair Iterations", len(repairs))

        st.markdown("### Executive Summary")
        st.write(review.get("summary", "No summary provided."))

        st.markdown("### Key Findings")
        for finding in review.get("key_findings", []):
            st.markdown(f"- ✅ {finding}")

        unresolved = review.get("unresolved_problems", [])
        if unresolved:
            st.markdown("### ⚠️ Unresolved Problems")
            for prob in unresolved:
                st.markdown(f"- ❌ {prob}")
        else:
            st.success("No unresolved problems! All specifications verified.")

        st.markdown("### Technical Debt & Recommendations")
        for rec in review.get("technical_debt_and_recommendations", []):
            st.markdown(f"- 💡 {rec}")

    # TAB 2: Generated Code
    with tab_code:
        st.subheader("Architecture Plan")
        st.info(state.get("architecture_summary", "Python application."))
        st.subheader("Final Application Source (`app.py`)")
        st.code(state.get("current_app_code", ""), language="python", line_numbers=True)

    # TAB 3: Test Suite & Engine Logs
    with tab_tests:
        st.subheader("Pytest Test Suite (`test_app.py`)")
        st.code(state.get("test_code", ""), language="python", line_numbers=True)

        st.subheader("Restricted Sandbox Test Output")
        test_success = latest_test.get("success", False)
        if test_success:
            st.success(f"Exit Code: {latest_test.get('exit_code')} (SUCCESS)")
        else:
            st.error(f"Exit Code: {latest_test.get('exit_code')} (FAILURE)")

        st.markdown("**Real Pytest Terminal Stdout/Stderr:**")
        st.markdown(f"<div class='terminal-box'>{latest_test.get('full_output', 'No logs recorded.')}</div>", unsafe_allow_html=True)

    # TAB 4: Repair History
    with tab_repairs:
        if not repairs:
            st.success("✨ No repairs needed! The application passed all tests on the very first attempt.")
        else:
            for item in repairs:
                it = item.get("iteration", 1)
                with st.expander(f"Repair Cycle #{it}: {item.get('explanation')}", expanded=True):
                    st.markdown(f"**Diagnostic Explanation:** {item.get('explanation')}")
                    if item.get("diff"):
                        st.markdown("**Code Difference (Diff):**")
                        st.code(item.get("diff"), language="diff")
                    st.markdown("**Repaired app.py code:**")
                    st.code(item.get("app_code", ""), language="python")

    # TAB 5: Export Project
    with tab_export:
        st.subheader("Download Generated Application Package")
        st.markdown("Download all verified code, test suite, and the reviewer summary report as a clean zip file ready to run.")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("app.py", state.get("current_app_code", ""))
            zip_file.writestr("test_app.py", state.get("test_code", ""))
            
            review_md = f"""# Code Review & Verification Report
**Status:** {review.get('status', 'N/A')}
**Score:** {review.get('overall_score', 'N/A')}
**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
{review.get('summary', '')}

## Key Findings
""" + "\n".join([f"- {f}" for f in review.get('key_findings', [])]) + "\n\n## Recommendations\n" + "\n".join([f"- {r}" for r in review.get('technical_debt_and_recommendations', [])])

            zip_file.writestr("REVIEW_REPORT.md", review_md)
            zip_file.writestr("requirements.txt", "pytest>=8.0.0\n")

        zip_buffer.seek(0)
        st.download_button(
            label="📦 Download Complete Project (.zip)",
            data=zip_buffer,
            file_name="generated_ai_app.zip",
            mime="application/zip",
            type="primary"
        )
