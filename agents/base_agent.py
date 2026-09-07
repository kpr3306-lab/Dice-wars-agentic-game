"""
Base class for all agents in the pipeline. Every agent exposes a `.think()`
call that returns both a *decision* and a *reasoning trace* — the trace is
what powers the "Behind the Scenes" live panel, so it must always be
human-readable, not just a dict of numbers.
"""
from dataclasses import dataclass, field


@dataclass
class AgentThought:
    agent: str          # "strategy" | "attack" | "defense"
    headline: str        # one-line summary shown in the UI feed
    detail: str           # 1-3 sentences of reasoning
    data: dict = field(default_factory=dict)  # raw numbers, for debugging/logging


class BaseAgent:
    name = "base"

    def __init__(self, owner: str):
        self.owner = owner   # which side this agent plays for, always "ai" here

    def think(self, state, **kwargs) -> AgentThought:
        raise NotImplementedError
