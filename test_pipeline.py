import sys
from core.llm_client import GeminiClient
from core.orchestrator import MultiAgentOrchestrator

def main():
    print("Testing 5-Agent Pipeline in Offline/Mock Mode...")
    client = GeminiClient(mock_mode=True)
    orchestrator = MultiAgentOrchestrator(gemini_client=client, max_repairs=3, timeout_seconds=10)

    events_received = []
    for event in orchestrator.execute_stream("Create a prioritized task manager", auto_push=False):
        event_type = event.get("event")
        agent = event.get("agent", "Orchestrator")
        msg = event.get("message", "")
        print(f"[{event_type}] ({agent}): {msg}")
        events_received.append(event_type)

    assert "ARCHITECT_DONE" in events_received, "Architect event missing"
    assert "TEST_RUN_DONE" in events_received, "Test run event missing"
    assert "REPAIR_DONE" in events_received, "Repair event missing"
    assert "REVIEW_DONE" in events_received, "Review event missing"
    assert "PIPELINE_COMPLETE" in events_received, "Pipeline complete event missing"

    print("\nSUCCESS: All 5 agents executed and communicated cleanly!")

if __name__ == "__main__":
    main()
