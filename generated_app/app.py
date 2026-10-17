import os
import sqlite3
import streamlit as st
import streamlit.components.v1 as components

DB_PATH = "space_shooter_scores.db"

class GameConfig:
    @staticmethod
    def get_difficulty_settings(difficulty: str) -> dict:
        settings = {
            "Casual": {"speed_mult": 0.8, "enemy_spawn_rate": 0.02, "score_mult": 1.0, "player_lives": 5},
            "Standard": {"speed_mult": 1.0, "enemy_spawn_rate": 0.035, "score_mult": 1.5, "player_lives": 3},
            "Pro": {"speed_mult": 1.3, "enemy_spawn_rate": 0.05, "score_mult": 2.0, "player_lives": 3},
            "Impossible": {"speed_mult": 1.7, "enemy_spawn_rate": 0.07, "score_mult": 3.0, "player_lives": 2}
        }
        return settings.get(difficulty, settings["Standard"])

class LeaderboardDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                score INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

        # Self-healing migration check
        cursor.execute("PRAGMA table_info(scores)")
        columns = [col[1] for col in cursor.fetchall()]
        if "difficulty" not in columns:
            cursor.execute("ALTER TABLE scores ADD COLUMN difficulty TEXT DEFAULT 'Standard'")
            conn.commit()
        if "date" not in columns:
            cursor.execute("ALTER TABLE scores ADD COLUMN date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            conn.commit()
        conn.close()

    def add_score(self, name: str, score: int, difficulty: str = "Standard") -> bool:
        if not name or not name.strip():
            return False
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scores (name, score, difficulty) VALUES (?, ?, ?)",
                (name.strip()[:20], int(score), difficulty)
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_top_scores(self, limit: int = 10) -> list:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, score, difficulty, date FROM scores ORDER BY score DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []

    def get_stats(self) -> dict:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), MAX(score), AVG(score) FROM scores")
            row = cursor.fetchone()
            conn.close()
            if row and row[0] > 0:
                return {
                    "total_games": row[0],
                    "high_score": row[1] if row[1] is not None else 0,
                    "avg_score": int(row[2]) if row[2] is not None else 0
                }
        except Exception:
            pass
        return {"total_games": 0, "high_score": 0, "avg_score": 0}

    def reset_leaderboard(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS scores")
            conn.commit()
            conn.close()
            self.init_db()
            return True
        except Exception:
            return False

# Instantiate DB engine
db = LeaderboardDB()

def get_arcade_html(difficulty: str) -> str:
    settings = GameConfig.get_difficulty_settings(difficulty)
    # We carefully construct the HTML/JS string without unescaped python f-string variables inside JS template literals.
    html_template = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body, html {
    margin: 0; padding: 0; width: 100%; height: 100%;
    background: #060814; overflow: hidden;
    font-family: 'Courier New', monospace;
    color: #00f3ff;
  }
  #game-container {
    position: relative;
    width: 100%;
    height: 640px;
    display: flex;
    justify-content: center;
    align-items: center;
  }
  canvas {
    background: #060814;
    box-shadow: 0 0 30px rgba(0, 243, 255, 0.2);
    cursor: crosshair;
  }
  #hud-overlay {
    position: absolute;
    top: 15px;
    left: 20px;
    right: 20px;
    display: flex;
    justify-content: space-between;
    pointer-events: none;
    font-size: 16px;
    font-weight: bold;
    text-shadow: 0 0 8px #00f3ff;
    z-index: 10;
  }
</style>
</head>
<body>
<div id="game-container">
  <div id="hud-overlay">
    <div>SCORE: <span id="lbl-score">0</span></div>
    <div>WAVE: <span id="lbl-wave">1</span></div>
    <div>SHIELD: <span id="lbl-shield">OFF</span></div>
    <div>LIVES: <span id="lbl-lives">__LIVES__</span></div>
  </div>
  <canvas id="cvs" width="800" height="640"></canvas>
</div>

<script>
const canvas = document.getElementById('cvs');
const ctx = canvas.getContext('2d');

