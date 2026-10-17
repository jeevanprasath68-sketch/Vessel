import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
from datetime import datetime

# ==========================================
# BACKEND BUSINESS LOGIC & DATABASE ENGINE
# ==========================================

class GameConfig:
    DIFFICULTIES = {
        "Casual": {"speed": 4.0, "paddle_width": 120, "lives": 5, "multiplier": 1.0},
        "Standard": {"speed": 6.0, "paddle_width": 100, "lives": 3, "multiplier": 1.5},
        "Pro": {"speed": 8.0, "paddle_width": 80, "lives": 2, "multiplier": 2.0},
        "Impossible": {"speed": 10.5, "paddle_width": 65, "lives": 1, "multiplier": 3.0}
    }

class LeaderboardDB:
    def __init__(self, db_path="brick_breaker.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS high_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        
        # Self-healing schema check
        cursor.execute("PRAGMA table_info(high_scores)")
        columns = [col[1] for col in cursor.fetchall()]
        if "difficulty" not in columns:
            cursor.execute("ALTER TABLE high_scores ADD COLUMN difficulty TEXT DEFAULT 'Standard'")
            conn.commit()
        if "created_at" not in columns:
            cursor.execute("ALTER TABLE high_scores ADD COLUMN created_at TEXT DEFAULT ''")
            conn.commit()
        conn.close()

    def add_score(self, player_name: str, score: int, difficulty: str):
        if not player_name.strip():
            player_name = "Anonymous"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO high_scores (player_name, score, difficulty, created_at) VALUES (?, ?, ?, ?)",
            (player_name.strip(), int(score), difficulty, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()

    def get_top_scores(self, limit=10, difficulty=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if difficulty and difficulty != "All":
            cursor.execute(
                "SELECT player_name, score, difficulty, created_at FROM high_scores WHERE difficulty = ? ORDER BY score DESC LIMIT ?",
                (difficulty, limit)
            )
        else:
            cursor.execute(
                "SELECT player_name, score, difficulty, created_at FROM high_scores ORDER BY score DESC LIMIT ?",
                (limit,)
            )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_stats(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), MAX(score), AVG(score) FROM high_scores")
        row = cursor.fetchone()
        conn.close()
        if row and row[0] > 0:
            return {"total_games": row[0], "max_score": row[1] or 0, "avg_score": int(row[2] or 0)}
        return {"total_games": 0, "max_score": 0, "avg_score": 0}

    def reset_leaderboard(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM high_scores")
        conn.commit()
        conn.close()

# ==========================================
# HTML5 CANVAS GAME FRONTEND
# ==========================================

def get_game_html(difficulty="Standard"): 
    config = GameConfig.DIFFICULTIES.get(difficulty, GameConfig.DIFFICULTIES["Standard"])
    speed = config["speed"]
    paddle_w = config["paddle_width"]
    lives = config["lives"]
    mult = config["multiplier"]

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ background: #060814; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; font-family: 'Courier New', monospace; }}
        canvas {{ background: #0a0e1a; box-shadow: 0 0 30px #00f3ff44, inset 0 0 20px #000000; border: 2px solid #00f3ff88; border-radius: 8px; cursor: none; }}
        #ui-overlay {{ position: absolute; top: 10px; color: #fff; font-size: 14px; pointer-events: none; text-shadow: 0 0 8px #00f3ff; }}
    </style>
    </head>
    <body>
    <canvas id="gameCanvas" width="800" height="560"></canvas>
    <script>
    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d');

    const INIT_SPEED = {speed};
    const PADDLE_W_INIT = {paddle_w};
    const INIT_LIVES = {lives};
    const SCORE_MULT = {mult};

    const AudioEngine = {{
        ctx: null,
        muted: false,
        init() {{
            if (!this.ctx) {{
                const AC = window.AudioContext || window.webkitAudioContext;
                if (AC) this.ctx = new AC();
            }}
            if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
        }},
        playTone(freq, type, duration, endFreq) {{
            if (this.muted) return;
            try {{
                this.init();
                if (!this.ctx) return;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = type || 'sine';
                osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
                if (endFreq) osc.frequency.exponentialRampToValueAtTime(endFreq, this.ctx.currentTime + duration);
                gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start();
                osc.stop(this.ctx.currentTime + duration);
            }} catch(e) {{}}
        }},
        hit() {{ this.playTone(440, 'square', 0.05, 220); }},
        paddleHit() {{ this.playTone(300, 'triangle', 0.08, 450); }},
        score() {{ this.playTone(523, 'sine', 0.08); setTimeout(() => this.playTone(659, 'sine', 0.12), 60); }},
        powerup() {{ this.playTone(784, 'sine', 0.1, 1046); }},
        explode() {{ this.playTone(150, 'sawtooth', 0.2, 50); }},
        laser() {{ this.playTone(880, 'square', 0.06, 440); }},
        gameOver() {{ this.playTone(220, 'sawtooth', 0.3, 110); }}
    }};

    let gameState = 'START';
    let score = 0;
    let lives = INIT_LIVES;
    let level = 1;
    let screenShake = 0;

    let paddle = {{
        x: canvas.width / 2 - PADDLE_W_INIT / 2,
        y: canvas.height - 35,
        w: PADDLE_W_INIT,
        h: 14,
        dx: 0,
        speed: 9,
        laserTimer: 0
    }};

    let ball = {{
        x: canvas.width / 2,
        y: canvas.height - 60,
        r: 8,
        dx: INIT_SPEED * 0.7,
        dy: -INIT_SPEED,
        speed: INIT_SPEED,
        sticky: false
    }};

    let bricks = [];
    let particles = [];
    let powerups = [];
    let lasers = [];
    let stars = [];

    for(let i=0; i<60; i++) {{
        stars.push({{
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 2,
            speed: 0.2 + Math.random() * 0.8
        }});
    }};

    function initBricks() {{
        bricks = [];
        const rows = 5;
        const cols = 9;
        const padding = 10;
        const offsetTop = 50;
        const offsetLeft = 45;
        const width = (canvas.width - (offsetLeft * 2) - (padding * (cols - 1))) / cols;
        const height = 22;

        const colors = ['#ff007f', '#ff7f00', '#ffe600', '#00ff66', '#00f3ff'];

        for(let r=0; r<rows; r++) {{
            for(let c=0; c<cols; c++) {{
                let hasPower = Math.random() < 0.18;
                let pType = ['laser', 'expand', 'multi', 'life'][Math.floor(Math.random()*4)];
                bricks.push({{
                    x: offsetLeft + c * (width + padding),
                    y: offsetTop + r * (height + padding),
                    w: width,
                    h: height,
                    status: 1,
                    color: colors[r],
                    hasPower: hasPower,
                    powerType: pType,
                    hp: r === 0 ? 2 : 1
                }});
            }}
        }}
    }}

    let keys = {{}};
    window.addEventListener('keydown', e => {{
        AudioEngine.init();
        if(['Space', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.code)) e.preventDefault();
        keys[e.code] = true;
        if(e.code === 'Space') {{
            if(gameState === 'START' || gameState === 'GAMEOVER' || gameState === 'VICTORY') {{
                resetGame();
                gameState = 'PLAYING';
            }} else if(ball.sticky) {{
                ball.sticky = false;
                ball.dy = -ball.speed;
            }}
        }}
        if(e.code === 'KeyP') {{
            if(gameState === 'PLAYING') gameState = 'PAUSED';
            else if(gameState === 'PAUSED') gameState = 'PLAYING';
        }}
    }});

    window.addEventListener('keyup', e => {{ keys[e.code] = false; }});
    canvas.addEventListener('mousemove', e => {{
        AudioEngine.init();
        const rect = canvas.getBoundingClientRect();
        let mouseX = e.clientX - rect.left;
        paddle.x = mouseX - paddle.w / 2;
        if(paddle.x < 0) paddle.x = 0;
        if(paddle.x + paddle.w > canvas.width) paddle.x = canvas.width - paddle.w;

        if(ball.sticky) {{
            ball.x = paddle.x + paddle.w / 2;
        }}
    }});

    canvas.addEventListener('mousedown', () => {{
        AudioEngine.init();
        if(gameState === 'START' || gameState === 'GAMEOVER' || gameState === 'VICTORY') {{
            resetGame();
            gameState = 'PLAYING';
        }} else if(ball.sticky) {{
            ball.sticky = false;
            ball.dy = -ball.speed;
        }} else if(paddle.laserTimer > 0) {{
            lasers.push({{x: paddle.x + 12, y: paddle.y, w: 4, h: 14}});
            lasers.push({{x: paddle.x + paddle.w - 16, y: paddle.y, w: 4, h: 14}});
            AudioEngine.laser();
        }}
    }});

    function resetGame() {{
        score = 0;
        lives = INIT_LIVES;
        level = 1;
        paddle.w = PADDLE_W_INIT;
        paddle.laserTimer = 0;
        resetBall();
        initBricks();
    }}

    function resetBall() {{
        ball.x = paddle.x + paddle.w / 2;
        ball.y = paddle.y - 12;
        ball.speed = INIT_SPEED + (level - 1) * 0.8;
        ball.dx = ball.speed * (Math.random() > 0.5 ? 0.6 : -0.6);
        ball.dy = -ball.speed;
        ball.sticky = true;
    }}

    function spawnParticles(x, y, color) {{
        for(let i=0; i<16; i++) {{
            let angle = Math.random() * Math.PI * 2;
            let speed = 1 + Math.random() * 5;
            particles.push({{
                x: x,
                y: y,
                dx: Math.cos(angle) * speed,
                dy: Math.sin(angle) * speed,
                r: 2 + Math.random() * 3,
                color: color,
                alpha: 1.0,
                decay: 0.02 + Math.random() * 0.03
            }});
        }}
    }}

    function spawnPowerup(x, y, type) {{
        powerups.push({{
            x: x,
            y: y,
            w: 26,
            h: 14,
            type: type,
            dy: 2.2
        }});
    }}

    initBricks();

    let lastTime = performance.now();

    function gameLoop(now) {{
        const dt = Math.min((now - lastTime) / 1000, 0.1);
        lastTime = now;

        update(dt);
        render();

        requestAnimationFrame(gameLoop);
    }}

    function update(dt) {{
        if(gameState !== 'PLAYING') return;

        if(screenShake > 0) screenShake -= dt * 15;

        if(keys['ArrowLeft'] || keys['KeyA']) paddle.x -= paddle.speed;
        if(keys['ArrowRight'] || keys['KeyD']) paddle.x += paddle.speed;
        if(paddle.x < 0) paddle.x = 0;
        if(paddle.x + paddle.w > canvas.width) paddle.x = canvas.width - paddle.w;

        if(ball.sticky) {{
            ball.x = paddle.x + paddle.w / 2;
        }} else {{
            ball.x += ball.dx;
            ball.y += ball.dy;

            if(ball.x - ball.r < 0) {{ ball.x = ball.r; ball.dx *= -1; AudioEngine.hit(); }}
            if(ball.x + ball.r > canvas.width) {{ ball.x = canvas.width - ball.r; ball.dx *= -1; AudioEngine.hit(); }}
            if(ball.y - ball.r < 0) {{ ball.y = ball.r; ball.dy *= -1; AudioEngine.hit(); }}

            if(ball.y > canvas.height) {{
                lives--;
                screenShake = 5;
                AudioEngine.gameOver();
                if(lives <= 0) {{
                    gameState = 'GAMEOVER';
                }} else {{
                    resetBall();
                }}
            }}

            if(
                ball.y + ball.r >= paddle.y &&
                ball.y - ball.r <= paddle.y + paddle.h &&
                ball.x >= paddle.x &&
                ball.x <= paddle.x + paddle.w
            ) {{
                AudioEngine.paddleHit();
                let hitPos = (ball.x - (paddle.x + paddle.w / 2)) / (paddle.w / 2);
                let angle = hitPos * (Math.PI / 3);
                let currentSpeed = Math.sqrt(ball.dx * ball.dx + ball.dy * ball.dy);
                ball.dx = currentSpeed * Math.sin(angle);
                ball.dy = -Math.abs(currentSpeed * Math.cos(angle));
                ball.y = paddle.y - ball.r;
            }}

            let activeBricks = 0;
            for(let b of bricks) {{
                if(b.status === 1) {{
                    activeBricks++;
                    if(
                        ball.x + ball.r > b.x &&
                        ball.x - ball.r < b.x + b.w &&
                        ball.y + ball.r > b.y &&
                        ball.y - ball.r < b.y + b.h
                    ) {{
                        b.hp--;
                        if(b.hp <= 0) {{
                            b.status = 0;
                            score += Math.round(10 * SCORE_MULT);
                            AudioEngine.score();
                            spawnParticles(b.x + b.w/2, b.y + b.h/2, b.color);
                            if(b.hasPower) spawnPowerup(b.x + b.w/2, b.y + b.h/2, b.powerType);
                        }} else {{
                            AudioEngine.hit();
                        }}
                        ball.dy *= -1;
                    }}
                }}
            }}

            if(activeBricks === 0) {{
                level++;
                AudioEngine.score();
                initBricks();
                resetBall();
            }}
        }}

        if(paddle.laserTimer > 0) paddle.laserTimer -= dt;

        for(let i = lasers.length - 1; i >= 0; i--) {{
            lasers[i].y -= 9;
            if(lasers[i].y < 0) {{
                lasers.splice(i, 1);
                continue;
            }}
            for(let b of bricks) {{
                if(b.status === 1 &&
                   lasers[i].x > b.x && lasers[i].x < b.x + b.w &&
                   lasers[i].y > b.y && lasers[i].y < b.y + b.h) {{
                    b.status = 0;
                    score += Math.round(10 * SCORE_MULT);
                    AudioEngine.score();
                    spawnParticles(b.x + b.w/2, b.y + b.h/2, b.color);
                    lasers.splice(i, 1);
                    break;
                }}
            }}
        }}

        for(let i = powerups.length - 1; i >= 0; i--) {{
            let p = powerups[i];
            p.y += p.dy;
            if(
                p.y + p.h >= paddle.y &&
                p.y <= paddle.y + paddle.h &&
                p.x + p.w >= paddle.x &&
                p.x <= paddle.x + paddle.w
            ) {{
                AudioEngine.powerup();
                if(p.type === 'expand') {{
                    paddle.w = Math.min(paddle.w + 30, 160);
                }} else if(p.type === 'laser') {{
                    paddle.laserTimer = 12;
                }} else if(p.type === 'life') {{
                    lives++;
                }} else if(p.type === 'multi') {{
                    ball.speed *= 1.1;
                }}
                powerups.splice(i, 1);
            }} else if(p.y > canvas.height) {{
                powerups.splice(i, 1);
            }}
        }}

        for(let i = particles.length - 1; i >= 0; i--) {{
            let pt = particles[i];
            pt.x += pt.dx;
            pt.y += pt.dy;
            pt.alpha -= pt.decay;
            if(pt.alpha <= 0) particles.splice(i, 1);
        }}

        for(let s of stars) {{
            s.y += s.speed;
            if(s.y > canvas.height) s.y = 0;
        }}
    }}

    function render() {{
        ctx.save();
        if(screenShake > 0) {{
            let shakeX = (Math.random() - 0.5) * screenShake;
            let shakeY = (Math.random() - 0.5) * screenShake;
            ctx.translate(shakeX, shakeY);
        }}

        ctx.fillStyle = '#0a0e1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = '#ffffff44';
        for(let s of stars) {{
            ctx.fillRect(s.x, s.y, s.size, s.size);
        }}

        for(let b of bricks) {{
            if(b.status === 1) {{
                ctx.save();
                ctx.shadowBlur = 10;
                ctx.shadowColor = b.color;
                ctx.fillStyle = b.color;
                ctx.fillRect(b.x, b.y, b.w, b.h);
                
                ctx.fillStyle = '#ffffff33';
                ctx.fillRect(b.x + 2, b.y + 2, b.w - 4, 4);
                if(b.hp > 1) {{
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = 1.5;
                    ctx.strokeRect(b.x + 3, b.y + 3, b.w - 6, b.h - 6);
                }}
                ctx.restore();
            }}
        }}

        for(let p of powerups) {{
            ctx.save();
            ctx.shadowBlur = 12;
            ctx.shadowColor = '#ffe600';
            ctx.fillStyle = '#ffe600';
            ctx.fillRect(p.x, p.y, p.w, p.h);
            ctx.fillStyle = '#000';
            ctx.font = 'bold 10px Courier New';
            ctx.fillText(p.type.toUpperCase().substring(0,3), p.x + 3, p.y + 11);
            ctx.restore();
        }}

        ctx.save();
        ctx.shadowBlur = 12;
        ctx.shadowColor = '#00f3ff';
        ctx.fillStyle = '#00f3ff';
        for(let l of lasers) {{
            ctx.fillRect(l.x, l.y, l.w, l.h);
        }}
        ctx.restore();

        ctx.save();
        ctx.shadowBlur = 15;
        ctx.shadowColor = paddle.laserTimer > 0 ? '#ff007f' : '#00f3ff';
        ctx.fillStyle = paddle.laserTimer > 0 ? '#ff007f' : '#00f3ff';
        ctx.fillRect(paddle.x, paddle.y, paddle.w, paddle.h);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(paddle.x + 8, paddle.y + 2, paddle.w - 16, 3);
        ctx.restore();

        ctx.save();
        ctx.shadowBlur = 15;
        ctx.shadowColor = '#00ff66';
        ctx.fillStyle = '#00ff66';
        ctx.beginPath();
        ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        for(let pt of particles) {{
            ctx.save();
            ctx.globalAlpha = pt.alpha;
            ctx.shadowBlur = 8;
            ctx.shadowColor = pt.color;
            ctx.fillStyle = pt.color;
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }}

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px Courier New';
        ctx.shadowBlur = 6;
        ctx.shadowColor = '#00f3ff';
        ctx.fillText("SCORE: " + score, 20, 28);
        ctx.fillText("LIVES: " + "❤ ".repeat(lives), 220, 28);
        ctx.fillText("LEVEL: " + level, 460, 28);
        if(paddle.laserTimer > 0) {{
            ctx.fillStyle = '#ff007f';
            ctx.fillText("LASER: " + paddle.laserTimer.toFixed(1) + "s", 590, 28);
        }}

        if(gameState === 'START') {{
            ctx.fillStyle = 'rgba(6, 8, 20, 0.85)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.shadowBlur = 20;
            ctx.shadowColor = '#00f3ff';
            ctx.fillStyle = '#00f3ff';
            ctx.font = 'bold 36px Courier New';
            ctx.textAlign = 'center';
            ctx.fillText("NEON BRICK BREAKER", canvas.width/2, canvas.height/2 - 40);
            ctx.fillStyle = '#fff';
            ctx.font = '16px Courier New';
            ctx.fillText("CLICK OR PRESS SPACE TO START", canvas.width/2, canvas.height/2 + 10);
            ctx.fillStyle = '#ffe600';
            ctx.font = '13px Courier New';
            ctx.fillText("Move mouse or use Arrow keys / A & D to steer paddle", canvas.width/2, canvas.height/2 + 50);
            ctx.textAlign = 'left';
        }} else if(gameState === 'PAUSED') {{
            ctx.fillStyle = 'rgba(6, 8, 20, 0.7)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.shadowBlur = 20;
            ctx.shadowColor = '#ffe600';
            ctx.fillStyle = '#ffe600';
            ctx.font = 'bold 32px Courier New';
            ctx.textAlign = 'center';
            ctx.fillText("GAME PAUSED", canvas.width/2, canvas.height/2);
            ctx.font = '14px Courier New';
            ctx.fillStyle = '#fff';
            ctx.fillText("Press 'P' to Resume", canvas.width/2, canvas.height/2 + 35);
            ctx.textAlign = 'left';
        }} else if(gameState === 'GAMEOVER') {{
            ctx.fillStyle = 'rgba(6, 8, 20, 0.9)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.shadowBlur = 25;
            ctx.shadowColor = '#ff007f';
            ctx.fillStyle = '#ff007f';
            ctx.font = 'bold 38px Courier New';
            ctx.textAlign = 'center';
            ctx.fillText("GAME OVER", canvas.width/2, canvas.height/2 - 30);
            ctx.fillStyle = '#fff';
            ctx.font = '18px Courier New';
            ctx.fillText("Final Score: " + score, canvas.width/2, canvas.height/2 + 15);
            ctx.font = '14px Courier New';
            ctx.fillStyle = '#00f3ff';
            ctx.fillText("Click or Press Space to Play Again", canvas.width/2, canvas.height/2 + 55);
            ctx.textAlign = 'left';
        }}

        ctx.restore();
    }}

    requestAnimationFrame(gameLoop);
    </script>
    </body>
    </html>
    """

# ==========================================
# STREAMLIT USER INTERFACE
# ==========================================

def main():
    st.set_page_config(
        page_title="Neon Brick Breaker Arcade",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    db = LeaderboardDB()

    with st.sidebar:
        st.title("⚡ Arcade Control")
        difficulty = st.selectbox("Select Difficulty", list(GameConfig.DIFFICULTIES.keys()), index=1)
        
        st.markdown("---")
        st.subheader("Submit High Score")
        with st.form("score_form"):
            player_name = st.text_input("Player Name", "CyberGamer")
            final_score = st.number_input("Final Score achieved", min_value=0, step=10, value=150)
            submitted = st.form_submit_button("Record Score")
            if submitted:
                db.add_score(player_name, final_score, difficulty)
                st.success(f"Saved score for {player_name}!")

        st.markdown("---")
        st.subheader("Database Management")
        with st.expander("Danger Zone"):
            if st.button("Reset Leaderboard DB", type="primary"):
                db.reset_leaderboard()
                st.warning("Leaderboard wiped successfully!")
                st.rerun()

    st.title("⚡ Neon Synthwave Brick Breaker")
    st.markdown("Destroy glowing synth blocks, collect falling power-ups (**EXPAND, LASER, LIFE**), and dominate the neon leaderboard!")

    stats = db.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Difficulty", difficulty)
    col2.metric("Total Games Recorded", stats["total_games"])
    col3.metric("All-Time High Score", stats["max_score"])
    col4.metric("Average Score", stats["avg_score"])

    st.markdown("### 🕹️ Game Arena")
    components.html(get_game_html(difficulty), height=600)

    st.markdown("---")
    st.subheader("🏆 Neon Hall of Fame")
    filter_diff = st.selectbox("Filter Leaderboard by Difficulty", ["All"] + list(GameConfig.DIFFICULTIES.keys()))
    
    scores = db.get_top_scores(limit=10, difficulty=filter_diff)
    if scores:
        df = pd.DataFrame(scores, columns=["Player Name", "Score", "Difficulty", "Date"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No high scores recorded yet. Be the first to submit one!")

if __name__ == "__main__":
    main()