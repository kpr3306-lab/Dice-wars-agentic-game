"""
Strategy Agent
--------------
Runs first, once per AI turn. Looks at the whole board and decides a
high-level posture for the turn, which is then handed down to the Attack
and Defense agents as a "goal" that biases their scoring. This is what
makes the pipeline hierarchical rather than three independent bots.

Goals:
  EXPAND      - press the advantage, take territory
  CONSOLIDATE - stop attacking, shore up borders (used when overextended)
  DEFEND      - focus on the weakest border where the human is threatening
  TARGET_WEAK - snowball against whichever side of the human is weakest
"""
from .base_agent import BaseAgent, AgentThought


class StrategyAgent(BaseAgent):
    name = "strategy"

    def think(self, state, **kwargs) -> AgentThought:
        owner = self.owner
        enemy = "human" if owner == "ai" else "ai"

        my_territories = state.owned_by(owner)
        enemy_territories = state.owned_by(enemy)
        my_dice = sum(state.territories[t].dice for t in my_territories)
        enemy_dice = sum(state.territories[t].dice for t in enemy_territories)
        my_largest_group = state.largest_group_size(owner)

        border = [tid for tid in my_territories if any(
            state.territories[n].owner == enemy for n in state.territories[tid].neighbors)]
        weak_border = [tid for tid in border if state.territories[tid].dice <= 2]

        dice_ratio = my_dice / max(enemy_dice, 1)
        exposure_ratio = len(weak_border) / max(len(border), 1)

        if exposure_ratio > 0.45 and dice_ratio < 1.15:
            goal = "DEFEND"
            headline = "Border looks thin — shifting to defense"
            detail = (f"{len(weak_border)} of {len(border)} border territories are down to "
                       f"1-2 dice while the dice ratio is {dice_ratio:.2f}. Prioritizing "
                       f"reinforcement over aggression this turn.")
        elif dice_ratio >= 1.4:
            goal = "EXPAND"
            headline = "Clear dice advantage — pressing the attack"
            detail = (f"Holding {my_dice} dice across {len(my_territories)} territories vs "
                       f"{enemy_dice} for the opponent ({dice_ratio:.2f}x). Favorable trades "
                       f"are everywhere, so this turn is about taking ground.")
        elif len(my_territories) > 0 and my_largest_group < len(my_territories) * 0.6:
            goal = "CONSOLIDATE"
            headline = "Territory is fragmented — consolidating"
            detail = (f"Largest connected group is only {my_largest_group} of "
                       f"{len(my_territories)} territories. Reinforcement bonus scales with "
                       f"connected group size, so linking up matters more than raw expansion.")
        else:
            goal = "TARGET_WEAK"
            headline = "Even fight — hunting the softest target"
            detail = ("No side has a clear dice edge, so this turn focuses on the single "
                       "best-odds attack rather than a broad push.")

        return AgentThought(
            agent=self.name, headline=headline, detail=detail,
            data={"goal": goal, "dice_ratio": round(dice_ratio, 2),
                  "my_dice": my_dice, "enemy_dice": enemy_dice,
                  "my_largest_group": my_largest_group,
                  "border": len(border), "weak_border": len(weak_border)},
        )
