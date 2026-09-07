# Dice Wars — Human vs. AI General

A browser-based Dice Wars clone built for an AI & Agent Systems course project.
Python backend (Flask + SocketIO), Canvas/CSS frontend, no game engine required.

## Run it

```bash
cd dicewars
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`. Pick a map, and play.

If you want to regenerate the maps (or add new ones), edit `generate_maps.py`
and re-run `python generate_maps.py` — it writes JSON into `game/data/`.

## What satisfies the course requirements

| Requirement | Where |
|---|---|
| 3+ maps | `generate_maps.py` generates 3 distinct Voronoi-based maps into `game/data/*.json` (18 / 28 / 40 territories) |
| Multi-agent system (attack/defense/strategy) | `agents/strategy_agent.py`, `agents/attack_agent.py`, `agents/defense_agent.py`, orchestrated by `agents/ai_controller.py` |
| Python | Entire backend + game logic + agents |
| Human vs. 1 AI | The three agents together *are* "the AI player" — see Behind the Scenes page in-app |
| Polished UI | HTML5 Canvas map renderer + CSS "war room" design system (`static/`) with dice-roll animations, capture/repel feedback, live agent reasoning feed |

## Architecture

```
app.py                  Flask + SocketIO server, holds per-session GameState
game/
  engine.py             Pure game logic: board, dice combat, reinforcement, win check
  data/*.json            Precomputed maps (Voronoi + island silhouette)
generate_maps.py        Standalone script that builds the maps (numpy/scipy/shapely)
agents/
  base_agent.py          Shared AgentThought structure (feeds the live UI panel)
  strategy_agent.py       Sets a per-turn goal: EXPAND / DEFEND / CONSOLIDATE / TARGET_WEAK
  attack_agent.py         Monte-Carlo win-probability scoring + move selection
  defense_agent.py        Vulnerability-weighted reinforcement placement
  ai_controller.py        Orchestrates strategy -> attack -> defense each AI turn
templates/               index.html (game), instructions.html, behind_the_scenes.html
static/
  css/style.css           Design system
  js/board_renderer.js    Canvas territory rendering, hit-testing, glow effects
  js/animations.js        Dice battle overlay animation
  js/main.js              Socket wiring + game flow
```

## Design notes

- **Maps are geography, not node graphs.** Territories are Voronoi cells clipped to
  a randomized island silhouette, so borders are organic and choke points emerge
  naturally, closer to a real Risk-style map than dots-and-lines.
- **The AI opponent is a pipeline, not 3 independent bots.** Strategy runs first and
  sets a goal; Attack and Defense both read that goal, so a single coherent posture
  drives the whole turn. This is deliberately framed as "1 AI player" for the human
  to play against, while still demonstrating multi-agent coordination internally.
- **Every agent decision is explainable.** Each agent returns an `AgentThought`
  (headline + 1-3 sentence reasoning + raw data), which streams live to the
  "Behind the Scenes" panel during play — this is your best demo material.

## Extending

- Add a 4th map: add one line to the `maps` list in `generate_maps.py`, re-run it.
- Add a baseline bot (random/greedy) for benchmarking: subclass `BaseAgent`
  and swap it into `AIController` — the engine and UI don't need to change.
- Tune AI difficulty: adjust `MIN_WIN_PROB` / `MAX_ATTACKS_PER_TURN` in
  `agents/attack_agent.py`.

## Deploying (Render)

This app needs a real persistent process with WebSocket support (for
Flask-SocketIO), which is what Render's free web service tier gives you.
It is **not** a fit for Streamlit — Streamlit can't host a custom
Flask + SocketIO backend or this project's hand-written Canvas/JS frontend.

**One-time setup:**

1. Push this folder to a GitHub repo (root of the repo = this folder, so
   `app.py` sits at the repo root).
2. On [render.com](https://render.com): **New → Web Service** → connect the repo.
   Render will detect `render.yaml` automatically and pre-fill everything;
   otherwise set manually:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn --worker-class eventlet -w 1 app:app`
   - **Runtime:** Python 3.11
3. Deploy. Render gives you a `https://<your-app>.onrender.com` URL.

**Why these specific settings:**

- `eventlet` worker — Flask-SocketIO needs an async-capable server for real
  WebSocket support in production; the plain dev server (`socketio.run`)
  isn't meant for this.
- `-w 1` (exactly one worker) — game state (`GAMES` dict in `app.py`) is
  held in memory per process. More than one worker means different players
  could land on different processes that don't share state, and a single
  player's socket reconnect could hit a worker that's never heard of their
  session. Fine for a course-scale demo; a real multi-user deployment would
  move `GAMES` into Redis and could then scale to multiple workers.
- **Free tier note:** Render's free web services spin down after inactivity,
  so the first request after idling takes ~30–50s to wake up. Fine for a demo
  or grading, not for a "click and it's instant" experience.
- The `SECRET_KEY` env var is auto-generated by `render.yaml`; don't reuse
  the `dice-wars-dev-secret` fallback in `app.py` for anything but local dev.

**To test the exact production command locally first:**

```bash
pip install -r requirements.txt
gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:5000
```