// Difficulty settings from Python
const DIFF_SPEED = __SPEED_MULT__;
const SPAWN_RATE = __SPAWN_RATE__;
const SCORE_MULT = __SCORE_MULT__;
const INIT_LIVES = __LIVES__;

// Audio Synthesizer via Web Audio API
const AudioEngine = {
    ctx: null,
    muted: false,
    init() {
        if (!this.ctx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (AC) this.ctx = new AC();
        }
        if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
    },
    playTone(freq, type, duration, endFreq) {
        if (this.muted) return;
        try {
            this.init();
            if (!this.ctx) return;
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = type || 'sine';
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
    hit() { this.playTone(420, 'square', 0.06, 200); },
    score() { this.playTone(523, 'sine', 0.1); setTimeout(() => this.playTone(659, 'sine', 0.15), 80); },
    laser() { this.playTone(880, 'sawtooth', 0.08, 220); },
    explode() { this.playTone(180, 'triangle', 0.25, 40); },
    gameOver() { this.playTone(330, 'sawtooth', 0.2, 165); },
    powerup() { this.playTone(440, 'sine', 0.1); setTimeout(() => this.playTone(880, 'sine', 0.2), 100); }
};

// Game States: 'MENU', 'PLAYING', 'PAUSED', 'GAMEOVER'
let gameState = 'MENU';
let score = 0;
let wave = 1;
let lives = INIT_LIVES;
let shakeTimer = 0;
let keys = {};
let mouse = { x: 400, y: 520, down: false };

// Entities
let player = {
    x: 400,
    y: 540,
    w: 36,
    h: 28,
    speed: 7 * DIFF_SPEED,
    shield: false,
    shieldTimer: 0,
    multishot: false,
    multishotTimer: 0,
    cooldown: 0
};

let lasers = [];
let enemies = [];
let particles = [];
let powerups = [];
let stars = [];

// Init Starfield Background
for(let i=0; i<80; i++) {
    stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: Math.random() * 2 + 0.5,
        speed: Math.random() * 1.5 + 0.5
    });
}

// Input listeners
window.addEventListener('keydown', e => {
    AudioEngine.init();
    keys[e.code] = true;
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) {
        e.preventDefault();
    }
    if (e.code === 'KeyP') {
        if (gameState === 'PLAYING') gameState = 'PAUSED';
        else if (gameState === 'PAUSED') gameState = 'PLAYING';
    }
    if ((e.code === 'Space' || e.code === 'Enter') && (gameState === 'MENU' || gameState === 'GAMEOVER')) {
        resetGame();
        gameState = 'PLAYING';
    }
});

window.addEventListener('keyup', e => { keys[e.code] = false; });

canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = e.clientX - rect.left;
    mouse.y = e.clientY - rect.top;
});

canvas.addEventListener('mousedown', e => {
    AudioEngine.init();
    if (gameState === 'MENU' || gameState === 'GAMEOVER') {
        resetGame();
        gameState = 'PLAYING';
    } else if (gameState === 'PLAYING') {
        mouse.down = true;
    }
});

canvas.addEventListener('mouseup', e => { mouse.down = false; });

function resetGame() {
    score = 0;
    wave = 1;
    lives = INIT_LIVES;
    lasers = [];
    enemies = [];
    particles = [];
    powerups = [];
    player.x = canvas.width / 2;
    player.y = canvas.height - 80;
    player.shield = false;
    player.shieldTimer = 0;
    player.multishot = false;
    player.multishotTimer = 0;
}

function spawnParticles(x, y, color, count=15) {
    for(let i=0; i<count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 4 + 1;
        particles.push({
            x: x, y: y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            alpha: 1.0,
            decay: Math.random() * 0.03 + 0.02,
            color: color || '#00f3ff',
            size: Math.random() * 3 + 1
        });
    }
}

