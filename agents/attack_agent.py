"""
Attack Agent
------------
Given the Strategy Agent's goal, scores every legal attack this turn and
executes the best one(s). Uses Monte-Carlo win probability from the engine
rather than a fixed lookup table, and biases its scoring toward the
strategy's goal (e.g. TARGET_WEAK cares about defender dice count more
than raw win%; EXPAND is willing to take slightly worse odds for tempo).
"""
from .base_agent import BaseAgent, AgentThought

MIN_WIN_PROB = {
    "EXPAND": 0.55,
    "TARGET_WEAK": 0.62,
    "CONSOLIDATE": 0.75,
    "DEFEND": 0.85,
}
MAX_ATTACKS_PER_TURN = {
    "EXPAND": 6,
    "TARGET_WEAK": 3,
    "CONSOLIDATE": 1,
    "DEFEND": 1,
}


class AttackAgent(BaseAgent):
    name = "attack"

    def score_move(self, state, src, dst, goal, win_prob):
        t_src, t_dst = state.territories[src], state.territories[dst]
        score = win_prob
        if goal == "TARGET_WEAK":
            score += (1 - t_dst.dice / 8) * 0.3
        if goal == "EXPAND":
            enemy_neighbors = sum(1 for n in state.territories[dst].neighbors
                                   if state.territories[n].owner == "human")
            score += 0.05 * enemy_neighbors  # prefer targets that open more front
        return score

    def plan(self, state, goal: str):
        """Return a ranked list of (src, dst, win_prob, score) without executing."""
        owner = self.owner
        threshold = MIN_WIN_PROB.get(goal, 0.6)
        candidates = []
        for src, dst in state.valid_attacks(owner):
            a_dice = state.territories[src].dice
            d_dice = state.territories[dst].dice
            wp = state.win_probability(a_dice, d_dice)
            if wp >= threshold:
                score = self.score_move(state, src, dst, goal, wp)
                candidates.append((src, dst, wp, score))
        candidates.sort(key=lambda c: c[3], reverse=True)
        return candidates

    def think(self, state, goal="TARGET_WEAK", **kwargs) -> AgentThought:
        candidates = self.plan(state, goal)
        if not candidates:
            return AgentThought(
                agent=self.name,
                headline="No favorable attacks available",
                detail=f"Scanned all legal moves under the '{goal}' posture — nothing clears "
                       f"the {int(MIN_WIN_PROB.get(goal, 0.6)*100)}% win-probability bar. Holding position.",
                data={"goal": goal, "candidates": 0},
            )
        src, dst, wp, score = candidates[0]
        headline = f"Attacking T{dst} from T{src} ({int(wp*100)}% win chance)"
        detail = (f"Evaluated {len(candidates)} legal attack(s) under the '{goal}' posture. "
                   f"T{src} ({state.territories[src].dice} dice) vs T{dst} "
                   f"({state.territories[dst].dice} dice) scored highest.")
        return AgentThought(
            agent=self.name, headline=headline, detail=detail,
            data={"goal": goal, "src": src, "dst": dst, "win_prob": round(wp, 2),
                  "candidates": len(candidates)},
        )
