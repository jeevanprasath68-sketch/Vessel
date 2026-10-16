import time
from core.build_manager import BuildManager

def test_build_manager_singleton():
    mgr1 = BuildManager.get_instance()
    mgr2 = BuildManager.get_instance()
    assert mgr1 is mgr2

def test_build_manager_mock_flow(monkeypatch):
    mgr = BuildManager.get_instance()
    mgr.reset()
    snap = mgr.get_snapshot()
    assert snap["is_running"] is False
    assert snap["progress"] == 0

    # Start a build with mock mode
    from unittest.mock import patch
    from core.orchestrator import MultiAgentOrchestrator

    mock_events = [
        {"event": "STAGE_START", "agent": "Architect", "message": "Blueprint..."},
        {"event": "ARCHITECT_DONE", "agent": "Architect", "message": "Done"},
        {"event": "PIPELINE_COMPLETE", "agent": "Orchestrator", "data": {"current_app_code": "import streamlit as st"}}
    ]

    with patch.object(MultiAgentOrchestrator, "execute_stream", return_value=iter(mock_events)):
        started = mgr.start_build(
            user_prompt="Mock Prompt",
            api_key="mock_key",
            model="gemini-flash-lite-latest",
            max_repairs=1,
            timeout_sec=5
        )
        assert started is True

        # Wait briefly for daemon thread to complete
        for _ in range(50):
            snap = mgr.get_snapshot()
            if not snap["is_running"]:
                break
            time.sleep(0.05)

        snap = mgr.get_snapshot()
        assert snap["is_running"] is False
        assert snap["progress"] == 100
        assert snap["final_state"] is not None
        assert "current_app_code" in snap["final_state"]
