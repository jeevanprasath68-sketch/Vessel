import os
import pytest
from app import GameConfig, LeaderboardDB

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_scores.db"
    return LeaderboardDB(db_path=str(db_file))

def test_difficulty_settings():
    casual = GameConfig.get_difficulty_settings("Casual")
    impossible = GameConfig.get_difficulty_settings("Impossible")
    unknown = GameConfig.get_difficulty_settings("NonExistent")

    assert casual["speed_mult"] == 0.8
    assert casual["player_lives"] == 5
    assert impossible["score_mult"] == 3.0
    assert impossible["player_lives"] == 2
    # Fallback to standard for unknown
    assert unknown["speed_mult"] == 1.0

def test_leaderboard_initialization(temp_db):
    stats = temp_db.get_stats()
    assert stats["total_games"] == 0
    assert stats["high_score"] == 0
    assert stats["avg_score"] == 0

def test_add_and_retrieve_scores(temp_db):
    assert temp_db.add_score("Viper", 1500, "Standard") is True
    assert temp_db.add_score("Maverick", 3400, "Pro") is True
    
    scores = temp_db.get_top_scores(limit=5)
    assert len(scores) == 2
    # Top score should be first
    assert scores[0][0] == "Maverick"
    assert scores[0][1] == 3400
    assert scores[0][2] == "Pro"

def test_invalid_score_submission(temp_db):
    # Empty name should fail
    assert temp_db.add_score("", 500) is False
    assert temp_db.add_score("   ", 500) is False

def test_leaderboard_stats(temp_db):
    temp_db.add_score("PilotA", 1000, "Standard")
    temp_db.add_score("PilotB", 3000, "Standard")

    stats = temp_db.get_stats()
    assert stats["total_games"] == 2
    assert stats["high_score"] == 3000
    assert stats["avg_score"] == 2000

def test_reset_leaderboard(temp_db):
    temp_db.add_score("PilotX", 9999, "Impossible")
    assert temp_db.get_stats()["total_games"] == 1

    temp_db.reset_leaderboard()
    stats = temp_db.get_stats()
    assert stats["total_games"] == 0
    assert stats["high_score"] == 0