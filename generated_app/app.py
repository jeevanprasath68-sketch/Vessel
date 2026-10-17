import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

DB_NAME = "ping_pong_arcade.db"

# --- DATABASE ENGINE & SELF-HEALING SCHEMA ---
class DatabaseEngine:
    @staticmethod
    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # Create tables if not exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                player_score INTEGER NOT NULL,
                ai_score INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                winner TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS high_scores (
                player_name TEXT PRIMARY KEY,
                high_score INTEGER NOT NULL,
                games_played INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Defensive column check & migration for matches
        cursor.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        if "difficulty" not in columns:
            cursor.execute("ALTER TABLE matches ADD COLUMN difficulty TEXT DEFAULT 'Medium'")
            
        conn.commit()
        conn.close()

    @classmethod
    def reset_db(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS matches")
        cursor.execute(
            "DROP TABLE IF EXISTS high_scores"
        )
        conn.commit()
        conn.close()
        cls.init_db()

    @classmethod
    def save_match(cls, player_name: str, p_score: int, ai_score: int, difficulty: str) -> bool:
        try:
            conn = cls.get_connection()
            cursor = conn.cursor()
            winner = player_name if p_score > ai_score else ("AI Bot" if ai_score > p_score else "Tie")
            
            cursor.execute(
                "INSERT INTO matches (player_name, player_score, ai_score, difficulty, winner) VALUES (?, ?, ?, ?, ?)",
                (player_name, p_score, ai_score, difficulty, winner)
            )
            
            # Update high scores
            cursor.execute("SELECT high_score, games_played FROM high_scores WHERE player_name = ?", (player_name,))
            row = cursor.fetchone()
            if row:
                new_high = max(row["high_score"], p_score)
                new_games = row["games_played"] + 1
                cursor.execute(
                    "UPDATE high_scores SET high_score = ?, games_played = ?, updated_at = CURRENT_TIMESTAMP WHERE player_name = ?",
                    (new_high, new_games, player_name)
                )
            else:
                cursor.execute(
                    "INSERT INTO high_scores (player_name, high_score, games_played) VALUES (?, ?, 1)",
                    (player_name, p_score)
                )
                
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Database error: {e}")
            return False

    @classmethod
    def get_leaderboard(cls) -> pd.DataFrame:
        try:
            conn = cls.get_connection()
            df = pd.read_sql_query("SELECT player_name, high_score, games_played, updated_at FROM high_scores ORDER BY high_score DESC LIMIT 10", conn)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame(columns=["player_name", "high_score", "games_played", "updated_at"])

    @classmethod
    def get_match_history(cls) -> pd.DataFrame:
        try:
            conn = cls.get_connection()
            df = pd.read_sql_query("SELECT id, player_name, player_score, ai_score, difficulty, winner, played_at FROM matches ORDER BY played_at DESC LIMIT 20", conn)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame(columns=["id", "player_name", "player_score", "ai_score", "difficulty", "winner", "played_at"])


# --- BUSINESS LOGIC / GAME VALIDATOR --- 
class GameValidator:
    @staticmethod
    def validate_score(player_score: int, ai_score: int) -> bool:
        if not isinstance(player_score, int) or not isinstance(ai_score, int):
            return False
        if player_score < 0 or ai_score < 0:
            return False
        return True

    @staticmethod
    def calculate_match_stats(df_matches: pd.DataFrame) -> Dict[str, Any]:
        if df_matches.empty:
            return {"total_matches": 0, "avg_player_score": 0.0, "player_win_rate": 0.0}
        total = len(df_matches)
        avg_score = df_matches["player_score"].mean()
        # Count matches where winner is not AI and not Tie
        wins = len(df_matches[df_matches["winner"].str.contains(r"AI|Tie", case=False, na=False) == False])
        win_rate = (wins / total) * 100 if total > 0 else 0.0
        return {
            "total_matches": total,
            "avg_player_score": round(avg_score, 1),
            "player_win_rate": round(win_rate, 1)
        }


# --- HTML/JS PONG GAME COMPONENT --- 
def get_pong_html(difficulty: str) -> str:
    # Map difficulty to AI speed/reaction
    ai_speeds = {"Easy": 0.04, "Medium": 0.07, "Hard": 0.12, "Legendary": 0.18}
    ai_speed = ai_speeds.get(difficulty, 0.07)
    winning_score = 5

    raw_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * { box-sizing: border-box; user-select: none; }
            body {
                background: #060913;
                color: #00f3ff;
                font-family: 'Courier New', Courier, monospace;
                text-align: center;
                margin: 0;
                padding: 10px 0;
                overflow: hidden;
            }
            #game-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            .arcade-header {
                font-size: 1.4rem;
                font-weight: 800;
                color: #00f3ff;
                text-shadow: 0 0 10px #00f3ff, 0 0 20px #00f3ff;
                letter-spacing: 3px;
                margin-bottom: 4px;
            }
            .instructions {
                font-size: 0.8rem;
                color: #94a3b8;
                margin-bottom: 8px;
            }
            canvas {
                border: 2px solid #00f3ff;
                box-shadow: 0 0 25px rgba(0, 243, 255, 0.35), inset 0 0 15px rgba(0, 243, 255, 0.2);
                background: #030611;
                border-radius: 8px;
                cursor: pointer;
            }
            .controls-hint {
                margin-top: 8px;
                font-size: 0.8rem;
                color: #cbd5e1;
            }
            .key {
                background: #1e293b;
                border: 1px solid #334155;
                padding: 2px 7px;
                border-radius: 4px;
                color: #00f3ff;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div id="game-container">
            <div class="arcade-header">&#127918; NEON CYBER PONG ARCADE</div>
            <div class="instructions">Difficulty: __DIFFICULTY__ | First to __WINNING_SCORE__ Wins | Sound &amp; Mouse Enabled</div>
            <canvas id="pongCanvas" width="700" height="400"></canvas>
            <div class="controls-hint">
                Controls: Drag <span class="key">Mouse/Touch</span> or use <span class="key">&#9650;</span> <span class="key">&#9660;</span> / <span class="key">W/S</span> &bull; <span class="key">P</span> to Pause &bull; Click Mute icon to toggle audio
            </div>
        </div>

        <script>
            const canvas = document.getElementById("pongCanvas");
            const ctx = canvas.getContext("2d");

            // Web Audio Synthesizer (Procedural Sound Engine)
            const AudioEngine = {
                ctx: null,
                muted: false,
                init() {
                    if (!this.ctx) {
                        const AC = window.AudioContext || window.webkitAudioContext;
                        if (AC) this.ctx = new AC();
                    }
                    if (this.ctx && this.ctx.state === "suspended") this.ctx.resume();
                },
                playTone(freq, type, duration, endFreq) {
                    if (this.muted) return;
                    try {
                        this.init();
                        if (!this.ctx) return;
                        const osc = this.ctx.createOscillator();
                        const gain = this.ctx.createGain();
                        osc.type = type || "sine";
                        osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
                        if (endFreq) osc.frequency.exponentialRampToValueAtTime(endFreq, this.ctx.currentTime + duration);
                        gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
                        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
                        osc.connect(gain);
                        gain.connect(this.ctx.destination);
                        osc.start();
                        osc.stop(this.ctx.currentTime + duration);
                    } catch(e) {}
                },
                hit() { this.playTone(380, "square", 0.06, 180); },
                wall() { this.playTone(280, "sine", 0.05, 360); },
                score() {
                    this.playTone(523, "sine", 0.12);
                    setTimeout(() => this.playTone(659, "sine", 0.18), 100);
                    setTimeout(() => this.playTone(784, "sine", 0.25), 200);
                },
                gameOver() { this.playTone(300, "sawtooth", 0.35, 120); }
            };

            // Game State Machine: 0 = MENU, 1 = PLAYING, 2 = PAUSED, 3 = GAME_OVER
            let gameState = 0;
            let winnerText = "";
            let screenShake = 0;

            // Background Stardust Particles
            const stars = [];
            for (let i = 0; i < 45; i++) {
                stars.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    size: Math.random() * 1.8 + 0.5,
                    alpha: Math.random() * 0.7 + 0.2,
                    speed: Math.random() * 0.4 + 0.1
                });
            }

            // Explosion Sparks Particle Engine
            let particles = [];
            function spawnSparks(x, y, color, count = 16) {
                for (let i = 0; i < count; i++) {
                    const angle = Math.random() * Math.PI * 2;
                    const speed = Math.random() * 4 + 1.5;
                    particles.push({
                        x: x,
                        y: y,
                        vx: Math.cos(angle) * speed,
                        vy: Math.sin(angle) * speed,
                        radius: Math.random() * 2.5 + 1,
                        alpha: 1,
                        decay: Math.random() * 0.03 + 0.02,
                        color: color
                    });
                }
            }

            // Game entities
            const ball = {
                x: canvas.width / 2,
                y: canvas.height / 2,
                radius: 8,
                speed: 5.5,
                velocityX: 5.5,
                velocityY: 5.5,
                color: "#ffe600"
            };

            const player = {
                x: 14,
                y: canvas.height / 2 - 42,
                width: 14,
                height: 84,
                score: 0,
                color: "#00f3ff"
            };

            const ai = {
                x: canvas.width - 28,
                y: canvas.height / 2 - 42,
                width: 14,
                height: 84,
                score: 0,
                color: "#ff007f"
            };

            // Controls
            let upPressed = false;
            let downPressed = false;

            window.addEventListener("keydown", (e) => {
                AudioEngine.init();
                if (e.key === "ArrowUp" || e.key === "w" || e.key === "W") {
                    upPressed = true;
                    e.preventDefault();
                }
                if (e.key === "ArrowDown" || e.key === "s" || e.key === "S") {
                    downPressed = true;
                    e.preventDefault();
                }
                if (e.code === "Space") {
                    e.preventDefault();
                    if (gameState === 0) gameState = 1;
                    else if (gameState === 3) resetMatch();
                }
                if (e.key === "p" || e.key === "P" || e.key === "Escape") {
                    if (gameState === 1) gameState = 2;
                    else if (gameState === 2) gameState = 1;
                }
            });

            window.addEventListener("keyup", (e) => {
                if (e.key === "ArrowUp" || e.key === "w" || e.key === "W") upPressed = false;
                if (e.key === "ArrowDown" || e.key === "s" || e.key === "S") downPressed = false;
            });

            // Mouse & Touch Controls
            canvas.addEventListener("mousemove", (e) => {
                const rect = canvas.getBoundingClientRect();
                const mouseY = (e.clientY - rect.top) * (canvas.height / rect.height);
                player.y = Math.max(0, Math.min(canvas.height - player.height, mouseY - player.height / 2));
            });

            canvas.addEventListener("touchmove", (e) => {
                e.preventDefault();
                const rect = canvas.getBoundingClientRect();
                const touchY = (e.touches[0].clientY - rect.top) * (canvas.height / rect.height);
                player.y = Math.max(0, Math.min(canvas.height - player.height, touchY - player.height / 2));
            }, { passive: false });

            canvas.addEventListener("click", (e) => {
                AudioEngine.init();
                const rect = canvas.getBoundingClientRect();
                const clickX = (e.clientX - rect.left) * (canvas.width / rect.width);
                const clickY = (e.clientY - rect.top) * (canvas.height / rect.height);

                // Check Mute button click (top-right corner: x: 650..690, y: 10..40)
                if (clickX >= 640 && clickX <= 690 && clickY >= 10 && clickY <= 40) {
                    AudioEngine.muted = !AudioEngine.muted;
                    return;
                }

                if (gameState === 0) gameState = 1;
                else if (gameState === 2) gameState = 1;
                else if (gameState === 3) resetMatch();
            });

            function collision(b, p) {
                return (
                    b.x + b.radius > p.x &&
                    b.x - b.radius < p.x + p.width &&
                    b.y + b.radius > p.y &&
                    b.y - b.radius < p.y + p.height
                );
            }

            function resetBall(direction) {
                ball.x = canvas.width / 2;
                ball.y = canvas.height / 2;
                ball.speed = 5.5;
                ball.velocityX = (direction || 1) * ball.speed;
                ball.velocityY = (Math.random() > 0.5 ? 1 : -1) * (Math.random() * 3 + 3);
            }

            function resetMatch() {
                player.score = 0;
                ai.score = 0;
                gameState = 1;
                resetBall(1);
            }

            function update() {
                // Update stars
                for (let star of stars) {
                    star.x -= star.speed;
                    if (star.x < 0) star.x = canvas.width;
                }

                // Update particles
                for (let i = particles.length - 1; i >= 0; i--) {
                    const p = particles[i];
                    p.x += p.vx;
                    p.y += p.vy;
                    p.alpha -= p.decay;
                    if (p.alpha <= 0) particles.splice(i, 1);
                }

                if (screenShake > 0) screenShake--;

                if (gameState !== 1) return;

                // Keyboard Movement
                if (upPressed && player.y > 0) player.y -= 7.5;
                if (downPressed && player.y < canvas.height - player.height) player.y += 7.5;

                // AI movement with smart tracking
                const aiTarget = ball.y - ai.height / 2;
                ai.y += (aiTarget - ai.y) * __AI_SPEED__;
                ai.y = Math.max(0, Math.min(canvas.height - ai.height, ai.y));

                // Ball Movement
                ball.x += ball.velocityX;
                ball.y += ball.velocityY;

                // Wall Collision (Top and Bottom)
                if (ball.y - ball.radius <= 0) {
                    ball.y = ball.radius;
                    ball.velocityY = Math.abs(ball.velocityY);
                    AudioEngine.wall();
                    spawnSparks(ball.x, ball.y, "#ffe600", 8);
                } else if (ball.y + ball.radius >= canvas.height) {
                    ball.y = canvas.height - ball.radius;
                    ball.velocityY = -Math.abs(ball.velocityY);
                    AudioEngine.wall();
                    spawnSparks(ball.x, ball.y, "#ffe600", 8);
                }

                // Paddle Collision
                const activePaddle = (ball.x < canvas.width / 2) ? player : ai;
                if (collision(ball, activePaddle)) {
                    AudioEngine.hit();
                    const collidePoint = (ball.y - (activePaddle.y + activePaddle.height / 2)) / (activePaddle.height / 2);
                    const angleRad = (Math.PI / 4) * Math.max(-1, Math.min(1, collidePoint));
                    const direction = (ball.x < canvas.width / 2) ? 1 : -1;

                    ball.speed = Math.min(ball.speed + 0.35, 12);
                    ball.velocityX = direction * ball.speed * Math.cos(angleRad);
                    ball.velocityY = ball.speed * Math.sin(angleRad);
                    spawnSparks(ball.x, ball.y, activePaddle.color, 16);
                    screenShake = 3;
                }

                // Scoring
                if (ball.x - ball.radius < 0) {
                    ai.score++;
                    AudioEngine.score();
                    spawnSparks(ball.x, ball.y, ai.color, 25);
                    screenShake = 6;
                    if (ai.score >= __WINNING_SCORE__) {
                        gameState = 3;
                        winnerText = "AI WINS! 🤖";
                        AudioEngine.gameOver();
                    } else {
                        resetBall(1);
                    }
                } else if (ball.x + ball.radius > canvas.width) {
                    player.score++;
                    AudioEngine.score();
                    spawnSparks(ball.x, ball.y, player.color, 25);
                    screenShake = 6;
                    if (player.score >= __WINNING_SCORE__) {
                        gameState = 3;
                        winnerText = "PLAYER WINS! 🏆";
                        AudioEngine.score();
                    } else {
                        resetBall(-1);
                    }
                }
            }

            function render() {
                ctx.save();
                if (screenShake > 0) {
                    const dx = (Math.random() - 0.5) * 6;
                    const dy = (Math.random() - 0.5) * 6;
                    ctx.translate(dx, dy);
                }

                // Clear canvas with deep space gradient
                const bgGrad = ctx.createLinearGradient(0, 0, 0, canvas.height);
                bgGrad.addColorStop(0, "#050814");
                bgGrad.addColorStop(1, "#030409");
                ctx.fillStyle = bgGrad;
                ctx.fillRect(0, 0, canvas.width, canvas.height);

                // Draw background stars
                for (let star of stars) {
                    ctx.fillStyle = "rgba(255, 255, 255, " + star.alpha + ")";
                    ctx.beginPath();
                    ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
                    ctx.fill();
                }

                // Draw center net with glowing dashed line
                ctx.save();
                ctx.shadowBlur = 8;
                ctx.shadowColor = "rgba(0, 243, 255, 0.4)";
                ctx.strokeStyle = "rgba(0, 243, 255, 0.25)";
                ctx.lineWidth = 2;
                ctx.setLineDash([8, 8]);
                ctx.beginPath();
                ctx.moveTo(canvas.width / 2, 0);
                ctx.lineTo(canvas.width / 2, canvas.height);
                ctx.stroke();
                ctx.restore();

                // Draw Scores
                ctx.save();
                ctx.font = "bold 44px 'Courier New', monospace";
                ctx.textAlign = "center";
                ctx.shadowBlur = 12;
                ctx.shadowColor = "#00f3ff";
                ctx.fillStyle = "#00f3ff";
                ctx.fillText(player.score, canvas.width / 4, 65);
                ctx.shadowColor = "#ff007f";
                ctx.fillStyle = "#ff007f";
                ctx.fillText(ai.score, 3 * canvas.width / 4, 65);
                ctx.restore();

                // Draw Player Paddle (Neon Cyan Glow)
                ctx.save();
                ctx.shadowBlur = 15;
                ctx.shadowColor = player.color;
                ctx.fillStyle = player.color;
                ctx.fillRect(player.x, player.y, player.width, player.height);
                ctx.restore();

                // Draw AI Paddle (Neon Magenta Glow)
                ctx.save();
                ctx.shadowBlur = 15;
                ctx.shadowColor = ai.color;
                ctx.fillStyle = ai.color;
                ctx.fillRect(ai.x, ai.y, ai.width, ai.height);
                ctx.restore();

                // Draw Ball (Neon Yellow Glow)
                ctx.save();
                ctx.shadowBlur = 18;
                ctx.shadowColor = ball.color;
                ctx.fillStyle = ball.color;
                ctx.beginPath();
                ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();

                // Draw Particles
                for (let p of particles) {
                    ctx.save();
                    ctx.shadowBlur = 8;
                    ctx.shadowColor = p.color;
                    ctx.fillStyle = p.color;
                    ctx.globalAlpha = Math.max(0, p.alpha);
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                }

                // Draw Sound Mute Toggle Icon at top-right
                ctx.save();
                ctx.font = "16px sans-serif";
                ctx.textAlign = "right";
                ctx.fillStyle = AudioEngine.muted ? "#64748b" : "#00f3ff";
                ctx.fillText(AudioEngine.muted ? "🔇 MUTED" : "🔊 SOUND", canvas.width - 15, 28);
                ctx.restore();

                // STATE OVERLAYS
                if (gameState === 0) {
                    // Menu / Title Screen
                    ctx.fillStyle = "rgba(4, 7, 18, 0.85)";
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.save();
                    ctx.textAlign = "center";
                    ctx.shadowBlur = 20;
                    ctx.shadowColor = "#00f3ff";
                    ctx.fillStyle = "#00f3ff";
                    ctx.font = "bold 32px 'Courier New', monospace";
                    ctx.fillText("NEON CYBER PONG", canvas.width / 2, canvas.height / 2 - 40);

                    const pulse = Math.abs(Math.sin(Date.now() / 350));
                    ctx.shadowBlur = 10 * pulse;
                    ctx.fillStyle = "#ffe600";
                    ctx.font = "bold 16px 'Courier New', monospace";
                    ctx.fillText("CLICK OR PRESS SPACE TO START", canvas.width / 2, canvas.height / 2 + 15);

                    ctx.fillStyle = "#94a3b8";
                    ctx.font = "12px 'Courier New', monospace";
                    ctx.fillText("Move: Mouse Drag or Arrow Keys / W-S | P: Pause", canvas.width / 2, canvas.height / 2 + 55);
                    ctx.restore();
                } else if (gameState === 2) {
                    // Paused Screen
                    ctx.fillStyle = "rgba(4, 7, 18, 0.75)";
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.save();
                    ctx.textAlign = "center";
                    ctx.shadowBlur = 15;
                    ctx.shadowColor = "#ffe600";
                    ctx.fillStyle = "#ffe600";
                    ctx.font = "bold 28px 'Courier New', monospace";
                    ctx.fillText("PAUSED", canvas.width / 2, canvas.height / 2 - 10);
                    ctx.fillStyle = "#94a3b8";
                    ctx.font = "14px 'Courier New', monospace";
                    ctx.fillText("PRESS 'P' OR CLICK TO RESUME", canvas.width / 2, canvas.height / 2 + 30);
                    ctx.restore();
                } else if (gameState === 3) {
                    // Game Over Screen
                    ctx.fillStyle = "rgba(4, 7, 18, 0.85)";
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.save();
                    ctx.textAlign = "center";
                    ctx.shadowBlur = 20;
                    ctx.shadowColor = player.score >= __WINNING_SCORE__ ? "#00f3ff" : "#ff007f";
                    ctx.fillStyle = player.score >= __WINNING_SCORE__ ? "#00f3ff" : "#ff007f";
                    ctx.font = "bold 34px 'Courier New', monospace";
                    ctx.fillText(winnerText, canvas.width / 2, canvas.height / 2 - 40);

                    ctx.shadowBlur = 8;
                    ctx.fillStyle = "#ffffff";
                    ctx.font = "bold 18px 'Courier New', monospace";
                    ctx.fillText("FINAL SCORE: " + player.score + " - " + ai.score, canvas.width / 2, canvas.height / 2 + 5);

                    ctx.fillStyle = "#ffe600";
                    ctx.font = "bold 15px 'Courier New', monospace";
                    ctx.fillText("PRESS SPACE OR CLICK TO PLAY AGAIN", canvas.width / 2, canvas.height / 2 + 45);

                    ctx.fillStyle = "#94a3b8";
                    ctx.font = "12px 'Courier New', monospace";
                    ctx.fillText("Record your score below in the Leaderboard form!", canvas.width / 2, canvas.height / 2 + 75);
                    ctx.restore();
                }

                ctx.restore();
            }

            function gameLoop() {
                update();
                render();
                requestAnimationFrame(gameLoop);
            }

            gameLoop();
        </script>
    </body>
    </html>
    """

    return raw_html.replace("__DIFFICULTY__", difficulty).replace("__AI_SPEED__", str(ai_speed)).replace("__WINNING_SCORE__", str(winning_score))


# --- STREAMLIT USER INTERFACE --- 
def main():
    st.set_page_config(
        page_title="Retro Arcade Ping Pong",
        page_icon="🏓",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize Database
    DatabaseEngine.init_db()

    # Custom Retro Styling
    st.markdown(
        """
        <style>
            .main-title {
                font-size: 2.5rem;
                color: #00ffcc;
                text-shadow: 0 0 12px rgba(0, 255, 204, 0.6);
                font-family: 'Courier New', Courier, monospace;
                font-weight: bold;
                margin-bottom: 0px;
            }
            .subtitle {
                color: #8b949e;
                font-size: 1.1rem;
                margin-bottom: 20px;
            }
            .metric-card {
                background-color: #161b22;
                border: 1px solid #30363d;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="main-title">🏓 RETRO ARCADE PING PONG</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Classic 2-Player arcade showdown against intelligent AI. Built with Streamlit & HTML5 Canvas.</div>', unsafe_allow_html=True)

    # Sidebar Configuration & Controls
    st.sidebar.markdown("## 🎮 Arcade Settings")
    player_name = st.sidebar.text_input("Player Tag / Name", value="Player1", max_chars=20)
    difficulty = st.sidebar.selectbox("AI Difficulty", ["Easy", "Medium", "Hard", "Legendary"], index=1)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 Match Saver")
    st.sidebar.info("Finished a game? Log your score to the arcade high-score board below!")
    
    with st.sidebar.form("save_form"):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            p_score_input = st.number_input("Your Score", min_value=0, max_value=10, value=5)
        with col_s2:
            ai_score_input = st.number_input("AI Score", min_value=0, max_value=10, value=2)
        
        submitted = st.form_submit_button("📥 Save Match Result")
        if submitted:
            if GameValidator.validate_score(p_score_input, ai_score_input):
                success = DatabaseEngine.save_match(player_name, p_score_input, ai_score_input, difficulty)
                if success:
                    st.sidebar.success(f"Score saved for {player_name}!")
                else:
                    st.sidebar.error("Failed to save score.")
            else:
                st.sidebar.error("Invalid score values provided.")

    # Database Maintenance
    with st.sidebar.expander("⚙️ Database & Maintenance"):
        if st.button("🗑️ Reset Arcade Database", type="primary"):
            DatabaseEngine.reset_db()
            st.sidebar.success("Database successfully wiped and re-initialized!")
            st.rerun()

    # Layout: Game Window & Stats Dashboard
    col_game, col_dash = st.columns([2.2, 1])

    with col_game:
        st.markdown("### 🕹️ Live Arena")
        # Embed HTML/JS Game inside Streamlit Component
        from streamlit.components.v1 import html
        html(get_pong_html(difficulty), height=480, scrolling=False)

    with col_dash:
        st.markdown("### 🏆 Arcade Leaderboard")
        df_leaderboard = DatabaseEngine.get_leaderboard()
        if not df_leaderboard.empty:
            st.dataframe(df_leaderboard, use_container_width=True, hide_index=True)
        else:
            st.info("No high scores recorded yet. Be the first!")

        st.markdown("### 📈 Career Statistics")
        df_matches = DatabaseEngine.get_match_history()
        stats = GameValidator.calculate_match_stats(df_matches)
        
        m1, m2 = st.columns(2)
        m1.metric("Total Matches", stats["total_matches"])
        m2.metric(
            "Win Rate", f"{stats['player_win_rate']}%")

    # Full Match History Table
    st.markdown("---")
    st.markdown("### 📜 Recent Match History")
    if not df_matches.empty:
        st.dataframe(df_matches, use_container_width=True, hide_index=True)
    else:
        st.markdown("*No recent match history available.*")


if __name__ == "__mainmain__" or __name__ == "__main__":
    main()