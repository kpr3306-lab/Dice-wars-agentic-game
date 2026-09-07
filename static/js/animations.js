/* Handles the dice-roll battle overlay: tumbling dice, win/lose reveal. */

function pipsFor(n) {
  return n;
}

function renderDiceRow(container, rolls, side) {
  container.innerHTML = "";
  rolls.forEach((val, i) => {
    const die = document.createElement("div");
    die.className = `die ${side}`;
    die.textContent = val;
    die.style.animationDelay = `${i * 70}ms`;
    container.appendChild(die);
  });
}

/**
 * Play the full battle animation for an AttackResult-shaped object.
 * Returns a Promise that resolves once the animation is done.
 */
function playBattleAnimation(result) {
  return new Promise((resolve) => {
    const overlay = document.getElementById("battle-overlay");
    const title = document.getElementById("battle-title");
    const resultEl = document.getElementById("battle-result");
    const attackerDiceEl = document.getElementById("attacker-dice");
    const defenderDiceEl = document.getElementById("defender-dice");

    title.textContent = `Territory ${result.attacker_id}  →  Territory ${result.defender_id}`;
    resultEl.className = "battle-result";
    resultEl.textContent = "";
    attackerDiceEl.innerHTML = "";
    defenderDiceEl.innerHTML = "";

    overlay.classList.add("show");

    setTimeout(() => {
      renderDiceRow(attackerDiceEl, result.attacker_rolls, "attacker");
      renderDiceRow(defenderDiceEl, result.defender_rolls, "defender");
    }, 120);

    const revealDelay = 120 + Math.max(result.attacker_rolls.length, result.defender_rolls.length) * 70 + 500;

    setTimeout(() => {
      const aTotal = result.attacker_total, dTotal = result.defender_total;
      resultEl.textContent = result.success
        ? `Attacker wins  ${aTotal} — ${dTotal}  ·  Territory captured`
        : `Defender holds  ${dTotal} — ${aTotal}  ·  Attack repelled`;
      resultEl.classList.add("show");
      resultEl.classList.add(result.success ? "win" : "lose");
    }, revealDelay);

    const closeDelay = revealDelay + 1350;
    setTimeout(() => {
      overlay.classList.remove("show");
      resolve();
    }, closeDelay);
  });
}

function showWinnerBanner(winner) {
  const banner = document.getElementById("winner-banner");
  const title = document.getElementById("winner-title");
  title.textContent = winner === "human" ? "Victory is Yours" : "The AI General Prevails";
  title.style.color = winner === "human" ? "#b25050" : "#5c8ca3";
  banner.classList.add("show");
}
