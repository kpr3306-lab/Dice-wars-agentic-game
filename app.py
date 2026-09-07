"""
Dice Wars — Flask + SocketIO server.
Holds one game per browser session (server-side authoritative state).
"""
import os
import random
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit

from game.engine import GameState, MAPS
from agents.ai_controller import AIController

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dice-wars-dev-secret")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

GAMES: dict[str, GameState] = {}
AI = AIController(owner="ai")


def get_state() -> GameState | None:
    sid = session.get("game_sid")
    return GAMES.get(sid)


@app.route("/")
def index():
    return render_template("index.html", maps=MAPS)


@app.route("/instructions")
def instructions():
    return render_template("instructions.html")


@app.route("/behind-the-scenes")
def behind_the_scenes():
    return render_template("behind_the_scenes.html")


@socketio.on("new_game")
def new_game(data):
    map_id = data.get("map_id", "skirmish_isle")
    if map_id not in MAPS:
        map_id = "skirmish_isle"
    seed = random.randint(0, 1_000_000)
    state = GameState(map_id, seed=seed)
    sid = request.sid
    session["game_sid"] = sid
    GAMES[sid] = state
    emit("state_update", state.to_dict())


@socketio.on("attack")
def on_attack(data):
    state = get_state()
    if not state or state.winner or state.turn_owner != "human":
        return
    src, dst = data.get("src"), data.get("dst")
    if not state.is_adjacent_enemy(src, dst, "human"):
        emit("error_msg", {"message": "Illegal attack."})
        return
    result = state.attack(src, dst)
    emit("attack_result", vars(result))
    emit("state_update", state.to_dict())


@socketio.on("end_attack_phase")
def end_attack_phase():
    """Human is done attacking this turn -> compute their reinforcement pool."""
    state = get_state()
    if not state or state.winner or state.turn_owner != "human":
        return
    bonus = state.end_turn_and_reinforce("human")
    emit("reinforcements_ready", {"pool": bonus})
    emit("state_update", state.to_dict())


@socketio.on("place_reinforcement")
def place_reinforcement(data):
    state = get_state()
    if not state or state.turn_owner != "human":
        return
    ok = state.place_reinforcement("human", data.get("territory_id"))
    emit("state_update", state.to_dict())
    if ok and state.pending_reinforcements == 0:
        _end_human_turn(state)


@socketio.on("skip_remaining_reinforcements")
def skip_remaining_reinforcements():
    state = get_state()
    if not state or state.turn_owner != "human":
        return
    state.auto_place_reinforcements("human")
    emit("state_update", state.to_dict())
    _end_human_turn(state)


def _end_human_turn(state: GameState):
    state.switch_turn()  # -> ai
    emit("state_update", state.to_dict())
    if state.winner:
        return
    _run_ai_turn(state)


def _run_ai_turn(state: GameState):
    steps = AI.run_turn(state)
    for step in steps:
        emit("ai_step", step)
        emit("state_update", state.to_dict())
    state.switch_turn()  # -> human
    emit("state_update", state.to_dict())
    emit("ai_turn_complete", {})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
