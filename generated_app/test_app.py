import os
import pytest
from app import GameConfig, LeaderboardDB

@pytest.fixture
def py_db(tmp_path):
    db_file = tmp_path / "test_arcade.db"
    db = LeaderboardDB(db_path=str(db_file))
    return db

def test_game_config_difficulties():
    assert "Casual" in GameConfig.DIFFICULTIES
    assert "Standard" in GameConfig.DIFFICULTIES
    assert "Pro" in GameConfig.DIFFICULTIES
    assert "Impossible" in GameConfig.DIFFICULTIES
    
    assert GameConfig.DIFFICULTIES["Casual"]["lives"] > GameConfig.DIFFICULTIES["Impossible"]["lives"]
    assert GameConfig.DIFFICULTIES["Impossible"]["multiplier"] > GameConfig.DIFFICULTIES["Casual"]["multiplier"]

def test_leaderboard_initialization(py_db):
    stats = py_db.get_stats()
    assert stats["total_games"] == 0
    assert stats["max_score"] == 0
    assert stats["avg_score"] == 0

def test_add_and_get_scores(py_db):
    py_db.add_score("PlayerOne", 500, "Standard")
    py_db.add_score("PlayerTwo", 1200, "Pro")
    
    scores = py_db.get_top_scores(limit=5)
    assert len(scores) == 2
    assert scores[0][0] == "PlayerTwo"
    assert scores[0][1] == 1200
    assert scores[1][0] == "PlayerOne"
    assert scores[1][1] == 500

def test_leaderboard_filtering(py_db):
    py_db.add_score("CasualChamp", 300, "Casual")
    py_db.add_score("ProGod", 2500, "Pro")
    
    casual_scores = py_db.get_top_scores(difficulty="Casual")
    assert len(casual_scores) == 1
    assert casual_scores[0][0] == "CasualChamp"
    assert casual_scores[0][2] == "Casual"

def test_leaderboard_stats(py_db):
    py_db.add_score("A", 100, "Standard")
    py_db.add_score("B", 300, "Standard")
    
    stats = py_db.get_stats()
    assert stats["total_games"] == 2
    assert stats["max_score"] == 300
    assert stats["avg_score"] == 200

def test_leaderboard_reset(py_db):
    py_db.add_score("Test", 999, "Standard")
    assert py_db.get_stats()["total_games"] == 1
    
    py_db.reset_leaderboard()
    assert py_db.get_stats()["total_games"] == 0
    assert py_db.get_stats()["max_score"] == 0