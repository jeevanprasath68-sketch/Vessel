import pytest
import os
import sqlite3
from app import ArcadeDB, GameConfig, DB_FILE

@pytest.fixture(autouse=True)
def setup_db():
    # Setup fresh DB for testing
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    ArcadeDB.init_db()
    yield
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_database_initialization():
    """Test that database and tables are correctly initialized."""
    conn = ArcadeDB.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='high_scores'")
    table = cursor.fetchone()
    conn.close()
    assert table is not None

def test_add_and_get_score():
    """Test adding a score and retrieving the leaderboard."""
    ArcadeDB.add_score("TestPlayer", 7, 3, "Normal")
    leaderboard = ArcadeDB.get_leaderboard(limit=5)
    
    assert len(leaderboard) == 1
    assert leaderboard[0]["player_name"] == "TestPlayer"
    assert leaderboard[0]["score"] == 7
    assert leaderboard[0]["ai_score"] == 3
    assert leaderboard[0]["difficulty"] == "Normal"

def test_global_stats_increment():
    """Test global match and points statistics tracking."""
    stats_before = ArcadeDB.get_global_stats()
    assert stats_before["total_matches"] == 0
    assert stats_before["total_points_scored"] == 0

    ArcadeDB.add_score(
        player_name="Champ",
        score=10,
        ai_score=8,
        difficulty="Hard"
    )

    stats_after = ArcadeDB.get_global_stats()
    assert stats_after["total_matches"] == 1
    assert stats_after["total_points_scored"] == 18

def test_clear_database():
    """Test clearing the database wipes scores and resets stats."""
    ArcadeDB.add_score("RetroKing", 5, 1, "Easy")
    assert len(ArcadeDB.get_leaderboard()) == 1

    ArcadeDB.clear_database()
    assert len(ArcadeDB.get_leaderboard()) == 0
    stats = ArcadeDB.get_global_stats()
    assert stats["total_matches"] == 0

def test_game_config_difficulties():
    """Test that all game configuration levels are well-defined."""
    assert "Easy" in GameConfig.DIFFICULTIES
    assert "Normal" in GameConfig.DIFFICULTIES
    assert "Hard" in GameConfig.DIFFICULTIES
    assert "Extreme" in GameConfig.DIFFICULTIES
    
    for diff, cfg in GameConfig.DIFFICULTIES.items():
        assert "ai_speed" in cfg
        assert "ball_speed" in cfg
        assert "target_score" in cfg
        assert cfg["target_score"] > 0