import numpy as np
import torch

from src.agents.store import LoadedAgent, load_agent
from src.drivers.actions import CANONICAL_ACTIONS, Action
from src.drivers.base import Driver
from src.replay.recorder import agent_driver


class AgentDriver(Driver):
    """A learned agent behind the driver interface. It decides every
    `action_repeat` steps and holds the action in between.

    deterministic: always pick the highest-scoring action (for watching
    and evaluation). Otherwise sample from the policy, seeded (training).
    """

    def __init__(self, agent: LoadedAgent, deterministic: bool = True) -> None:
        self.agent = agent
        self.name = agent.agent_id
        self.deterministic = deterministic
        self.reset(0)

    @staticmethod
    def load(agent: str, checkpoint: str | None = None) -> "AgentDriver":
        return AgentDriver(load_agent(agent, checkpoint, prefer_best=True))

    def reset(self, seed: int | None = None) -> None:
        self._steps = 0
        self._action: Action = CANONICAL_ACTIONS[0]
        self._generator = torch.Generator().manual_seed(seed or 0)

    def act(self, observation: np.ndarray) -> Action:
        if self._steps % self.agent.spec.action_repeat == 0:
            with torch.inference_mode():
                logits, _ = self.agent.network(
                    torch.as_tensor(observation).unsqueeze(0)
                )
            if self.deterministic:
                index = int(logits.argmax())
            else:
                probabilities = torch.softmax(logits[0], dim=0)
                index = int(
                    torch.multinomial(
                        probabilities, 1, generator=self._generator
                    )
                )
            self._action = CANONICAL_ACTIONS[index]
        self._steps += 1
        return self._action

    def record(self) -> dict:
        return agent_driver(self.agent.agent_id, self.agent.checkpoint)

    @property
    def label(self) -> str:
        return f"{self.agent.agent_id} (agent)"
