import os
import io
import zipfile
import time
import subprocess
import streamlit as st
from dotenv import load_dotenv

from core.llm_client import GeminiClient
from core.orchestrator import MultiAgentOrchestrator
from core.build_manager import BuildManager

# Load local .env
load_dotenv()

st.set_page_config(
    page_title="Vessel // Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- MONOCHROME BLACK & WHITE CSS (Cepter EFX style) -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Deep Dark Background */
    html, body, [class*="css"], .stApp {
        background-color: #0b0b0b !important;
        color: #ededed !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        -webkit-font-smoothing: antialiased !important;
    }

    /* Sidebar Monochrome Styling */
    section[data-testid="stSidebar"] {
        background-color: #080808 !important;
        border-right: 1px solid #1a1a1a !important;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
    h1 {
        font-size: 24px !important;
        font-weight: 700 !important;
        margin: 0 0 2px 0 !important;
        line-height: 1.2 !important;
    }
    h2, h3 {
        font-size: 18px !important;
        margin: 0 0 4px 0 !important;
    }
    h4, h5 {
        font-size: 13.5px !important;
        margin: 0 0 4px 0 !important;
    }

    /* Main Viewport Container: Compact padding to eliminate scrolling */
    .block-container, div[data-testid="stMainBlockContainer"] {
        padding-top: 1.25rem !important;
        padding-bottom: 0.75rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }

    /* Technical Kicker / Subtitle */
    .mono-kicker {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10.5px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        color: #71717a !important;
        margin-bottom: 4px !important;
    }

    /* Minimalist Cards */
    .mono-card {
        background: #111111;
        border: 1px solid #1f1f1f;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 8px;
    }

    /* Monochromatic Status Pill */
    .mono-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #141414;
        color: #ededed;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 500;
        padding: 4px 10px;
        border-radius: 4px;
        border: 1px solid #262626;
    }
    .mono-pill.active {
        background: #ffffff;
        color: #0b0b0b;
        font-weight: 700;
        border-color: #ffffff;
    }

    /* Buttons: Strict Black & White */
    .stButton > button, button[kind="primary"], button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #0b0b0b !important;
        border: 1px solid #ffffff !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        letter-spacing: -0.01em !important;
        padding: 8px 16px !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background-color: #e5e5e5 !important;
        border-color: #e5e5e5 !important;
        color: #000000 !important;
        transform: translateY(-1px) !important;
    }
    
    /* Secondary / Normal Buttons (Ghost outline) */
    div:not([data-testid="stForm"]) > div > .stButton > button[kind="secondary"],
    .stButton > button:not([kind="primary"]) {
        background-color: #121212 !important;
        color: #ffffff !important;
        border: 1px solid #262626 !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background-color: #1a1a1a !important;
        border-color: #404040 !important;
        color: #ffffff !important;
    }

    /* Link Buttons */
    a[data-testid="stLinkButton"] {
        background-color: #121212 !important;
        color: #ffffff !important;
        border: 1px solid #262626 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        transition: all 0.15s ease !important;
    }
    a[data-testid="stLinkButton"]:hover {
        background-color: #1a1a1a !important;
        border-color: #404040 !important;
        color: #ffffff !important;
    }

    /* Form Inputs */
    input, textarea, [data-baseweb="select"] > div {
        background-color: #0e0e0e !important;
        border: 1px solid #222222 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-size: 13px !important;
    }
    input:focus, textarea:focus, [data-baseweb="select"] > div:focus-within {
        border-color: #ffffff !important;
        box-shadow: none !important;
    }

    /* Streamlit Containers with border=True */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #111111 !important;
        border: 1px solid #1f1f1f !important;
        border-radius: 8px !important;
    }

    /* Code blocks */
    div[data-testid="stCode"] {
        background-color: #080808 !important;
        border: 1px solid #1c1c1c !important;
        border-radius: 6px !important;
    }
    pre {
        background-color: #080808 !important;
    }

    /* Terminal Console */
    .terminal-box {
        background-color: #070707;
        color: #f4f4f5;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12.5px;
        padding: 16px;
        border-radius: 6px;
        overflow-x: auto;
        white-space: pre-wrap;
        line-height: 1.5;
        border: 1px solid #1f1f1f;
    }

    /* Metrics: Pure Black & White */
    div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700 !important;
        color: #ffffff !important;
        font-family: 'Inter', sans-serif !important;
        letter-spacing: -0.03em !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 11px !important;
        font-weight: 600 !important;
        color: #71717a !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }

    /* Tabs: Monochromatic Minimalist */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #71717a !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border: none !important;
        padding: 10px 16px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff !important;
        border-bottom: 2px solid #ffffff !important;
        font-weight: 600 !important;
    }

    /* Sidebar Navigation Menu - Buttonless Clickable Items */
    div[data-testid="stRadio"] {
        width: 100% !important;
    }

    /* Completely hide the widget label if present */
    div[data-testid="stRadio"] > div:first-child:not([data-testid="stRadioGroup"]),
    div[data-testid="stRadio"] [data-testid="stWidgetLabel"] {
        display: none !important;
    }

    /* Radio Group options vertical stack */
    div[data-testid="stRadioGroup"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 4px !important;
        width: 100% !important;
    }

    /* Each option row item */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"],
    div[data-testid="stRadio"] label[data-testid="stRadioOption"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        width: 100% !important;
        min-height: 40px !important;
        padding: 8px 14px !important;
        margin: 0 !important;
        border-radius: 6px !important;
        cursor: pointer !important;
        border: 1px solid transparent !important;
        background-color: transparent !important;
        box-sizing: border-box !important;
        transition: background-color 0.15s ease, border-color 0.15s ease !important;
    }

    /* Inner wrapper inside option */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"] > div {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        width: 100% !important;
        gap: 0 !important;
    }

    /* Completely hide circular radio dot indicator */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div > div:first-child,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"] > div > div:first-child,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"] svg {
        display: none !important;
    }

    /* Text container - Strictly horizontal on one line */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"],
    div[data-testid="stRadio"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        white-space: nowrap !important;
    }

    /* Text element styling */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {
        color: #a1a1aa !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
        line-height: 1.4 !important;
        user-select: none !important;
        transition: color 0.15s ease !important;
    }

    /* Hover highlight for unselected menu item */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:hover:not([data-selected]):not(:has(input:checked)),
    div[data-testid="stRadio"] label[data-testid="stRadioOption"]:hover:not([data-selected]):not(:has(input:checked)) {
        background-color: #18181b !important;
        border-color: #27272a !important;
    }
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:hover:not([data-selected]):not(:has(input:checked)) p,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"]:hover:not([data-selected]):not(:has(input:checked)) p {
        color: #ffffff !important;
    }

    /* Active / Selected state - High contrast white pill with bold black text */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected],
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:has(input:checked),
    div[data-testid="stRadioGroup"] [data-selected] label[data-testid="stRadioOption"],
    div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected],
    div[data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked) {
        background-color: #ffffff !important;
        border-color: #ffffff !important;
    }
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected] p,
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:has(input:checked) p,
    div[data-testid="stRadioGroup"] [data-selected] label[data-testid="stRadioOption"] p,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected] p,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked) p {
        color: #09090b !important;
        font-weight: 600 !important;
    }

    /* Hover on Active / Selected item stays white/off-white */
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected]:hover,
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:has(input:checked):hover,
    div[data-testid="stRadioGroup"] [data-selected] label[data-testid="stRadioOption"]:hover,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected]:hover,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked):hover {
        background-color: #f4f4f5 !important;
        border-color: #f4f4f5 !important;
    }
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected]:hover p,
    div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:has(input:checked):hover p,
    div[data-testid="stRadioGroup"] [data-selected] label[data-testid="stRadioOption"]:hover p,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected]:hover p,
    div[data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked):hover p {
        color: #000000 !important;
    }

    /* Remove standard alert colors (make all alerts clean monochrome dark cards) */
    div[data-testid="stAlert"] {
        background-color: #121212 !important;
        color: #ededed !important;
        border: 1px solid #262626 !important;
        border-radius: 6px !important;
    }
    div[data-testid="stAlert"] svg {
        fill: #ffffff !important;
    }

    /* Progress Bar */
    div[data-testid="stProgress"] > div {
        background-color: #1a1a1a !important;
        border-radius: 4px !important;
        height: 6px !important;
    }
    div[data-testid="stProgress"] > div > div > div > div {
        background-color: #ffffff !important;
        border-radius: 4px !important;
    }

    /* Dividers */
    hr {
        border-color: #1a1a1a !important;
    }

    /* Transparent Streamlit Header with Always-Accessible Sidebar Control */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2.5rem !important;
        z-index: 99999 !important;
    }

    /* Keep Sidebar Toggle Button visible, prominent & styled in monochrome */
    button[data-testid="stExpandSidebarButton"],
    button[data-testid="stSidebarCollapseButton"] {
        visibility: visible !important;
        display: flex !important;
        opacity: 1 !important;
        background: #141414 !important;
        color: #ffffff !important;
        border: 1px solid #262626 !important;
        border-radius: 6px !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        z-index: 999999 !important;
    }
    button[data-testid="stExpandSidebarButton"]:hover,
    button[data-testid="stSidebarCollapseButton"]:hover {
        background: #222222 !important;
        border-color: #404040 !important;
        color: #ffffff !important;
    }
    button[data-testid="stExpandSidebarButton"] svg,
    button[data-testid="stSidebarCollapseButton"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }

    /* Hide standard Streamlit header clutter (Deploy button, MainMenu) */
    header[data-testid="stHeader"] [data-testid="stToolbarActions"],
    header[data-testid="stHeader"] [data-testid="stMainMenu"],
    header[data-testid="stHeader"] [data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- CONFIG & REPOSITORY STATE -----------------
from dotenv import load_dotenv
load_dotenv()

DEFAULT_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_REPO_URL = "https://github.com/jeevanprasath68-sketch/generated.git"
output_dir = os.path.join(os.getcwd(), "generated_app")
os.makedirs(output_dir, exist_ok=True)

if "active_api_key" not in st.session_state:
    st.session_state["active_api_key"] = DEFAULT_API_KEY

effective_api_key = st.session_state["active_api_key"]

current_remote = ""
try:
    chk = subprocess.run(["git", "remote", "get-url", "origin"], cwd=output_dir, capture_output=True, text=True)
    if chk.returncode == 0 and chk.stdout.strip():
        current_remote = chk.stdout.strip()
except Exception:
    pass

if not current_remote:
    current_remote = DEFAULT_REPO_URL
    try:
        if not os.path.exists(os.path.join(output_dir, ".git")):
            subprocess.run(["git", "init"], cwd=output_dir, capture_output=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=output_dir, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", DEFAULT_REPO_URL], cwd=output_dir, capture_output=True)
    except Exception:
        pass

connected_remote = current_remote

if "selected_model" not in st.session_state or st.session_state["selected_model"] == "gemini-flash-latest":
    st.session_state["selected_model"] = "gemini-flash-lite-latest"

effective_model = st.session_state["selected_model"]
app_type = "Streamlit Web App"

# Global build manager instance
build_mgr = BuildManager.get_instance()
build_snapshot = build_mgr.get_snapshot()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown("<div class='mono-kicker'>VESSEL // STUDIO</div>", unsafe_allow_html=True)
    st.markdown("### Navigation")
    
    menu = st.radio(
        "Navigation Menu",
        [
            "App Builder",
            "API Key Settings",
            "GitHub Repository"
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown("<div class='mono-kicker'>ENVIRONMENT STATUS</div>", unsafe_allow_html=True)
    key_tag = "ACTIVE" if effective_api_key else "NONE"
    repo_slug = connected_remote.split('/')[-1].replace('.git', '') if connected_remote else 'NONE'
    
    if build_snapshot["is_running"]:
        build_tag = f"RUNNING ({build_snapshot['progress']}%)"
        build_style = "color: #0b0b0b; background: #ffffff; font-weight: 800; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 2px 8px; border-radius: 4px;"
    else:
        build_tag = "READY"
        build_style = "color: #a1a1aa; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-size: 11.5px; background: #18181b; padding: 2px 8px; border-radius: 4px; border: 1px solid #27272a;"

    st.markdown(
        f"""
        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px; font-size: 13px;">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                <span style="color: #a1a1aa;"><b>BUILD ENGINE</b></span>
                <span style="{build_style}"><b>{build_tag}</b></span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                <span style="color: #a1a1aa;"><b>KEY STATUS</b></span>
                <span style="color: #ffffff; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-size: 11.5px; background: #18181b; padding: 2px 8px; border-radius: 4px; border: 1px solid #27272a;"><b>{key_tag}</b></span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                <span style="color: #a1a1aa;"><b>ENGINE MODEL</b></span>
                <span style="color: #ffffff; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-size: 11.5px;"><b>{effective_model}</b></span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                <span style="color: #a1a1aa;"><b>REPOSITORY</b></span>
                <span style="color: #ffffff; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-size: 11.5px;"><b>{repo_slug}</b></span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                <span style="color: #a1a1aa;"><b>DEPLOYMENT</b></span>
                <span style="color: #0b0b0b; background: #ffffff; font-weight: 800; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; padding: 2px 8px; border-radius: 4px;"><b>AUTOMATED</b></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()
    st.markdown(
        """
        <div style="font-size: 12px; color: #71717a; line-height: 1.5;">
            <b>Autonomous 5-Agent</b> Engineering Engine<br>
            Powered by <b>Google Gemini</b>
        </div>
        """,
        unsafe_allow_html=True
    )


# =====================================================================
# MENU 1: API KEY SETTINGS
# =====================================================================
if menu == "API Key Settings":
    if build_snapshot["is_running"]:
        st.markdown(
            f"""
            <div style="background: #121214; border: 1px solid #27272a; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #ffffff; font-weight: 700; font-size: 11.5px; font-family: 'JetBrains Mono', monospace;">BUILD ENGINE IN BACKGROUND // [{build_snapshot['current_agent'].upper()}]</span>
                    <span style="color: #a1a1aa; font-size: 12px; margin-left: 8px;">{build_snapshot['status_message']}</span>
                </div>
                <span style="color: #0b0b0b; background: #ffffff; font-weight: 800; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 2px 8px; border-radius: 4px;">{build_snapshot['progress']}%</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div class='mono-kicker'>CONFIGURATION</div>", unsafe_allow_html=True)
    st.title("API Credentials & Model Engine")
    st.caption("Manage authentication for Google Generative Language API and configure language models.")

    col_kmain, col_kinfo = st.columns([1.5, 1.2], gap="large")

    with col_kmain:
        with st.container(border=True):
            st.markdown("##### Google Gemini API Key")
            key_input = st.text_input(
                "Gemini API Key",
                value=st.session_state["active_api_key"],
                type="password",
                help="Stored locally in .env. Never committed to version control.",
                label_visibility="collapsed"
            )

            if key_input.strip() and key_input.strip() != st.session_state["active_api_key"]:
                st.session_state["active_api_key"] = key_input.strip()

            c1, c2, c3 = st.columns([1, 1, 1.2])
            with c1:
                if st.button("Save Key", use_container_width=True):
                    k = key_input.strip()
                    if k:
                        st.session_state["active_api_key"] = k
                        try:
                            with open(".env", "w", encoding="utf-8") as f:
                                f.write(f"GEMINI_API_KEY={k}\n")
                            os.environ["GEMINI_API_KEY"] = k
                            st.success("API key written to .env")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Save error: {e}")
                    else:
                        st.error("Enter a valid key string.")

            with c2:
                if st.button("Reload from .env", use_container_width=True):
                    from dotenv import load_dotenv
                    load_dotenv(override=True)
                    env_k = os.getenv("GEMINI_API_KEY", "")
                    st.session_state["active_api_key"] = env_k
                    st.success("Key reloaded from .env")
                    st.rerun()

            with c3:
                if st.button("Detect Models", use_container_width=True):
                    with st.spinner("Probing ModelService API..."):
                        found = GeminiClient.list_available_models(st.session_state["active_api_key"])
                        if found:
                            st.session_state["detected_models"] = found
                            st.success(f"{len(found)} authorized models discovered")
                        else:
                            st.warning("No models returned. Verify Generative Language API status.")

            st.divider()

            st.markdown("##### Language Model Selection")
            detected = st.session_state.get("detected_models", [])
            standard_models = [
                "gemini-flash-lite-latest",
                "gemini-flash-latest",
                "gemini-pro-latest",
                "gemini-2.0-flash",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "Custom Model..."
            ]
            choices = detected if detected else standard_models
            if "Custom Model..." not in choices:
                choices.append("Custom Model...")

            curr_idx = choices.index(st.session_state["selected_model"]) if st.session_state["selected_model"] in choices else 0
            chosen_model = st.selectbox("Active Gemini Model", options=choices, index=curr_idx)
            
            if chosen_model == "Custom Model...":
                custom_input = st.text_input("Custom Model String:", value=st.session_state.get("custom_model", ""))
                if custom_input.strip():
                    st.session_state["selected_model"] = custom_input.strip()
                    st.session_state["custom_model"] = custom_input.strip()
            else:
                st.session_state["selected_model"] = chosen_model

            st.markdown(f"<span class='mono-pill active'>ACTIVE MODEL // {st.session_state['selected_model']}</span>", unsafe_allow_html=True)

    with col_kinfo:
        with st.container(border=True):
            st.markdown("<div class='mono-kicker'>MODEL CAPABILITIES</div>", unsafe_allow_html=True)
            st.markdown("##### Gemini Architecture Matrix")
            st.markdown(
                """
                <div style="display: flex; flex-direction: column; gap: 10px; font-size: 12.5px; color: #a1a1aa; margin-top: 8px;">
                    <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <b style="color: #ffffff; font-size: 13px;">gemini-flash-latest</b>
                            <span style="font-size: 10px; font-family: monospace; color: #71717a; font-weight: 700;">DEFAULT</span>
                        </div>
                        High-throughput, sub-second latency optimized for rapid multi-agent code generation and fast self-repair cycles.
                    </div>
                    <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <b style="color: #ffffff; font-size: 13px;">gemini-pro-latest</b>
                            <span style="font-size: 10px; font-family: monospace; color: #71717a; font-weight: 700;">DEEP REASONING</span>
                        </div>
                        Complex systems architect with 2M token context, designed for sophisticated schemas and edge-case testing.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.divider()
            st.markdown("<div class='mono-kicker'>SECURITY & ENCRYPTION</div>", unsafe_allow_html=True)
            st.markdown("##### Zero-Leakage Credential Policy")
            st.caption(
                "API credentials are held securely in application session memory and written to a git-ignored local `.env` file. Keys are strictly excluded from generated artifacts, test suites, and git commits."
            )


# =====================================================================
# MENU 2: GITHUB REPOSITORY
# =====================================================================
elif menu == "GitHub Repository":
    if build_snapshot["is_running"]:
        st.markdown(
            f"""
            <div style="background: #121214; border: 1px solid #27272a; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #ffffff; font-weight: 700; font-size: 11.5px; font-family: 'JetBrains Mono', monospace;">BUILD ENGINE IN BACKGROUND // [{build_snapshot['current_agent'].upper()}]</span>
                    <span style="color: #a1a1aa; font-size: 12px; margin-left: 8px;">{build_snapshot['status_message']}</span>
                </div>
                <span style="color: #0b0b0b; background: #ffffff; font-weight: 800; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 2px 8px; border-radius: 4px;">{build_snapshot['progress']}%</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div class='mono-kicker'>INFRASTRUCTURE</div>", unsafe_allow_html=True)
    st.title("Deployment Repository")
    st.caption("Target GitHub repository for continuous Streamlit Community Cloud hosting.")

    col_rmain, col_rinfo = st.columns([1.5, 1.2], gap="large")

    with col_rmain:
        with st.container(border=True):
            st.markdown("##### Git Origin Remote")
            repo_input = st.text_input(
                "Repository URL",
                value=connected_remote,
                help="HTTPS Git remote origin URL",
                label_visibility="collapsed"
            )

            r1, r2, r3 = st.columns([1, 1, 1])
            with r1:
                if st.button("Update Repo", use_container_width=True):
                    clean_url = repo_input.strip()
                    if clean_url:
                        try:
                            remotes = subprocess.run(["git", "remote"], cwd=output_dir, capture_output=True, text=True).stdout
                            if "origin" in remotes.split():
                                subprocess.run(["git", "remote", "set-url", "origin", clean_url], cwd=output_dir, capture_output=True)
                            else:
                                subprocess.run(["git", "remote", "add", "origin", clean_url], cwd=output_dir, capture_output=True)
                            st.success("Origin remote updated")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Remote error: {e}")
                    else:
                        st.error("Provide a valid repository URL.")

            with r2:
                if st.button("Reset Default", use_container_width=True):
                    try:
                        subprocess.run(["git", "remote", "set-url", "origin", DEFAULT_REPO_URL], cwd=output_dir, capture_output=True)
                        st.success("Default repository restored")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Reset error: {e}")

            with r3:
                st.link_button("View on GitHub ↗", connected_remote, use_container_width=True)

            st.divider()

            st.markdown("##### Manual Sync")
            st.caption("Pushes the current generated build to origin/main immediately:")
            if st.button("Push to GitHub Now", use_container_width=True):
                with st.spinner("Pushing build to origin/main..."):
                    subprocess.run(["git", "add", "."], cwd=output_dir)
                    subprocess.run(["git", "commit", "-m", f"Manual sync: {time.strftime('%Y-%m-%d %H:%M:%S')}"], cwd=output_dir)
                    p = subprocess.run(["git", "push", "origin", "main"], cwd=output_dir, capture_output=True, text=True)
                    if p.returncode == 0:
                        st.success("Pushed to origin/main. Cloud redeployment initiated.")
                    else:
                        st.error(f"Push failed: {p.stderr}")

    with col_rinfo:
        with st.container(border=True):
            st.markdown("<div class='mono-kicker'>AUTOMATED PIPELINE</div>", unsafe_allow_html=True)
            st.markdown("##### CI/CD Deployment Flow")
            st.markdown(
                """
                <div style="display: flex; flex-direction: column; gap: 10px; font-size: 12.5px; color: #a1a1aa; margin-top: 8px;">
                    <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 12px;">
                        <b style="color: #ffffff; font-size: 13px;">1. Local Pytest Sandbox</b>
                        <div style="margin-top: 3px;">Generated app code and test suites are validated in a sandboxed runner before any deployment.</div>
                    </div>
                    <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 12px;">
                        <b style="color: #ffffff; font-size: 13px;">2. Automated Git Push</b>
                        <div style="margin-top: 3px;">Verified code is committed with timestamped semantic messages and pushed to <code>origin/main</code>.</div>
                    </div>
                    <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 12px;">
                        <b style="color: #ffffff; font-size: 13px;">3. Streamlit Cloud Webhook</b>
                        <div style="margin-top: 3px;">Streamlit Community Cloud automatically rebuilds and launches the live production URL.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.divider()
            st.markdown("<div class='mono-kicker'>TARGET ENVIRONMENT</div>", unsafe_allow_html=True)
            st.markdown("##### Workspace Remote")
            st.caption(f"Local Workspace: `generated_app/`\n\nBranch: `main`\n\nRemote URL: `{connected_remote}`")


# =====================================================================
# MENU 3: APP BUILDER (MAIN WORKSPACE)
# =====================================================================
elif menu == "App Builder":
    # Header
    col_head, col_badges = st.columns([3, 2])
    with col_head:
        st.markdown("<div class='mono-kicker'>AUTONOMOUS ENGINE</div>", unsafe_allow_html=True)
        st.title("Vessel Studio")
        st.caption("5-agent AI team: Architect → Developer → Testing Engine → Repair Agent → Reviewer")
    with col_badges:
        st.markdown(
            f"""
            <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px; justify-content: center; height: 100%;">
                <div>
                    <span class="mono-pill active"><b>{effective_model.upper()}</b></span>
                </div>
                <div style="display: flex; gap: 6px;">
                    <span class="mono-pill"><b>AUTO-DEPLOY</b></span>
                    <span class="mono-pill"><b>PYTEST SANDBOX</b></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div style='margin-bottom: 4px;'></div>", unsafe_allow_html=True)

    # 1. Main Workspace Canvas (Top / Center)
    workspace_area = st.container()

    # 2. Chatbox / Application Specification Card (Fixed on the bottom of the website)
    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        col_p_title, col_new_app, col_template = st.columns([2.5, 1.1, 1.9])
        with col_p_title:
            st.markdown("<h5 style='margin: 0; font-size: 14px; font-weight: 600;'>Application Specification</h5>", unsafe_allow_html=True)
        with col_new_app:
            if st.button("➕ New App", help="Clear current app results and start fresh", use_container_width=True):
                st.session_state.pop("last_run_state", None)
                st.session_state.pop("local_app_launched", None)
                st.session_state["prompt_input"] = ""
                st.session_state["prev_template"] = "Load a template..."
                build_mgr.reset()
                st.rerun()
        with col_template:
            template_choice = st.selectbox(
                "Quick Templates",
                options=[
                    "Load a template...",
                    "Campus Lost & Found Portal",
                    "Personal Finance & Budget Dashboard",
                    "Prioritized Task & Project Manager",
                    "In-Memory Key-Value Store with ACID"
                ],
                label_visibility="collapsed"
            )
            if template_choice != "Load a template..." and template_choice != st.session_state.get("prev_template"):
                st.session_state["prev_template"] = template_choice
                templates = {
                    "Campus Lost & Found Portal": "Build a functional web application called CampusFind — College Lost & Found Portal using Python and Streamlit with search, category filtering, persistent database, and claim reporting.",
                    "Personal Finance & Budget Dashboard": "Build a comprehensive personal finance dashboard with income/expense logging, category breakdown charts, monthly budget tracker, and CSV export.",
                    "Prioritized Task & Project Manager": "Build a Task and TaskManager application with priority sorting (1-5), completion status tracking, search filtering, and metrics dashboard.",
                    "In-Memory Key-Value Store with ACID": "Create an in-memory Key-Value store with atomic transactions (BEGIN, COMMIT, ROLLBACK), nested transaction blocks, and snapshot isolation."
                }
                st.session_state["prompt_input"] = templates[template_choice]
                # Clear previous app UI immediately when selecting a new template
                st.session_state.pop("last_run_state", None)
                st.session_state.pop("local_app_launched", None)
                build_mgr.reset()
                st.rerun()

        default_prompt = st.session_state.get(
            "prompt_input",
            "Build a functional web application called CampusFind — College Lost & Found Portal using Python and Streamlit with search, category filtering, persistent database, and claim reporting."
        )

        user_prompt = st.text_area(
            "Prompt",
            value=default_prompt,
            height=68,
            placeholder="Specify application features, algorithms, schemas, and UI layout...",
            label_visibility="collapsed"
        )

        col_run_btn, col_popover = st.columns([4, 1])
        with col_run_btn:
            is_building = build_snapshot["is_running"]
            btn_label = "Building Application in Background..." if is_building else "Generate & Deploy Application"
            start_button = st.button(btn_label, type="primary", use_container_width=True, disabled=is_building)
        with col_popover:
            with st.popover("Engine Options"):
                st.markdown("<div class='mono-kicker'>EXECUTION PARAMS</div>", unsafe_allow_html=True)
                max_repairs = st.slider("Max Repair Cycles", min_value=1, max_value=5, value=st.session_state.get("max_repairs", 3))
                st.session_state["max_repairs"] = max_repairs
                timeout_sec = st.slider("Test Timeout (seconds)", min_value=5, max_value=40, value=st.session_state.get("timeout_sec", 20))
                st.session_state["timeout_sec"] = timeout_sec

    # Start build trigger handler (runs detached in background thread)
    if start_button:
        if not user_prompt.strip():
            st.error("Please enter an application requirement.")
        elif not effective_api_key or not effective_api_key.strip():
            st.error("Gemini API Key missing. Configure in API Key Settings.")
        else:
            st.session_state.pop("last_run_state", None)
            started = build_mgr.start_build(
                user_prompt=user_prompt.strip(),
                api_key=effective_api_key.strip(),
                model=effective_model,
                max_repairs=st.session_state.get("max_repairs", 3),
                timeout_sec=st.session_state.get("timeout_sec", 20),
                app_type=app_type
            )
            if started:
                st.rerun()

    # 3. Populate Main Workspace Area (Above the Chatbox)
    with workspace_area:
        active_snapshot = build_mgr.get_snapshot()

        if active_snapshot["is_running"]:
            # Strictly purge any previous session results so they completely disappear during build
            st.session_state.pop("last_run_state", None)
            st.session_state.pop("local_app_launched", None)

            st.markdown("<div class='mono-kicker'>PIPELINE EXECUTION // RUNNING IN BACKGROUND</div>", unsafe_allow_html=True)
            col_status_txt, col_status_pct = st.columns([3, 1])
            with col_status_txt:
                st.markdown(f"**[{active_snapshot['current_agent'].upper()}]** {active_snapshot['status_message']}")
            with col_status_pct:
                st.markdown(f"<div style='text-align: right; font-family: monospace; font-size: 13px; font-weight: 700;'>{active_snapshot['progress']}%</div>", unsafe_allow_html=True)

            st.progress(active_snapshot['progress'])

            with st.expander("Pipeline Stream Log", expanded=True):
                events = active_snapshot.get("events", [])
                if events:
                    for ev in events:
                        ts = ev.get("timestamp", "")
                        ag = ev.get("agent", "")
                        msg = ev.get("message", "")
                        st.caption(f"[{ts}] [{ag}] {msg}")
                else:
                    st.caption("Initializing agents...")

            time.sleep(0.7)
            st.rerun()

        elif active_snapshot.get("error"):
            st.error(f"Execution failure: {active_snapshot['error']}")
            if active_snapshot.get("traceback"):
                st.code(active_snapshot["traceback"], language="python")
            if st.button("Dismiss & Return to Standby"):
                build_mgr.reset()
                st.rerun()

        elif active_snapshot.get("final_state") is not None or "last_run_state" in st.session_state:
            if active_snapshot.get("final_state") is not None:
                st.session_state["last_run_state"] = active_snapshot["final_state"]

            state = st.session_state["last_run_state"]
            review = state.get("review", {})
            tests = state.get("latest_test_result", {})

            # Primary Action Bar Container
            with st.container(border=True):
                col_l1, col_l2, col_l3, col_l4 = st.columns([1.8, 1.8, 1.2, 1.2])
                with col_l1:
                    if st.button("Launch Local Web App (Port 8502)", type="primary", use_container_width=True):
                        app_path = os.path.join(output_dir, "app.py")
                        if os.path.exists(app_path):
                            import sys
                            cmd = [sys.executable, "-m", "streamlit", "run", app_path, "--server.port", "8502", "--server.headless", "true"]
                            subprocess.Popen(cmd)
                            st.session_state["local_app_launched"] = True
                        else:
                            st.error("No app.py found.")
                    if st.session_state.get("local_app_launched"):
                        st.success("App active on port 8502")
                        st.markdown("**[Open Local App: http://localhost:8502](http://localhost:8502)**")
                with col_l2:
                    st.link_button("View on Streamlit Cloud ↗", "https://share.streamlit.io", use_container_width=True)
                with col_l3:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        zip_file.writestr("app.py", state.get("current_app_code", ""))
                        zip_file.writestr("test_app.py", state.get("test_code", ""))
                        zip_file.writestr("requirements.txt", "streamlit\npytest>=8.0.0\n")
                    zip_buffer.seek(0)
                    st.download_button(
                        label="Export ZIP",
                        data=zip_buffer,
                        file_name="generated_app.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                with col_l4:
                    if st.button("➕ Start New App", help="Clear results and start fresh", use_container_width=True):
                        st.session_state.pop("last_run_state", None)
                        st.session_state.pop("local_app_launched", None)
                        build_mgr.reset()
                        st.rerun()

            # Metrics Row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("VERIFICATION", review.get("status", "VERIFIED"))
            m2.metric("QUALITY SCORE", review.get("overall_score", "N/A"))
            m3.metric("TEST SUITE", f"{tests.get('passed_tests', 0)} / {tests.get('total_tests', 0)} PASSED")
            m4.metric("SELF-REPAIRS", f"{len(state.get('repair_history', []))} CYCLES")

            # Clean Tabs
            tab_code, tab_tests, tab_repairs, tab_audit = st.tabs([
                "Source Code",
                "Test Suite Output",
                "Self-Repair History",
                "QA Report"
            ])

            with tab_code:
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown("<div class='mono-kicker'>APPLICATION ENGINE</div>", unsafe_allow_html=True)
                    st.code(state.get("current_app_code", ""), language="python")
                with col_c2:
                    st.markdown("<div class='mono-kicker'>PYTEST SPECIFICATION</div>", unsafe_allow_html=True)
                    st.code(state.get("test_code", ""), language="python")

            with tab_tests:
                st.markdown(f"<div class='terminal-box'>{tests.get('full_output', 'No output recorded.')}</div>", unsafe_allow_html=True)

            with tab_repairs:
                repairs = state.get("repair_history", [])
                if not repairs:
                    st.markdown("Zero repairs required. Generated code passed all tests on first run.")
                else:
                    for item in repairs:
                        st.markdown(f"**CYCLE #{item.get('iteration')} //** {item.get('explanation')}")
                        if item.get("diff"):
                            st.code(item.get("diff"), language="diff")

            with tab_audit:
                st.markdown("<div class='mono-kicker'>ARCHITECTURE</div>", unsafe_allow_html=True)
                st.markdown(state.get("architecture_summary", "No architecture recorded."))
                st.divider()

                score_breakdown = review.get("score_breakdown")
                if score_breakdown:
                    st.markdown("<div class='mono-kicker'>OBJECTIVE QUALITY BENCHMARK</div>", unsafe_allow_html=True)
                    sb_c1, sb_c2, sb_c3, sb_c4 = st.columns(4)
                    sb_c1.metric("Tests Verified", score_breakdown.get("test_verification", "4.0/4.0"))
                    sb_c2.metric("Repair Friction", score_breakdown.get("repair_efficiency", "1.5/1.5"))
                    sb_c3.metric("Test Suite Depth", score_breakdown.get("test_depth", "2.0/2.0"))
                    sb_c4.metric("Code Architecture", score_breakdown.get("code_architecture", "2.5/2.5"))
                    st.divider()

                st.markdown("<div class='mono-kicker'>EXECUTIVE AUDIT</div>", unsafe_allow_html=True)
                st.write(review.get("summary", "No executive summary available."))

                col_kf, col_td = st.columns(2)
                with col_kf:
                    st.markdown("**Key Findings:**")
                    for f in review.get("key_findings", []):
                        st.markdown(f"- {f}")
                with col_td:
                    st.markdown("**Technical Recommendations:**")
                    for td in review.get("technical_debt_and_recommendations", []):
                        st.markdown(f"- {td}")

        else:
            # Standby / Hero state before generation (Compact No-Scroll Fit)
            st.markdown(
                """
                <div style="padding: 4px 0 6px 0;">
                    <div class="mono-card" style="padding: 12px 16px; margin-bottom: 4px;">
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px;">
                            <div class="mono-kicker" style="margin-bottom: 0;">AUTONOMOUS MULTI-AGENT ARCHITECTURE</div>
                            <span style="font-size: 10.5px; font-family: monospace; color: #71717a;">5-AGENT ENGINE // STANDBY</span>
                        </div>
                        <p style="color: #a1a1aa; font-size: 12px; line-height: 1.45; margin: 0 0 8px 0;">
                            Deterministic engineering pipeline generating verified Streamlit web apps with sandboxed pytest suites, self-healing traceback repair, and automated cloud sync.
                        </p>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px;">
                            <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 7px 10px;">
                                <div style="color: #71717a; font-size: 9.5px; font-family: monospace; font-weight: 700;">01 // ARCHITECT</div>
                                <div style="color: #ffffff; font-size: 11.5px; font-weight: 600; margin-top: 1px;">System Blueprint</div>
                            </div>
                            <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 7px 10px;">
                                <div style="color: #71717a; font-size: 9.5px; font-family: monospace; font-weight: 700;">02 // DEVELOPER</div>
                                <div style="color: #ffffff; font-size: 11.5px; font-weight: 600; margin-top: 1px;">App & Test Code</div>
                            </div>
                            <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 7px 10px;">
                                <div style="color: #71717a; font-size: 9.5px; font-family: monospace; font-weight: 700;">03 // TESTING</div>
                                <div style="color: #ffffff; font-size: 11.5px; font-weight: 600; margin-top: 1px;">Sandboxed Pytest</div>
                            </div>
                            <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 7px 10px;">
                                <div style="color: #71717a; font-size: 9.5px; font-family: monospace; font-weight: 700;">04 // REPAIR</div>
                                <div style="color: #ffffff; font-size: 11.5px; font-weight: 600; margin-top: 1px;">Traceback Patch</div>
                            </div>
                            <div style="background: #090909; border: 1px solid #1f1f1f; border-radius: 6px; padding: 7px 10px;">
                                <div style="color: #71717a; font-size: 9.5px; font-family: monospace; font-weight: 700;">05 // REVIEWER</div>
                                <div style="color: #ffffff; font-size: 11.5px; font-weight: 600; margin-top: 1px;">Cloud Auto-Deploy</div>
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
