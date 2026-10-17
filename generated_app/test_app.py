import pytest
import pandas as pd
import sqlite3
import os
from app import DatabaseEngine, GameValidator, DB_NAME

@pytest.fixture(autouse=True)
def setup_test_db():
    # Use a test database or reset before/after tests
    DatabaseEngine.init_db()
    yield
    # Cleanup optional

def test_score_validator_happy_path():
    assert GameValidator.validate_score(5, 2) is True
    assert GameValidator.validate_score(0, 0) is True
    assert GameValidator.validate_score(10, 8) is True

def test_score_validator_edge_cases():
    # Negative scores are invalid
    assert GameValidator.validate_score(-1, 3) is False
    # Non-integer inputs should return False
    assert GameValidator.validate_score("5", 2) is False # type: ignore
    assert GameValidator.validate_score(5, None) is False # type: ignore

def test_calculate_match_stats_empty():
    empty_df = pd.DataFrame(columns=["id", "player_name", "player_score", "ai_score", "difficulty", "winner", "played_at"])
    stats = GameValidator.calculate_match_stats(empty_df)
    assert stats["total_matches"] == 0
    assert stats["avg_player_score"] == 0.0
    assert stats["player_win_rate"] == 0.0

def test_calculate_match_stats_populated():
    data = {
        "id": [1, 2, 3],
        "player_name": ["TestUser", "TestUser", "TestUser"],
        "player_score": [5, 2, 5],
        "ai_score": [3, 5, 1],
        "difficulty": ["Medium", "Hard", "Easy"],
        "winner": ["TestUser", "AI Bot", "TestUser"],
        "played_at": ["2023-10-01 10:00:00", "2023-10-01 10:05:00", "2023-10-01 10:10:00"]
    }
    df = pd.DataFrame(data)
    stats = GameValidator.calculate_match_stats(df)
    assert stats["total_matches"] == 3
    assert stats["avg_player_score"] == 4.0
    assert stats["player_win_rate"] == 66.7

def test_database_persistence_and_retrieval():
    # Test saving match data and retrieving leaderboard/history
    success = DatabaseEngine.save_match("PyTestHero", 5, 1, "Hard")
    assert success is True

    leaderboard = DatabaseEngine.get_leaderboard()
    assert not leaderboard.empty
    assert "PyTestHero" in leaderboard["player_name"].values

    history = DatabaseEngine.get_match_history()
    assert not history.empty
    match_record = history[history["player_name"] == "PyTestHero"]
    assert len(match_record) > 0
    assert match_record.iloc[0]["player_score"] == 5

def test_database_self_healing_schema():
    # Ensure init_db runs smoothly without raising exceptions even if run repeatedly
    try:
        DatabaseEngine.init_db()
        DatabaseEngine.init_db()
        assert True
    except Exception as e:
        pytest.fail(f"Database self-healing schema initialization failed with error: {e}")