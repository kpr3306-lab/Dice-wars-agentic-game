"""
Defense Agent
-------------
Runs once per AI turn, after the Attack Agent has finished (i.e. once the
reinforcement pool is known). Distributes the pool one die at a time,
prioritizing exposed border territories, weighted by the strategy goal.
"""
from .base_agent import BaseAgent, AgentThought


class DefenseAgent(BaseAgent):
    name = "defense"

    def vulnerability(self, state, tid, owner, enemy):
        t = state.territories[tid]
        threat = sum(state.territories[n].dice for n in t.neighbors
                     if state.territories[n].owner == enemy)
        return threat - t.dice

    def think(self, state, goal="TARGET_WEAK", **kwargs) -> AgentThought:
        owner = self.owner
        enemy = "human" if owner == "ai" else "ai"
        pool = state.pending_reinforcements
        placements = []

        if pool <= 0:
            return AgentThought(
                agent=self.name, headline="No reinforcements to place this turn",
                detail="Connected territory bonus was 0 or already spent.",
                data={"placements": []},
            )

        remaining = pool
        guard = 0
        while remaining > 0 and guard < 200:
            guard += 1
            owned = [tid for tid in state.owned_by(owner) if state.territories[tid].dice < 8]
            if not owned:
                break
            owned.sort(key=lambda tid: self.vulnerability(state, tid, owner, enemy), reverse=True)
            target = owned[0]
            state.place_reinforcement(owner, target)
            placements.append(target)
            remaining -= 1

        counts = {}
        for tid in placements:
            counts[tid] = counts.get(tid, 0) + 1
        summary = ", ".join(f"T{tid} (+{n})" for tid, n in counts.items())
        headline = f"Reinforcing {len(counts)} territor{'y' if len(counts)==1 else 'ies'}"
        detail = (f"Distributed {pool} reinforcement dice to the most vulnerable border "
                   f"positions (enemy threat minus own dice): {summary}.")
        return AgentThought(
            agent=self.name, headline=headline, detail=detail,
            data={"placements": placements, "pool": pool},
        )
