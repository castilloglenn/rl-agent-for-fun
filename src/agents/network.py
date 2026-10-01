import torch
from torch import nn

from src.agents.model import ModelSpec
from src.drivers.actions import CANONICAL_NAMES
from src.sim.observation import OBSERVATION_NAMES

# Stopped, an agent must press gas or reverse (7f6, decision 060): at
# speed 0 the other pedals (none, brake) can't move the car, and steering
# needs speed, so picking them is sitting still. Those actions get a score
# so low their probability is 0 (large, not -inf: entropy stays finite).
SPEED = OBSERVATION_NAMES.index("speed")
MASKED = -1e9
MOVES = torch.tensor(
    [name.split("+")[1] in ("gas", "reverse") for name in CANONICAL_NAMES]
)


def mask_stopped(
    logits: torch.Tensor, observations: torch.Tensor
) -> torch.Tensor:
    """`logits` with the actions that can't move a stopped car blocked,
    for each observation whose speed is 0.
    """
    if logits.shape[-1] != len(MOVES):
        return logits
    stopped = observations[..., SPEED] == 0
    blocked = stopped.unsqueeze(-1) & ~MOVES.to(logits.device)
    return logits.masked_fill(blocked, MASKED)

_ACTIVATIONS = {"tanh": nn.Tanh, "relu": nn.ReLU}


def _mlp(sizes: list[int], activation: str) -> nn.Sequential:
    layers: list[nn.Module] = []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:
            layers.append(_ACTIVATIONS[activation]())
    return nn.Sequential(*layers)


class PolicyNetwork(nn.Module):
    """Actor-critic: a policy head (one score per action) and a value head
    (how good the situation looks), as separate networks of the model's
    shape. PPO (5a2) trains both. Imitation (5b) trains the policy.
    Stopped, the policy only picks gas or reverse (`mask_stopped`, 7f6).
    """

    def __init__(
        self, spec: ModelSpec, observation_size: int, action_count: int
    ) -> None:
        super().__init__()
        hidden = list(spec.hidden)
        self.policy = _mlp(
            [observation_size, *hidden, action_count], spec.activation
        )
        self.value = _mlp([observation_size, *hidden, 1], spec.activation)

    def forward(
        self, observations: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Action scores (logits) and values, for a batch of observations."""
        logits = mask_stopped(self.policy(observations), observations)
        return logits, self.value(observations).squeeze(-1)
