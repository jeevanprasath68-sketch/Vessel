import pytest
from core.git_sync import (
    sanitize_url,
    sanitize_message,
    resolve_streamlit_cloud_url,
    resolve_github_token,
    load_vessel_config,
    save_vessel_config
)

def test_sanitize_url():
    raw_with_token = "https://x-access-token:ghp_secrettoken1234567890@github.com/user/repo.git"
    clean = sanitize_url(raw_with_token)
    assert "secrettoken" not in clean
    assert clean == "https://github.com/user/repo.git"

def test_sanitize_message():
    err = "fatal: Authentication failed for 'https://x-access-token:ghp_1234567890abcdef1234567890abcdef@github.com/user/repo.git'"
    clean = sanitize_message(err)
    assert "ghp_" not in clean
    assert "1234567890abcdef" not in clean
    assert "https://github.com/user/repo.git" in clean

def test_resolve_streamlit_cloud_url_smart_default():
    remote = "https://github.com/jeevanprasath68-sketch/generated.git"
    url = resolve_streamlit_cloud_url(remote)
    assert "jeevanprasath68-sketch" in url
    assert "generated" in url
    assert url.endswith(".streamlit.app")

def test_save_and_load_vessel_config(tmp_path, monkeypatch):
    test_cfg_file = str(tmp_path / "test_vessel_config.json")
    monkeypatch.setattr("core.git_sync.CONFIG_FILE", test_cfg_file)

    save_vessel_config({"github_token": "test_token_xyz", "streamlit_cloud_url": "https://custom.streamlit.app"})
    loaded = load_vessel_config()
    assert loaded["github_token"] == "test_token_xyz"
    assert loaded["streamlit_cloud_url"] == "https://custom.streamlit.app"
