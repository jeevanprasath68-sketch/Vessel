import sqlite3
import streamlit as st
import streamlit.components.v1 as components
from typing import List, Dict, Any, Optional
import datetime

DB_FILE = "ping_pong_arcade.db"

class ArcadeDB:
    """Robust SQLite database engine with automatic schema migration and self-healing."""
    
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # Create tables if not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS high_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                ai_score INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_matches INTEGER DEFAULT 0,
                total_points_scored INTEGER DEFAULT 0
            )
        """)
        
        # Check and add missing columns if upgrading schema
        cursor.execute("PRAGMA table_info(high_scores)")
        columns = [row["name"] for row in cursor.fetchall()]
        
        if "difficulty" not in columns:
            cursor.execute("ALTER TABLE high_scores ADD COLUMN difficulty TEXT DEFAULT 'Normal'")
            
        conn.commit()
        
        # Ensure stats row exists
        cursor.execute("SELECT COUNT(*) as cnt FROM game_stats")
        if cursor.fetchone()["cnt"] == 0:
            cursor.execute("INSERT INTO game_stats (total_matches, total_points_scored) VALUES (0, 0)")
            conn.commit()
            
        conn.close()

    @classmethod
    def add_score(cls, player_name: str, score: int, ai_score: int, difficulty: str):
        cls.init_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO high_scores (player_name, score, ai_score, difficulty, timestamp) VALUES (?, ?, ?, ?, ?)",
            (player_name, score, ai_score, difficulty, timestamp)
        )
        cursor.execute(
            "UPDATE game_stats SET total_matches = total_matches + 1, total_points_scored = total_points_scored + ?",
            (score + ai_score,)
        )
        conn.commit()
        conn.close()

    @classmethod
    def get_leaderboard(cls, limit: int = 10) -> List[Dict[str, Any]]:
        cls.init_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT player_name, score, ai_score, difficulty, timestamp FROM high_scores ORDER BY score DESC, timestamp ASC LIMIT ?",
            (limit,)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    @classmethod
    def get_global_stats(cls) -> Dict[str, int]:
        cls.init_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT total_matches, total_points_scored FROM game_stats LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"total_matches": row["total_matches"], "total_points_scored": row["total_points_scored"]}
        return {"total_matches": 0, "total_points_scored": 0}

    @classmethod
    def clear_database(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS high_scores")
        cursor.execute("DROP TABLE IF EXISTS game_stats")
        conn.commit()
        conn.close()
        cls.init_db()

class GameConfig:
    """Game configuration helper for difficulties and rules."""
    DIFFICULTIES = {
        "Easy": {"ai_speed": 3.5, "ball_speed": 4.0, "target_score": 5},
        "Normal": {"ai_speed": 5.0, "ball_speed": 6.0, "target_score": 7},
        "Hard": {"ai_speed": 7.5, "ball_speed": 8.5, "target_score": 10},
        "Extreme": {"ai_speed": 10.0, "ball_speed": 11.0, "target_score": 11}
    }

def render_ping_pong_canvas(ai_speed: float, ball_speed: float, target_score: int, player_name: str):
    """Renders the retro arcade HTML/JS canvas securely without f-string JS template collision."""
    html_code = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Retro Ping Pong</title>
        <style>
            body {
                background-color: #0b0f19;
                color: #00ffcc;
                font-family: 'Courier New', Courier, monospace;
                text-align: center;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }
            #game-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
            }
            canvas {
                border: 4px solid #00ffcc;
                box-shadow: 0 0 25px rgba(0, 255, 204, 0.4);
                background: #000;
                display: block;
            }
            .scoreboard {
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 12px;
                letter-spacing: 2px;
                text-transform: uppercase;
            }
            .controls-hint {
                margin-top: 10px;
                font-size: 13px;
                color: #88aacc;
            }
        </style>
    </head>
    <body>
        <div id="game-container">
            <div class="scoreboard" id="scoreBoard">
                __PLAYER__ : <span id="playerScore">0</span> &nbsp;|&nbsp; AI : <span id="aiScore">0</span> (Target: __TARGET__)</div>
            <canvas id="pongCanvas" width="700" height="450"></canvas>
            <div class="controls-hint">Use <b>UP / DOWN Arrow Keys</b> or <b>W / S</b> to move your paddle. Press <b>SPACE</b> to Start/Pause.</div>
        </div>

        <script>
            const canvas = document.getElementById("pongCanvas");
            const ctx = canvas.getContext("2d");

            const playerName = "__PLAYER__";
            const targetScore = __TARGET__;
            const aiSpeed = __AI_SPEED__;
            const baseBallSpeed = __BALL_SPEED__;

            let playerScore = 0;
            let aiScore = 0;
            let gameRunning = false;
            let gameOver = false;

            // Paddle setup
            const paddleWidth = 12;
            const paddleHeight = 80;
            const player = {
                x: 15,
                y: canvas.height / 2 - paddleHeight / 2,
                width: paddleWidth,
                height: paddleHeight,
                score: 0,
                dy: 6
            };

            const ai = {
                x: canvas.width - 27,
                y: canvas.height / 2 - paddleHeight / 2,
                width: paddleWidth,
                height: paddleHeight,
                score: 0
            };

            // Ball setup
            const ball = {
                x: canvas.width / 2,
                y: canvas.height / 2,
                radius: 9,
                speed: baseBallSpeed,
                velocityX: baseBallSpeed * (Math.random() > 0.5 ? 1 : -1),
                velocityY: baseBallSpeed * (Math.random() * 2 - 1)
            };

            // Keyboard tracking
            const keys = {};
            window.addEventListener('keydown', function(e) {
                if(["ArrowUp","ArrowDown"," ", "KeyW", "KeyS"].includes(e.code)) {
                    e.preventDefault();
                }
                keys[e.code] = true;
                if(e.code === 'Space') {
                    if(gameOver) {
                        resetMatch();
                    } else {
                        gameRunning = !gameRunning;
                    }
                }
            });

            window.addEventListener('keyup', function(e) {
                keys[e.code] = false;
            });

            function resetBall(winner) {
                ball.x = canvas.width / 2;
                ball.y = canvas.height / 2;
                ball.speed = baseBallSpeed;
                ball.velocityX = -ball.velocityX;
                ball.velocityY = (Math.random() * 4 - 2);
            }

            function resetMatch() {
                playerScore = 0;
                aiScore = 0;
                document.getElementById("playerScore").innerText = playerScore;
                document.getElementById("aiScore").innerText = aiScore;
                gameOver = false;
                gameRunning = true;
                resetBall('player');
            }

            function update() {
                if (!gameRunning || gameOver) return;

                // Player movement
                if ((keys['ArrowUp'] || keys['KeyW']) && player.y > 0) {
                    player.y -= player.dy;
                }
                if ((keys['ArrowDown'] || keys['KeyS']) && player.y < canvas.height - player.height) {
                    player.y += player.dy;
                }

                // AI movement (track ball with slight lag/speed limit)
                let aiCenter = ai.y + ai.height / 2;
                if (aiCenter < ball.y - 10) {
                    ai.y += aiSpeed;
                } else if (aiCenter > ball.y + 10) {
                    ai.y -= aiSpeed;
                }
                // Clamp AI
                if (ai.y < 0) ai.y = 0;
                if (ai.y > canvas.height - ai.height) ai.y = canvas.height - ai.height;

                // Ball movement
                ball.x += ball.velocityX;
                ball.y += ball.velocityY;

                // Wall collision (Top & Bottom)
                if (ball.y - ball.radius < 0) {
                    ball.y = ball.radius;
                    ball.velocityY = -ball.velocityY;
                } else if (ball.y + ball.radius > canvas.height) {
                    ball.y = canvas.height - ball.radius;
                    ball.velocityY = -ball.velocityY;
                }

                // Paddle collision detection
                let activePaddle = (ball.x < canvas.width / 2) ? player : ai;

                if (
                    ball.x - ball.radius < activePaddle.x + activePaddle.width &&
                    ball.x + ball.radius > activePaddle.x &&
                    ball.y > activePaddle.y &&
                    ball.y < activePaddle.y + activePaddle.height
                ) {
                    // Calculate bounce angle based on where it hit the paddle
                    let collidePoint = ball.y - (activePaddle.y + activePaddle.height / 2);
                    collidePoint = collidePoint / (activePaddle.height / 2);
                    let angleRad = (Math.PI / 4) * collidePoint;

                    let direction = (ball.x < canvas.width / 2) ? 1 : -1;
                    ball.speed += 0.2; // slight speed increase on hit
                    ball.velocityX = direction * ball.speed * Math.cos(angleRad);
                    ball.velocityY = ball.speed * Math.sin(angleRad);
                }

                // Scoring
                if (ball.x - ball.radius < 0) {
                    aiScore++;
                    document.getElementById("aiScore").innerText = aiScore;
                    checkGameOver();
                    resetBall('ai');
                } else if (ball.x + ball.radius > canvas.width) {
                    playerScore++;
                    document.getElementById("playerScore").innerText = playerScore;
                    checkGameOver();
                    resetBall('player');
                }
            }

            function checkGameOver() {
                if (playerScore >= targetScore || aiScore >= targetScore) {
                    gameOver = true;
                    gameRunning = false;
                    // Send score back or notify streamlet
                    if (window.parent) {
                        window.parent.postMessage({type: 'PING_PONG_GAME_OVER', playerScore: playerScore, aiScore: aiScore}, '*');
                    }
                }
            }

            function drawRect(x, y, w, h, color) {
                ctx.fillStyle = color;
                ctx.fillRect(x, y, w, h);
            }

            function drawCircle(x, y, r, color) {
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, r, 0, Math.PI * 2, false);
                ctx.closePath();
                ctx.fill();
            }

            function drawNet() {
                for (let i = 0; i <= canvas.height; i += 15) {
                    drawRect(canvas.width / 2 - 1, i, 2, 10, "#223344");
                }
            }

            function drawText(text, x, y, color, size = '20px') {
                ctx.fillStyle = color;
                ctx.font = size + " 'Courier New'";
                ctx.textAlign = "center";
                ctx.fillText(text, x, y);
            }

            function render() {
                // Clear canvas
                drawRect(0, 0, canvas.width, canvas.height, "#000000");

                // Net
                drawNet();

                // Paddles
                drawRect(player.x, player.y, player.width, player.height, "#00ffcc");
                drawRect(ai.x, ai.y, ai.width, ai.height, "#ff0055");

                // Ball
                drawCircle(ball.x, ball.y, ball.radius, "#ffff00");

                if (!gameRunning && !gameOver) {
                    drawText("PRESS SPACE TO START", canvas.width / 2, canvas.height / 2 - 40, "#00ffcc", "24px");
                }

                if (gameOver) {
                    drawRect(0, 0, canvas.width, canvas.height, "rgba(0, 0, 0, 0.85)");
                    let winnerText = (playerScore > aiScore) ? "YOU WIN! 🎉" : "AI WINS! 🤖";
                    let color = (playerScore > aiScore) ? "#00ffcc" : "#ff0055";
                    drawText(winnerText, canvas.width / 2, canvas.height / 2 - 20, color, "36px");
                    drawText("PRESS SPACE TO PLAY AGAIN", canvas.width / 2, canvas.height / 2 + 30, "#ffffff", "18px");
                }
            }

            function gameLoop() {
                update();
                render();
                requestAnimationFrame(gameLoop);
            }

            // Start loop
            gameLoop();
        </script>
    </body>
    </html>
    """.replace("__PLAYER__", player_name).replace("__TARGET__", str(target_score)).replace("__AI_SPEED__", str(ai_speed)).replace("__BALL_SPEED__", str(ball_speed))
    
    components.html(html_code, height=560)

