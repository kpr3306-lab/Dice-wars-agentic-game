"""
Dice Wars core game engine.
Pure game logic - no Flask, no rendering. Deterministic given a random seed,
easy to unit test, easy for agents to simulate against.
"""
import json
import os
import random
from dataclasses import dataclass, field

MAX_DICE = 8
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MAPS = {
    "skirmish_isle": "Skirmish Isle (small, fast)",
    "twin_peninsulas": "Twin Peninsulas (medium)",
    "grand_continent": "Grand Continent (large)",
}


def load_map(map_id: str) -> dict:
    path = os.path.join(DATA_DIR, f"{map_id}.json")
    with open(path) as f:
        return json.load(f)


@dataclass
class Territory:
    id: int
    owner: str          # "human" | "ai"
    dice: int
    neighbors: list
    polygon: list
    centroid: list


@dataclass
class AttackResult:
    attacker_id: int
    defender_id: int
    attacker_rolls: list
    defender_rolls: list
    attacker_total: int
    defender_total: int
    success: bool
    attacker_dice_before: int
    defender_dice_before: int


class GameState:
    """Full mutable state for one match."""

    def __init__(self, map_id: str, seed: int | None = None):
        self.map_id = map_id
        self.map_data = load_map(map_id)
        self.rng = random.Random(seed)
        self.territories: dict[int, Territory] = {}
        self.turn_owner = "human"       # whose turn it is
        self.turn_number = 1
        self.winner = None
        self.log = []                    # human-readable event log
        self.last_attack: AttackResult | None = None
        self.pending_reinforcements = 0  # dice the current player still needs to place
        self._setup_board()

    # ---------- setup ----------

    def _setup_board(self):
        raw = self.map_data["territories"]
        ids = [t["id"] for t in raw]
        self.rng.shuffle(ids)
        half = len(ids) // 2
        human_ids = set(ids[:half])
        for t in raw:
            owner = "human" if t["id"] in human_ids else "ai"
            self.territories[t["id"]] = Territory(
                id=t["id"], owner=owner,
                dice=self.rng.randint(1, 3),
                neighbors=t["neighbors"],
                polygon=t["polygon"], centroid=t["centroid"],
            )
        self._top_up_random_dice()

    def _top_up_random_dice(self, extra_pool=None):
        """Classic Dice Wars opening: distribute a pool of random extra dice
        one at a time onto random owned territories under the cap, per player."""
        for owner in ("human", "ai"):
            pool = extra_pool if extra_pool is not None else len(self.owned_by(owner)) * 2
            owned = self.owned_by(owner)
            for _ in range(pool):
                candidates = [t for t in owned if self.territories[t].dice < MAX_DICE]
                if not candidates:
                    break
                tid = self.rng.choice(candidates)
                self.territories[tid].dice += 1

    # ---------- queries ----------

    def owned_by(self, owner: str) -> list[int]:
        return [tid for tid, t in self.territories.items() if t.owner == owner]

    def is_adjacent_enemy(self, src: int, dst: int, owner: str) -> bool:
        t_src, t_dst = self.territories[src], self.territories[dst]
        return (t_src.owner == owner and t_dst.owner != owner
                and dst in t_src.neighbors and t_src.dice > 1)

    def valid_attacks(self, owner: str) -> list[tuple[int, int]]:
        moves = []
        for tid in self.owned_by(owner):
            t = self.territories[tid]
            if t.dice <= 1:
                continue
            for n in t.neighbors:
                if self.territories[n].owner != owner:
                    moves.append((tid, n))
        return moves

    def connected_groups(self, owner: str) -> list[set]:
        """Return list of connected territory clusters owned by `owner`."""
        owned = set(self.owned_by(owner))
        groups = []
        seen = set()
        for start in owned:
            if start in seen:
                continue
            stack = [start]
            group = set()
            while stack:
                cur = stack.pop()
                if cur in group:
                    continue
                group.add(cur)
                for n in self.territories[cur].neighbors:
                    if n in owned and n not in group:
                        stack.append(n)
            seen |= group
            groups.append(group)
        return groups

    def largest_group_size(self, owner: str) -> int:
        groups = self.connected_groups(owner)
        return max((len(g) for g in groups), default=0)

    def win_probability(self, attacker_dice: int, defender_dice: int) -> float:
        """Approximate win probability via Monte Carlo (fast, good enough for agents)."""
        if attacker_dice <= 1:
            return 0.0
        wins = 0
        trials = 400
        for _ in range(trials):
            a = sorted((self.rng.randint(1, 6) for _ in range(attacker_dice)), reverse=True)
            d = sorted((self.rng.randint(1, 6) for _ in range(defender_dice)), reverse=True)
            if sum(a) > sum(d):
                wins += 1
        return wins / trials

    # ---------- actions ----------

    def attack(self, src: int, dst: int) -> AttackResult:
        t_src, t_dst = self.territories[src], self.territories[dst]
        a_dice, d_dice = t_src.dice, t_dst.dice
        a_rolls = sorted((self.rng.randint(1, 6) for _ in range(a_dice)), reverse=True)
        d_rolls = sorted((self.rng.randint(1, 6) for _ in range(d_dice)), reverse=True)
        a_total, d_total = sum(a_rolls), sum(d_rolls)
        success = a_total > d_total

        result = AttackResult(
            attacker_id=src, defender_id=dst,
            attacker_rolls=a_rolls, defender_rolls=d_rolls,
            attacker_total=a_total, defender_total=d_total,
            success=success,
            attacker_dice_before=a_dice, defender_dice_before=d_dice,
        )

        if success:
            moved = a_dice - 1
            t_dst.owner = t_src.owner
            t_dst.dice = moved
            t_src.dice = 1
            self.log.append(f"T{src}→T{dst}: {a_total} vs {d_total} — CAPTURED")
        else:
            t_src.dice = 1
            self.log.append(f"T{src}→T{dst}: {a_total} vs {d_total} — repelled")

        self.last_attack = result
        self._check_winner()
        return result

    def end_turn_and_reinforce(self, owner: str) -> int:
        """Called once a player is done attacking. Computes reinforcement pool."""
        bonus = self.largest_group_size(owner)
        bonus = max(bonus, 1)
        self.pending_reinforcements = bonus
        return bonus

    def place_reinforcement(self, owner: str, territory_id: int) -> bool:
        t = self.territories.get(territory_id)
        if not t or t.owner != owner or self.pending_reinforcements <= 0:
            return False
        if t.dice >= MAX_DICE:
            return False
        t.dice += 1
        self.pending_reinforcements -= 1
        return True

    def auto_place_reinforcements(self, owner: str):
        """Fallback: dump any remaining reinforcements onto border territories
        with the fewest dice (used if a player doesn't manually place them)."""
        while self.pending_reinforcements > 0:
            owned = [tid for tid in self.owned_by(owner) if self.territories[tid].dice < MAX_DICE]
            if not owned:
                break
            border = [tid for tid in owned if any(
                self.territories[n].owner != owner for n in self.territories[tid].neighbors)]
            pool = border or owned
            pool.sort(key=lambda tid: self.territories[tid].dice)
            self.territories[pool[0]].dice += 1
            self.pending_reinforcements -= 1

    def switch_turn(self):
        self.turn_owner = "ai" if self.turn_owner == "human" else "human"
        if self.turn_owner == "human":
            self.turn_number += 1

    def _check_winner(self):
        if not self.owned_by("human"):
            self.winner = "ai"
        elif not self.owned_by("ai"):
            self.winner = "human"

    # ---------- serialization ----------

    def to_dict(self):
        return {
            "map_id": self.map_id,
            "width": self.map_data["width"],
            "height": self.map_data["height"],
            "island_outline": self.map_data["island_outline"],
            "turn_owner": self.turn_owner,
            "turn_number": self.turn_number,
            "winner": self.winner,
            "pending_reinforcements": self.pending_reinforcements,
            "log": self.log[-30:],
            "territories": {
                str(tid): {
                    "id": t.id, "owner": t.owner, "dice": t.dice,
                    "neighbors": t.neighbors, "polygon": t.polygon, "centroid": t.centroid,
                } for tid, t in self.territories.items()
            },
        }