function spawnEnemy() {
    const types = ['drone', 'fighter', 'tank'];
    const rand = Math.random();
    let type = 'drone';
    let hp = 1;
    let color = '#ff007f';
    let w = 30, h = 24;

    if (wave >= 2 && rand > 0.6) {
        type = 'fighter';
        hp = 2;
        color = '#ffe600';
        w = 34; h = 28;
    }
    if (wave >= 3 && rand > 0.85) {
        type = 'tank';
        hp = 4;
        color = '#9d00ff';
        w = 44; h = 36;
    }

    enemies.push({
        x: Math.random() * (canvas.width - 60) + 30,
        y: -40,
        w: w,
        h: h,
        type: type,
        hp: hp,
        maxHp: hp,
        speed: (Math.random() * 1.5 + 1.0) * DIFF_SPEED * (1 + wave * 0.05),
        color: color,
        shootTimer: Math.random() * 100
    });
}

function spawnPowerup(x, y) {
    if (Math.random() < 0.25) {
        const type = Math.random() > 0.5 ? 'shield' : 'multishot';
        powerups.push({
            x: x, y: y,
            w: 22, h: 22,
            type: type,
            speed: 2.0
        });
    }
}

// Main Loop
let lastTime = performance.now();

function gameLoop(now) {
    const dt = Math.min((now - lastTime) / 1000, 0.1);
    lastTime = now;

    update(dt);
    render();

    requestAnimationFrame(gameLoop);
}

function update(dt) {
    // Stars update
    for(let s of stars) {
        s.y += s.speed;
        if (s.y > canvas.height) s.y = 0;
    }

    if (shakeTimer > 0) shakeTimer -= dt;

    if (gameState !== 'PLAYING') return;

    // Wave progression
    if (score >= wave * 500) {
        wave++;
        AudioEngine.score();
    }

    // Player Movement (Keyboard & Mouse)
    let moveX = 0;
    if (keys['ArrowLeft'] || keys['KeyA']) moveX = -1;
    if (keys['ArrowRight'] || keys['KeyD']) moveX = 1;
    
    if (moveX !== 0) {
        player.x += moveX * player.speed;
    } else {
        // Smooth mouse follow interpolation
        player.x += (mouse.x - player.x) * 0.15;
    }

    // Boundary clamp
    if (player.x < player.w/2) player.x = player.w/2;
    if (player.x > canvas.width - player.w/2) player.x = canvas.width - player.w/2;

    // Timers
    if (player.shield) {
        player.shieldTimer -= dt;
        if (player.shieldTimer <= 0) player.shield = false;
    }
    if (player.multishot) {
        player.multishotTimer -= dt;
        if (player.multishotTimer <= 0) player.multishot = false;
    }

    // Shooting
    if (player.cooldown > 0) player.cooldown -= dt;
    if ((keys['Space'] || mouse.down) && player.cooldown <= 0) {
        AudioEngine.laser();
        if (player.multishot) {
            lasers.push({ x: player.x, y: player.y - 15, vx: 0, vy: -12, color: '#00ff66' });
            lasers.push({ x: player.x - 12, y: player.y - 10, vx: -2, vy: -11, color: '#00ff66' });
            lasers.push({ x: player.x + 12, y: player.y - 10, vx: 2, vy: -11, color: '#00ff66' });
        } else {
            lasers.push({ x: player.x, y: player.y - 15, vx: 0, vy: -12, color: '#00f3ff' });
        }
        player.cooldown = 0.15;
    }

    // Update lasers
    for (let i = lasers.length - 1; i >= 0; i--) {
        let l = lasers[i];
        l.x += l.vx;
        l.y += l.vy;
        if (l.y < -10 || l.x < 0 || l.x > canvas.width) {
            lasers.splice(i, 1);
        }
    }

    // Enemy Spawning
    if (Math.random() < SPAWN_RATE * (1 + wave * 0.1)) {
        spawnEnemy();
    }

    // Update enemies
    for (let i = enemies.length - 1; i >= 0; i--) {
        let e = enemies[i];
        e.y += e.speed;

        // Enemy collision with player
        const dx = e.x - player.x;
        const dy = e.y - player.y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < (e.w/2 + player.w/2)) {
            AudioEngine.explode();
            shakeTimer = 0.3;
            spawnParticles(player.x, player.y, '#ff007f', 25);
            enemies.splice(i, 1);
            if (player.shield) {
                player.shield = false;
            } else {
                lives--;
                if (lives <= 0) {
                    AudioEngine.gameOver();
                    gameState = 'GAMEOVER';
                }
            }
            continue;
        }

        // Out of bounds
        if (e.y > canvas.height + 50) {
            enemies.splice(i, 1);
            continue;
        }

        // Laser vs Enemy collision
        for (let j = lasers.length - 1; j >= 0; j--) {
            let l = lasers[j];
            const ldx = l.x - e.x;
            const ldy = l.y - e.y;
            if (Math.abs(ldx) < e.w/2 + 4 && Math.abs(ldy) < e.h/2 + 4) {
                e.hp--;
                lasers.splice(j, 1);
                spawnParticles(l.x, l.y, e.color, 6);
                AudioEngine.hit();

                if (e.hp <= 0) {
                    AudioEngine.explode();
                    spawnParticles(e.x, e.y, e.color, 20);
                    score += Math.floor(100 * SCORE_MULT * (e.maxHp));
                    spawnPowerup(e.x, e.y);
                    enemies.splice(i, 1);
                }
                break;
            }
        }
    }

    // Update powerups
    for (let i = powerups.length - 1; i >= 0; i--) {
        let p = powerups[i];
        p.y += p.speed;
        const pdx = p.x - player.x;
        const pdy = p.y - player.y;
        if (Math.abs(pdx) < 25 && Math.abs(pdy) < 25) {
            AudioEngine.powerup();
            if (p.type === 'shield') {
                player.shield = true;
                player.shieldTimer = 8.0;
            } else {
                player.multishot = true;
                player.multishotTimer = 8.0;
            }
            powerups.splice(i, 1);
            continue;
        }
        if (p.y > canvas.height + 30) {
            powerups.splice(i, 1);
        }
    }

    // Update particles
    for (let i = particles.length - 1; i >= 0; i--) {
        let p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.alpha -= p.decay;
        if (p.alpha <= 0) particles.splice(i, 1);
    }

    // HUD DOM update
    document.getElementById('lbl-score').innerText = score;
    document.getElementById('lbl-wave').innerText = wave;
    document.getElementById('lbl-lives').innerText = lives;
    document.getElementById('lbl-shield').innerText = player.shield ? Math.ceil(player.shieldTimer) + 's' : (player.multishot ? 'MULTI' : 'OFF');
}

