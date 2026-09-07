const socket = io();

const canvas = document.getElementById("board-canvas");
const renderer = new BoardRenderer(canvas);

let currentState = null;
let selectedTerritory = null;
let placingReinforcements = false;
let aiTurnBusy = false;

const feedEl = document.getElementById("live-feed");
const tooltipEl = document.getElementById("tooltip");

// ---------------------------------------------------------------- map select
document.querySelectorAll(".map-card").forEach((card) => {
  card.addEventListener("click", () => {
    const mapId = card.dataset.mapId;
    document.getElementById("map-select-screen").style.display = "none";
    document.getElementById("game-screen").style.display = "grid";
    feedEl.innerHTML = "";
    socket.emit("new_game", { map_id: mapId });
  });
});

document.getElementById("new-game-btn").addEventListener("click", () => {
  document.getElementById("game-screen").style.display = "none";
  document.getElementById("map-select-screen").style.display = "flex";
  document.getElementById("winner-banner").classList.remove("show");
});
document.getElementById("play-again-btn").addEventListener("click", () => {
  document.getElementById("winner-banner").classList.remove("show");
  document.getElementById("game-screen").style.display = "none";
  document.getElementById("map-select-screen").style.display = "flex";
});

// ---------------------------------------------------------------- socket events
socket.on("state_update", (state) => {
  currentState = state;
  renderer.setState(state);
  updateHud(state);
  if (state.turn_owner === "ai" && !state.winner) {
    aiTurnBusy = true;
    setControlsEnabled(false);
  } else if (state.turn_owner === "human") {
    setControlsEnabled(state.pending_reinforcements === 0);
  }
  if (state.winner) showWinnerBanner(state.winner);
});

socket.on("attack_result", async (result) => {
  await playBattleAnimation(result);
});

socket.on("ai_step", async (step) => {
  if (step.type === "thought") {
    pushFeed(step.thought);
  } else if (step.type === "attack_result") {
    await playBattleAnimation(step.result);
  }
});

socket.on("ai_turn_complete", () => {
  aiTurnBusy = false;
  setControlsEnabled(true);
});

socket.on("reinforcements_ready", (data) => {
  placingReinforcements = true;
  document.getElementById("reinforce-banner").style.display = "block";
  document.getElementById("reinforce-pool").textContent = data.pool;
  document.getElementById("end-attack-btn").disabled = true;
});

socket.on("error_msg", (data) => {
  console.warn(data.message);
});

// ---------------------------------------------------------------- HUD
function updateHud(state) {
  const territories = Object.values(state.territories);
  const humanT = territories.filter((t) => t.owner === "human");
  const aiT = territories.filter((t) => t.owner === "ai");

  document.getElementById("turn-number").textContent = state.turn_number;
  document.getElementById("human-count").textContent = humanT.length;
  document.getElementById("ai-count").textContent = aiT.length;
  document.getElementById("human-dice").textContent = humanT.reduce((s, t) => s + t.dice, 0);
  document.getElementById("ai-dice").textContent = aiT.reduce((s, t) => s + t.dice, 0);

  const badge = document.getElementById("turn-badge");
  if (state.turn_owner === "human") {
    badge.className = "turn-badge human";
    badge.innerHTML = '<span class="dot human"></span> Your Turn';
  } else {
    badge.className = "turn-badge ai";
    badge.innerHTML = '<span class="dot ai"></span> AI General is Moving…';
  }

  const pool = state.pending_reinforcements;
  if (pool > 0 && state.turn_owner === "human") {
    placingReinforcements = true;
    document.getElementById("reinforce-banner").style.display = "block";
    document.getElementById("reinforce-pool").textContent = pool;
  } else if (pool === 0) {
    placingReinforcements = false;
    document.getElementById("reinforce-banner").style.display = "none";
  }
}

function pushFeed(thought) {
  const div = document.createElement("div");
  div.className = `thought ${thought.agent}`;
  div.innerHTML = `
    <span class="agent-tag">${thought.agent} agent</span>
    <div class="headline">${thought.headline}</div>
    <div class="detail">${thought.detail}</div>
  `;
  feedEl.prepend(div);
  while (feedEl.children.length > 40) feedEl.removeChild(feedEl.lastChild);
}

function setControlsEnabled(enabled) {
  document.getElementById("end-attack-btn").disabled = !enabled;
}

// ---------------------------------------------------------------- board interaction
canvas.addEventListener("mousemove", (e) => {
  if (!currentState) return;
  const hit = renderer.hitTest(e.clientX, e.clientY);
  renderer.hoverId = hit;
  if (hit !== null) {
    const t = currentState.territories[hit];
    tooltipEl.textContent = `Territory ${t.id} — ${t.owner === "human" ? "Yours" : "AI"} — ${t.dice} dice`;
    tooltipEl.style.left = e.clientX + 14 + "px";
    tooltipEl.style.top = e.clientY + 14 + "px";
    tooltipEl.classList.add("show");
  } else {
    tooltipEl.classList.remove("show");
  }
});
canvas.addEventListener("mouseleave", () => tooltipEl.classList.remove("show"));

canvas.addEventListener("click", (e) => {
  if (!currentState || currentState.turn_owner !== "human" || currentState.winner || aiTurnBusy) return;
  const hit = renderer.hitTest(e.clientX, e.clientY);
  if (hit === null) return;
  const t = currentState.territories[hit];

  if (placingReinforcements) {
    if (t.owner === "human") {
      socket.emit("place_reinforcement", { territory_id: hit });
    }
    return;
  }

  if (selectedTerritory === null) {
    if (t.owner === "human" && t.dice > 1) {
      selectedTerritory = hit;
      const targets = t.neighbors.filter((n) => currentState.territories[n].owner !== "human");
      renderer.setSelection(hit, targets);
    }
  } else {
    if (hit === selectedTerritory) {
      selectedTerritory = null;
      renderer.setSelection(null, []);
      return;
    }
    const srcT = currentState.territories[selectedTerritory];
    if (srcT.neighbors.includes(hit) && t.owner !== "human") {
      socket.emit("attack", { src: selectedTerritory, dst: hit });
      selectedTerritory = null;
      renderer.setSelection(null, []);
    } else if (t.owner === "human" && t.dice > 1) {
      selectedTerritory = hit;
      const targets = t.neighbors.filter((n) => currentState.territories[n].owner !== "human");
      renderer.setSelection(hit, targets);
    } else {
      selectedTerritory = null;
      renderer.setSelection(null, []);
    }
  }
});

// ---------------------------------------------------------------- action buttons
document.getElementById("end-attack-btn").addEventListener("click", () => {
  selectedTerritory = null;
  renderer.setSelection(null, []);
  socket.emit("end_attack_phase");
});

document.getElementById("skip-reinforce-btn").addEventListener("click", () => {
  socket.emit("skip_remaining_reinforcements");
  document.getElementById("reinforce-banner").style.display = "none";
  placingReinforcements = false;
  aiTurnBusy = true;
  setControlsEnabled(false);
  pushFeed({ agent: "strategy", headline: "AI General's turn begins…", detail: "Handing off to the strategy agent." });
});
