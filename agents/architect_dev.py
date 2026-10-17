from typing import Dict, Any, Optional
from core.llm_client import GeminiClient

ARCHITECT_DEV_PROMPT = """
You are a Principal Software Architect and Senior Python Developer specializing in Streamlit Web Applications.
Your job is to read the user's application requirement and produce a self-contained, high-quality, production-ready Streamlit web application in `app.py` along with an exhaustive pytest test suite in `test_app.py`.

Rules:
1. Write clean, idiomatic, typed Python 3 code in `app.py`.
2. Architecture requirements:
   - Implement clean, testable business logic classes and functions (e.g. data engines, models, solvers, validators, algorithms) at the top of `app.py`.
   - Build a comprehensive, beautiful Streamlit web interface in `app.py` using `import streamlit as st`:
     a. CRITICAL - NEVER PRODUCE A BLANK APP: The Streamlit UI code MUST EXECUTE whenever `streamlit run app.py` is invoked. Place UI calls at the module level or inside `def main():` / `def render_ui():`, and ALWAYS CALL IT AT THE VERY BOTTOM OF `app.py` (e.g. `if __name__ == '__main__': main()`).
     b. Include rich visual components: page title (`st.set_page_config`, `st.title`), form inputs (`st.form`, `st.text_input`, `st.selectbox`, `st.number_input`, `st.date_input`), action buttons (`st.button`), KPIs (`st.metric`), cards or tables (`st.dataframe`), search/filter tools, and status feedback (`st.success`, `st.error`).
     c. Ensure business logic functions and classes can be cleanly imported into `test_app.py` without executing the Streamlit browser runtime.
3. The test suite (`test_app.py`) must import and test the core logic functions/classes directly from `app` (e.g., `from app import DataEngine, Calculator, ...`) without needing the UI runner.
4. Database & Storage Resilience (CRITICAL):
   - If using SQLite or persistent databases:
     a. Never allow `sqlite3.OperationalError` due to missing columns or outdated tables. In `_init_db()`, inspect existing tables (using `PRAGMA table_info(table_name)`) and automatically add any missing columns via `ALTER TABLE ... ADD COLUMN` so upgrading an existing database file never crashes.
     b. Provide a "Reset Database / Clear All Data" control in the Streamlit UI (e.g. inside a sidebar expander) so users can wipe stale test data anytime with a single click.
     c. Wrap queries touching columns in defensive error handling and call `_init_db()` to self-heal schema if missing columns or tables are detected.
5. Games & Embedded HTML/JavaScript Safety (CRITICAL):
   - When embedding HTML, CSS, or JavaScript in Python (e.g. using `components.html(...)` or `st.components.v1.html` for games/canvas):
     a. NEVER use Python f-strings with unescaped JavaScript template literals (like `${var}` or `${obj.prop}`)! Python f-strings will try to evaluate `{var}` as Python variables, instantly crashing with `NameError: name '...' is not defined`.
     b. ALWAYS use standard JavaScript string concatenation (e.g. `"Score: " + score + " - Player: " + player.name`), OR use a standard string without `f` and use `.replace("__PARAM__", str(param))`.
6. Include at least 4-6 diverse unit tests covering:
   - Happy paths / basic functionality
   - Edge cases (bounds, invalid inputs, empty structures)
   - Error handling / expected exceptions (using `pytest.raises`)
7. You MUST return your response strictly as a JSON object with this exact structure:
{
  "architecture_summary": "Brief 2-3 sentence overview of the design patterns and components.",
  "app_code": "# full Python code for app.py",
  "test_code": "# full pytest code for test_app.py"
}
"""