function render() {
    ctx.save();
    // Camera shake
    if (shakeTimer > 0) {
        const offsetX = (Math.random() - 0.5) * 10;
        const offsetY = (Math.random() - 0.5) * 10;
        ctx.translate(offsetX, offsetY);
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw Stars
    ctx.fillStyle = '#ffffff';
    for(let s of stars) {
        ctx.globalAlpha = s.speed / 2;
        ctx.fillRect(s.x, s.y, s.size, s.size);
    }
    ctx.globalAlpha = 1.0;

    // Draw Particles
    for(let p of particles) {
        ctx.save();
        ctx.globalAlpha = p.alpha;
        ctx.shadowBlur = 8;
        ctx.shadowColor = p.color;
        ctx.fillStyle = p.color;
        ctx.fillRect(p.x, p.y, p.size, p.size);
        ctx.restore();
    }

    // Draw Powerups
    for(let p of powerups) {
        ctx.save();
        ctx.shadowBlur = 12;
        ctx.shadowColor = p.type === 'shield' ? '#00f3ff' : '#00ff66';
        ctx.fillStyle = p.type === 'shield' ? '#00f3ff' : '#00ff66';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 11, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#060814';
        ctx.font = 'bold 10px Courier New';
        ctx.fillText(p.type === 'shield' ? 'S' : 'M', p.x - 3, p.y + 4);
        ctx.restore();
    }

    // Draw Lasers
    for(let l of lasers) {
        ctx.save();
        ctx.shadowBlur = 12;
        ctx.shadowColor = l.color;
        ctx.fillStyle = l.color;
        ctx.fillRect(l.x - 2, l.y - 8, 4, 16);
        ctx.restore();
    }

    // Draw Enemies
    for(let e of enemies) {
        ctx.save();
        ctx.shadowBlur = 14;
        ctx.shadowColor = e.color;
        ctx.strokeStyle = e.color;
        ctx.lineWidth = 2;
        ctx.fillStyle = '#060814';

        ctx.beginPath();
        ctx.moveTo(e.x, e.y + e.h/2);
        ctx.lineTo(e.x - e.w/2, e.y - e.h/2);
        ctx.lineTo(e.x, e.y - e.h/4);
        ctx.lineTo(e.x + e.w/2, e.y - e.h/2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();
    }

    // Draw Player
    if (gameState === 'PLAYING' || gameState === 'PAUSED') {
        ctx.save();
        ctx.shadowBlur = 15;
        ctx.shadowColor = '#00f3ff';
        ctx.strokeStyle = '#00f3ff';
        ctx.lineWidth = 2;
        ctx.fillStyle = '#060814';

        ctx.beginPath();
        ctx.moveTo(player.x, player.y - player.h/2);
        ctx.lineTo(player.x - player.w/2, player.y + player.h/2);
        ctx.lineTo(player.x, player.y + player.h/3);
        ctx.lineTo(player.x + player.w/2, player.y + player.h/2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        if (player.shield) {
            ctx.strokeStyle = '#00f3ff';
            ctx.shadowColor = '#00f3ff';
            ctx.beginPath();
            ctx.arc(player.x, player.y, player.w, 0, Math.PI * 2);
            ctx.stroke();
        }
        ctx.restore();
    }

    // UI Overlays in Canvas
    if (gameState === 'MENU') {
        ctx.fillStyle = 'rgba(6, 8, 20, 0.85)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.shadowBlur = 20;
        ctx.shadowColor = '#00f3ff';
        ctx.fillStyle = '#00f3ff';
        ctx.font = 'bold 36px Courier New';
        ctx.textAlign = 'center';
        ctx.fillText('GALAXY SPACE SHOOTER', canvas.width/2, canvas.height/2 - 50);

        ctx.shadowBlur = 10;
        ctx.shadowColor = '#ffe600';
        ctx.fillStyle = '#ffe600';
        ctx.font = '18px Courier New';
        ctx.fillText('CLICK OR PRESS SPACE TO START', canvas.width/2, canvas.height/2 + 10);

        ctx.fillStyle = '#00ff66';
        ctx.font = '14px Courier New';
        ctx.fillText('Controls: Arrow Keys / WASD / Mouse to Move | Space / Click to Shoot | P to Pause', canvas.width/2, canvas.height/2 + 60);
        ctx.textAlign = 'left';
    } else if (gameState === 'PAUSED') {
        ctx.fillStyle = 'rgba(6, 8, 20, 0.7)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.shadowBlur = 20;
        ctx.shadowColor = '#ffe600';
        ctx.fillStyle = '#ffe600';
        ctx.font = 'bold 32px Courier New';
        ctx.textAlign = 'center';
        ctx.fillText('GAME PAUSED', canvas.width/2, canvas.height/2);
        ctx.font = '16px Courier New';
        ctx.fillText('Press P to Resume', canvas.width/2, canvas.height/2 + 40);
        ctx.textAlign = 'left';
    } else if (gameState === 'GAMEOVER') {
        ctx.fillStyle = 'rgba(6, 8, 20, 0.85)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.shadowBlur = 25;
        ctx.shadowColor = '#ff007f';
        ctx.fillStyle = '#ff007f';
        ctx.font = 'bold 40px Courier New';
        ctx.textAlign = 'center';
        ctx.fillText('GAME OVER', canvas.width/2, canvas.height/2 - 60);

        ctx.shadowBlur = 15;
        ctx.shadowColor = '#00f3ff';
        ctx.fillStyle = '#00f3ff';
        ctx.font = '22px Courier New';
        ctx.fillText('FINAL SCORE: ' + score, canvas.width/2, canvas.height/2 - 10);

        ctx.fillStyle = '#ffe600';
        ctx.font = '16px Courier New';
        ctx.fillText('SUBMIT YOUR SCORE BELOW!', canvas.width/2, canvas.height/2 + 35);
        ctx.fillText('CLICK OR PRESS SPACE TO RESTART', canvas.width/2, canvas.height/2 + 75);
        ctx.textAlign = 'left';
    }

    ctx.restore();
}

requestAnimationFrame(gameLoop);
</script>
</body>
</html>
"""

    # Inject dynamic configuration values securely
    html_template = html_template.replace("__SPEED_MULT__", str(settings["speed_mult"]))
    html_template = html_template.replace("__SPAWN_RATE__", str(settings["enemy_spawn_rate"]))
    html_template = html_template.replace("__SCORE_MULT__", str(settings["score_mult"]))
    html_template = html_template.replace("__LIVES__", str(settings["player_lives"]))
    return html_template

def main():
    st.set_page_config(
        page_title="Galaxy Space Shooter Arcade",
        page_icon="🚀",
        layout="wide"
    );

    st.title("🚀 GALAXY SPACE SHOOTER ARCADE")
    st.markdown("Retro glowing vector arcade shooter with procedural Web Audio, power-up shields & multishot, and persistent SQLite leaderboards.")

    # Sidebar controls & stats
    with st.sidebar:
        st.header("⚙️ Game Control Panel")
        difficulty = st.selectbox("Select Difficulty", ["Casual", "Standard", "Pro", "Impossible"], index=1)
        
        st.divider()
        st.subheader("📊 Leaderboard Stats")
        stats = db.get_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Games", stats["total_games"])
            st.metric("High Score", stats["high_score"])
        with col2:
            st.metric("Avg Score", stats["avg_score"])

        st.divider()
        with st.expander("🛠️ Database Management"):
            if st.button("⚠️ Reset Leaderboard", type="secondary"):
                db.reset_leaderboard()
                st.success("Leaderboard wiped successfully!")
                st.rerun()

    # Layout: Game Canvas on left, High Score Submission & Leaderboard on right
    col_game, col_board = st.columns([2.1, 1])

    with col_game:
        st.subheader(f"🎮 Active Sector ({difficulty} Mode)")
        arcade_html = get_arcade_html(difficulty)
        components.html(arcade_html, height=660)

    with col_board:
        st.subheader("🏆 Submit Score")
        with st.form("score_form", clear_on_submit=True):
            player_name = st.text_input("Pilot Call Sign", max_chars=20, placeholder="ACE_PILOT")
            final_score = st.number_input("Final Score Achieved", min_value=0, step=10, value=0)
            sub_diff = st.selectbox("Recorded Difficulty", ["Casual", "Standard", "Pro", "Impossible"], index=1)
            submit_btn = st.form_submit_button("Record to Database")

            if submit_btn:
                if db.add_score(player_name, final_score, sub_diff):
                    st.success(f"Score {final_score} recorded for {player_name}!")
                    st.rerun()
                else:
                    st.error("Please provide a valid pilot call sign.")

        st.divider()
        st.subheader("🎖️ Top Aces Leaderboard")
        top_scores = db.get_top_scores(10)
        if top_scores:
            formatted_data = []
            for idx, (name, score, diff, date) in enumerate(top_scores, start=1):
                formatted_data.append({
                    "Rank": f"#{idx}",
                    "Pilot": name,
                    "Score": score,
                    "Difficulty": diff,
                    "Date": str(date)[:16]
                })
            st.dataframe(formatted_data, hide_index=True, use_container_width=True)
        else:
            st.info("No high scores recorded yet. Be the first ace!")

if __name__ == '__main__':
    main()