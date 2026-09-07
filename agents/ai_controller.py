"""
AIController
------------
The thing the human actually plays against. From the outside it is "the AI
opponent" (satisfies the human-vs-1-AI requirement); internally it
orchestrates three specialist agents in a fixed pipeline each turn
(satisfies the multi-agent requirement):

    StrategyAgent  -> decides a goal for the turn
    AttackAgent    -> repeatedly attacks while good moves exist under that goal
    DefenseAgent   -> places the turn's reinforcement pool once attacking stops

Every step emits an AgentThought which the caller (Flask/SocketIO layer)
streams to the frontend "Behind the Scenes" panel and replays as animated
dice battles.
"""
from .strategy_agent import StrategyAgent
from .attack_agent import AttackAgent
from .defense_agent import DefenseAgent


class AIController:
    def __init__(self, owner="ai"):
        self.owner = owner
        self.strategy = StrategyAgent(owner)
        self.attack = AttackAgent(owner)
        self.defense = DefenseAgent(owner)

    def run_turn(self, state):
        """Executes one full AI turn against `state` (mutates it in place).
        Returns a list of step dicts, each either a 'thought' or an
        'attack_result', in the order they should be replayed/animated."""
        steps = []

        strat_thought = self.strategy.think(state)
        steps.append({"type": "thought", "thought": vars(strat_thought)})
        goal = strat_thought.data["goal"]

        attacks_done = 0
        max_attacks = {"EXPAND": 6, "TARGET_WEAK": 3, "CONSOLIDATE": 1, "DEFEND": 1}.get(goal, 3)

        while attacks_done < max_attacks:
            attack_thought = self.attack.think(state, goal=goal)
            steps.append({"type": "thought", "thought": vars(attack_thought)})
            if "src" not in attack_thought.data:
                break
            src, dst = attack_thought.data["src"], attack_thought.data["dst"]
            result = state.attack(src, dst)
            steps.append({"type": "attack_result", "result": vars(result)})
            attacks_done += 1
            if state.winner:
                break

        if not state.winner:
            state.end_turn_and_reinforce(self.owner)
            defense_thought = self.defense.think(state, goal=goal)
            steps.append({"type": "thought", "thought": vars(defense_thought)})

        return steps
