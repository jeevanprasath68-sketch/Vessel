"""
Git Synchronization and Headless Deployment Utility
Handles automated Git commits, rebases, and authenticated HTTPS pushes
for local development and headless cloud environments (e.g. Streamlit Community Cloud).
"""
import os
import re
import json
import subprocess
from typing import Optional, Dict, Any

CONFIG_FILE = os.path.join(os.getcwd(), "vessel_config.json")
DEFAULT_REPO_URL = "https://github.com/jeevanprasath68-sketch/generated.git"
DEFAULT_STREAMLIT_URL = "https://share.streamlit.io"


def load_vessel_config() -> Dict[str, Any]:
    """Loads persistent settings (tokens, URLs) from vessel_config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_vessel_config(updates: Dict[str, Any]) -> bool:
    """Updates and saves persistent settings to vessel_config.json."""
    try:
        current = load_vessel_config()
        current.update(updates)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return True
    except Exception as e:
        print(f"[Warning] Failed to save config: {e}")
        return False


def resolve_github_token() -> Optional[str]:
    """
    Resolves GitHub Personal Access Token (PAT) across multiple sources:
    1. Streamlit secrets (if available in cloud environment)
    2. Environment variables: GITHUB_TOKEN, GH_TOKEN
    3. vessel_config.json (saved via UI)
    """
    token = None
    # 1. Check Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "GITHUB_TOKEN" in st.secrets:
                token = str(st.secrets["GITHUB_TOKEN"]).strip()
            elif "GH_TOKEN" in st.secrets:
                token = str(st.secrets["GH_TOKEN"]).strip()
    except Exception:
        pass

    # 2. Check environment variables
    if not token:
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if token:
            token = token.strip()

    # 3. Check persistent config
    if not token:
        cfg = load_vessel_config()
        t = cfg.get("github_token", "")
        if t and isinstance(t, str):
            token = t.strip()

    return token if token else None


def resolve_streamlit_cloud_url(connected_remote: str = "") -> str:
    """
    Resolves the live Streamlit Community Cloud app URL:
    1. Streamlit secrets: STREAMLIT_APP_URL
    2. Environment variables: STREAMLIT_APP_URL
    3. vessel_config.json: streamlit_cloud_url
    4. Smart default based on GitHub repo owner/name or share.streamlit.io
    """
    # 1. Check Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "STREAMLIT_APP_URL" in st.secrets:
            url = str(st.secrets["STREAMLIT_APP_URL"]).strip()
            if url:
                return url
    except Exception:
        pass

    # 2. Check environment variable
    env_url = os.getenv("STREAMLIT_APP_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    # 3. Check persistent config
    cfg = load_vessel_config()
    cfg_url = cfg.get("streamlit_cloud_url", "")
    if cfg_url and isinstance(cfg_url, str) and cfg_url.strip():
        return cfg_url.strip()

    # 4. Smart default:
    # If repo is https://github.com/jeevanprasath68-sketch/generated.git,
    # Streamlit Cloud app default subdomain is often jeevanprasath68-sketch-generated.streamlit.app
    if connected_remote:
        m = re.search(r"github\.com[/:]([\w-]+)/([\w-]+)", connected_remote)
        if m:
            owner, repo = m.group(1), m.group(2).replace(".git", "")
            return f"https://{owner}-{repo}.streamlit.app"

    return DEFAULT_STREAMLIT_URL


def sanitize_url(url: str) -> str:
    """Removes basic auth credentials (tokens) from Git URLs for safe public display."""
    if not url:
        return ""
    return re.sub(r"https://[^@]+@github\.com", "https://github.com", url)


def sanitize_message(msg: str) -> str:
    """Scrubs any embedded GitHub tokens or credentials from error/status messages."""
    if not msg:
        return ""
    clean = re.sub(r"x-access-token:[a-zA-Z0-9_\-\.]+@", "x-access-token:***@", msg)
    clean = re.sub(r"ghp_[a-zA-Z0-9]{30,}", "***", clean)
    clean = re.sub(r"github_pat_[a-zA-Z0-9_]{30,}", "***", clean)
    return sanitize_url(clean)


def sync_and_push(
    repo_dir: str,
    commit_msg: str,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stages, commits, and pushes all changes in repo_dir to origin/main.
    Uses GitHub Personal Access Token (if available) for non-interactive headless authentication.
    """
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        return {
            "success": False,
            "error": "Not a git repository (missing .git directory).",
            "message": "Git push failed: Not a git repository."
        }

    # Non-interactive Git environment: prevents Git from hanging indefinitely on terminal prompt
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"

    raw_remote = ""
    try:
        remote_chk = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env
        )
        if remote_chk.returncode != 0 or not remote_chk.stdout.strip():
            return {
                "success": False,
                "error": "No 'origin' remote configured.",
                "message": "Git push failed: origin remote not found."
            }

        raw_remote = remote_chk.stdout.strip()
        display_remote = sanitize_url(raw_remote)

        # Resolve GitHub token if not explicitly provided
        if not token:
            token = resolve_github_token()

        # Build authenticated remote push target if token is present and it's a GitHub HTTPS URL
        if token and "github.com" in raw_remote:
            clean_host_path = re.sub(r"^https?://([^@]+@)?github\.com/", "", raw_remote)
            if not clean_host_path.endswith(".git"):
                clean_host_path += ".git"
            auth_push_target = f"https://x-access-token:{token}@github.com/{clean_host_path}"
        else:
            auth_push_target = raw_remote

        # Configure local git identity if not already set
        subprocess.run(["git", "config", "user.name", "Vessel Studio"], cwd=repo_dir, capture_output=True, env=env)
        subprocess.run(["git", "config", "user.email", "vessel@autonomous.build"], cwd=repo_dir, capture_output=True, env=env)

        # Untrack any accidentally committed sqlite databases
        subprocess.run(["git", "rm", "--cached", "-f", "*.db", "*.sqlite", "*.sqlite3"], cwd=repo_dir, capture_output=True, env=env)

        # Stage all changes
        subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True, env=env)

        # Check if there are changes to commit
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True, env=env)
        has_changes = bool(status_res.stdout.strip())

        if has_changes:
            clean_msg = commit_msg.replace('"', "'")
            subprocess.run(["git", "commit", "-m", clean_msg], cwd=repo_dir, capture_output=True, env=env)

        # Push to origin main using authenticated target
        push_res = subprocess.run(
            ["git", "push", "-u", auth_push_target, "main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env
        )

        # If rejected due to non-fast-forward, attempt pull rebase and push again
        if push_res.returncode != 0 and ("fetch first" in (push_res.stderr or "") or "non-fast-forward" in (push_res.stderr or "")):
            subprocess.run(["git", "pull", "--rebase", auth_push_target, "main"], cwd=repo_dir, capture_output=True, env=env)
            push_res = subprocess.run(
                ["git", "push", "-u", auth_push_target, "main"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                env=env
            )

        if push_res.returncode == 0:
            rev_res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, capture_output=True, text=True, env=env)
            commit_hash = rev_res.stdout.strip() if rev_res.returncode == 0 else "HEAD"
            return {
                "success": True,
                "remote_url": display_remote,
                "commit_hash": commit_hash,
                "message": f"Successfully pushed commit {commit_hash} to {display_remote}. Streamlit Cloud will auto-redeploy!"
            }
        else:
            raw_err = (push_res.stderr or push_res.stdout or "Push rejected").strip()
            clean_err = sanitize_message(raw_err)

            if "could not read Username" in clean_err or "No such device or address" in clean_err or "Authentication failed" in clean_err:
                clean_err = (
                    "Authentication required: Streamlit Community Cloud runs in a headless environment. "
                    "Please save your GitHub Personal Access Token (PAT) under 'GitHub Repository' settings "
                    "or in Streamlit Cloud Secrets (GITHUB_TOKEN)."
                )

            return {
                "success": False,
                "remote_url": display_remote,
                "error": clean_err,
                "message": f"Git auto-push encountered error: {clean_err}"
            }

    except Exception as e:
        err_msg = sanitize_message(str(e))
        return {
            "success": False,
            "remote_url": sanitize_url(raw_remote),
            "error": err_msg,
            "message": f"Git auto-push failed: {err_msg}"
        }
