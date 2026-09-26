import torch
from torch import nn

from src.agents.model import ModelSpec

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
        return self.policy(observations), self.value(observations).squeeze(-1)