GAME_ARCHITECTURE_DIRECTIVE = """
=== HIGHEST QUALITY INTERACTIVE GAME / ARCADE SPECIFICATION (MANDATORY FOR GAMES) ===
The user requirement is an interactive game, arcade experience, or canvas simulation.
You MUST deliver an arcade-grade, visually stunning, polished web game of the ABSOLUTE HIGHEST QUALITY that runs directly in the browser via `st.components.v1.html(..., height=640)`.

A high-quality game MUST incorporate the following 7 Pillars:

1. Visuals & Art Direction (HTML5 Canvas):
   - Cyberpunk / Neon Synthwave theme: Deep space dark background (#060814 or #0a0e1a).
   - Luminous Neon Glow: Add `ctx.shadowBlur = 12; ctx.shadowColor = '#00f3ff';` (or '#ff007f', '#ffe600', '#00ff66') for dynamic glowing effects on paddles, balls, lasers, enemies, and score text. Reset `ctx.shadowBlur = 0;` after drawing glowing elements.
   - Dynamic Background: Animated floating stardust or retro vector perspective grid so the canvas feels alive at all times.
   - Particle Engine: An embedded particle system where 12-24 glowing spark particles explode with velocity, gravity/drag, and fading alpha whenever a collision, score, hit, or explosion occurs.
   - Screen Impact / Shake: Trigger a subtle camera shake on heavy impacts or player damage.
   - 60 FPS Delta-Time Physics: Use `requestAnimationFrame` with delta-time calculation (`const dt = Math.min((now - lastTime) / 1000, 0.1);`) for buttery-smooth motion on all screens.

2. Procedural Sound Effects via Web Audio API (Zero External Files!):
   - Implement a lightweight, self-contained procedural sound synthesizer using browser `AudioContext`:
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
         gameOver() { this.playTone(330, 'sawtooth', 0.2, 165); }
     };
   - Initialize/resume audio on the first user click or keypress to comply with browser autoplay security policies.
   - Provide an on-screen mute button or click toggle in the canvas HUD.

3. Complete Game State Machine:
   - State 1 (START / MENU): Glowing title, animated 'PRESS SPACE OR CLICK TO START', high score display, and clear control instructions.
   - State 2 (PLAYING): Active game loop with live HUD (Score, High Score, Health/Lives, Difficulty Level).
   - State 3 (PAUSED): Press 'P' or 'ESC' or click Pause button to show a sleek translucent pause screen.
   - State 4 (GAME OVER / VICTORY): Displays Final Score, celebratory particle fireworks for new high scores, and 'PRESS SPACE OR CLICK TO PLAY AGAIN'.

4. Dual Controls (Keyboard + Mouse/Touch):
   - Keyboard: Arrow keys, WASD, Space bar. Always add `e.preventDefault()` for Arrow keys and Space bar so the page doesn't scroll!
   - Touch & Mouse: Support `mousemove` and `touchmove` so players on laptops, trackpads, tablets, or phones can play effortlessly without a keyboard.

5. Python Backend Engine & Test Suite (`test_app.py`):
   - At the top of `app.py`, implement testable Python classes:
     * `GameConfig` / `DifficultyManager`: Constants and methods for speeds, AI response curves, and score multipliers across difficulties.
     * `LeaderboardDB`: SQLite manager with `init_db()`, `add_score(name, score, difficulty)`, `get_top_scores(limit=10)`, `get_stats()`, and `reset_leaderboard()`.
   - `test_app.py` MUST import and test these backend classes directly with 5-6 passing unit tests covering initialization, score additions, stats calculation, and difficulty bounds.

6. Streamlit Page Integration:
   - Header with custom game title and difficulty selector (`st.selectbox` or `st.radio`: 'Casual', 'Standard', 'Pro', 'Impossible').
   - Center: The HTML5 Canvas game rendered in full glory via `st.components.v1.html(..., height=640)`.
   - Below/Beside Game: High score submission form (`st.form`) allowing players to record their final score to the SQLite leaderboard, a live Leaderboard table (`st.dataframe`), and instructions.

7. JavaScript Code Safety (CRITICAL):
   - NEVER use Python f-strings with unescaped JavaScript template literals `${var}`!
   - ALWAYS use standard JavaScript string concatenation (e.g. `"Score: " + score`) or use a standard string without `f` and `.replace("__PARAM__", str(param))`.
"""

def is_game_requirement(prompt: str, app_type: str = "") -> bool:
    game_keywords = [
        "game", "arcade", "pong", "snake", "tetris", "space invaders", "shooter",
        "flappy", "breakout", "brick", "paddle", "platformer", "racer", "racing",
        "maze", "rpg", "puzzle", "card game", "chess", "canvas", "interactive simulation",
        "play", "asteroid", "pacman", "frogger", "tictactoe", "tic-tac-toe", "pinball",
        "minesweeper", "alien", "galaxy", "combat", "score", "quest"
    ]
    text = f"{prompt} {app_type}".lower()
    return any(kw in text for kw in game_keywords)

class ArchitectDeveloperAgent:
    """Agent 1: Generates architecture, application code (app.py), and test suite (test_app.py)."""
    
    def __init__(self, client: GeminiClient):
        self.client = client

    def run(self, user_prompt: str, app_type: str = "Streamlit Web App") -> Dict[str, Any]:
        is_game = is_game_requirement(user_prompt, app_type)
        if is_game:
            extra_instructions = (
                "\n\n==================================================\n"
                "CRITICAL: Detected Game / Arcade requirement.\n"
                "You must strictly apply the following AAA Game Architecture Directive:\n"
                + GAME_ARCHITECTURE_DIRECTIVE
            )
        else:
            extra_instructions = ""

        prompt = (
            f"User Requirement:\n\"\"\"{user_prompt}\"\"\"\n\n"
            "Generate the architecture plan, the complete Streamlit web application (`app.py`), and the pytest test suite (`test_app.py`)."
            f"{extra_instructions}"
        )
        result = self.client.generate_json(prompt, system_instruction=ARCHITECT_DEV_PROMPT)
        
        raw_app = result.get("app_code")
        raw_test = result.get("test_code")
        if not raw_app or not raw_test:
            raise ValueError(f"ArchitectDeveloperAgent generated incomplete structure: {result}")
            
        return {
            "architecture_summary": str(result.get("architecture_summary") or "Python application and test suite generated."),
            "app_code": str(raw_app).strip(),
            "test_code": str(raw_test).strip(),
            "is_game": is_game
        }