def main():
    st.set_page_config(
        page_title="Retro Arcade Ping Pong",
        page_icon="🏓",
        layout="wide"
    )

    # Initialize DB
    ArcadeDB.init_db()

    st.title("🏓 Retro Arcade Ping Pong")
    st.markdown("Play classic table tennis against a smart AI opponent right inside your browser! Control your paddle with **UP/DOWN** or **W/S** keys. Press **SPACE** to start or pause.")

    # Sidebar Configuration
    st.sidebar.header("⚙️ Game Settings")
    player_name = st.sidebar.text_input("Player Name", value="RetroChamp")
    difficulty = st.sidebar.selectbox("Difficulty", list(GameConfig.DIFFICULTIES.keys()), index=1)
    
    cfg = GameConfig.DIFFICULTIES[difficulty]
    
    st.sidebar.markdown(f"***")
    st.sidebar.markdown(f"**AI Speed:** {cfg['ai_speed']}")
    st.sidebar.markdown(f"**Ball Speed:** {cfg['ball_speed']}")
    st.sidebar.markdown(f"**Target Score:** {cfg['target_score']} pts")

    # Database Reset Control in Expander
    with st.sidebar.expander("🛠️ Danger Zone / Admin"):
        if st.button("Reset Leaderboard DB"):
            ArcadeDB.clear_database()
            st.success("Database wiped successfully!")
            st.rerun()

    # Global Stats Metrics
    stats = ArcadeDB.get_global_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Matches Played", stats["total_matches"])
    with col2:
        st.metric("Total Points Rally", stats["total_points_scored"])
    with col3:
        st.metric("Current Challenger", player_name)

    st.markdown("---")

    # Render Game Canvas Component
    render_ping_pong_canvas(
        ai_speed=cfg["ai_speed"],
        ball_speed=cfg["ball_speed"],
        target_score=cfg["target_score"],
        player_name=player_name
    )

    st.markdown("---")

    # Leaderboard Section
    st.subheader("🏆 Arcade Hall of Fame (Leaderboard)")
    leaderboard = ArcadeDB.get_leaderboard(limit=10)
    if leaderboard:
        st.dataframe(leaderboard, use_container_width=True)
    else:
        st.info("No matches recorded yet. Play a game to record your score on the leaderboard!")

    # Manual score registration form in case browser event message passing is intercepted
    with st.expander("📝 Manual Score Submissions / Save Match Result"):
        with st.form("manual_score_form"):
            m_player = st.text_input("Player", value=player_name)
            m_score = st.number_input("Your Score", min_value=0, max_value=20, value=cfg["target_score"])
            m_ai_score = st.number_input("AI Score", min_value=0, max_value=20, value=3)
            m_diff = st.selectbox("Difficulty Record", list(GameConfig.DIFFICULTIES.keys()), index=list(GameConfig.DIFFICULTIES.keys()).index(difficulty))
            submitted = st.form_submit_button("Submit Score to Leaderboard")
            if submitted:
                ArcadeDB.add_score(m_player, m_score, m_ai_score, m_diff)
                st.success(f"Score recorded for {m_player}!")
                st.rerun()

if __name__ == "__main__":
    main()