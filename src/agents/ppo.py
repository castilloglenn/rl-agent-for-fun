"""PPO (Proximal Policy Optimization): advantages and the update step.

The training loop that collects experience is in src/experiments/training.py.
"""

from dataclasses import dataclass

import torch

from src.agents.network import PolicyNetwork
from src.agents.trainer import TrainerSpec


@dataclass
class Rollout:
    """One rollout of decisions, in order. dones[t] is 1 when the episode
    ended after decision t (wrecked or time up: no value beyond it).
    """

    observations: torch.Tensor  # (T, observation size)
    actions: torch.Tensor  # (T,) action indices
    log_probs: torch.Tensor  # (T,) of the actions, when they were taken
    values: torch.Tensor  # (T,)
    rewards: torch.Tensor  # (T,) reward profile, summed over held steps
    dones: torch.Tensor  # (T,) 0 or 1
    last_value: float  # value of the observation after the last decision


def advantages(
    rollout: Rollout, gamma: float, gae_lambda: float
) -> tuple[torch.Tensor, torch.Tensor]:
    """GAE (Generalized Advantage Estimation): how much better each
    decision went than the value head expected. Returns (advantages,
    returns), where returns are what the value head learns.
    """
    count = len(rollout.rewards)
    result = torch.zeros(count)
    running = 0.0
    for t in reversed(range(count)):
        next_value = (
            rollout.last_value if t == count - 1 else rollout.values[t + 1]
        )
        alive = 1.0 - rollout.dones[t]
        delta = (
            rollout.rewards[t] + gamma * next_value * alive - rollout.values[t]
        )
        running = delta + gamma * gae_lambda * alive * running
        result[t] = running
    return result, result + rollout.values


@dataclass(frozen=True)
class UpdateStats:
    policy_loss: float
    value_loss: float
    entropy: float
    approx_kl: float  # how far the policy moved (KL divergence estimate)
    clip_fraction: float  # share of decisions hitting the clip limit


def update(
    network: PolicyNetwork,
    optimizer: torch.optim.Optimizer,
    rollout: Rollout,
    trainer: TrainerSpec,
    generator: torch.Generator,
) -> UpdateStats:
    """Learns from one rollout: `epochs` passes in shuffled minibatches."""
    advantage, returns = advantages(rollout, trainer.gamma, trainer.gae_lambda)
    count = len(rollout.rewards)
    totals = {name: 0.0 for name in UpdateStats.__dataclass_fields__}
    batches = 0
    network.train()
    for _ in range(trainer.epochs):
        order = torch.randperm(count, generator=generator)
        for start in range(0, count, trainer.minibatch):
            index = order[start : start + trainer.minibatch]
            logits, values = network(rollout.observations[index])
            log_probs = torch.log_softmax(logits, dim=-1)
            new_log_prob = log_probs.gather(
                1, rollout.actions[index].unsqueeze(1)
            ).squeeze(1)
            log_ratio = new_log_prob - rollout.log_probs[index]
            ratio = log_ratio.exp()

            batch_advantage = advantage[index]
            if len(index) > 1:
                batch_advantage = (batch_advantage - batch_advantage.mean()) / (
                    batch_advantage.std() + 1e-8
                )
            clipped = ratio.clamp(1 - trainer.clip, 1 + trainer.clip)
            policy_loss = -torch.min(
                ratio * batch_advantage, clipped * batch_advantage
            ).mean()
            value_loss = 0.5 * (returns[index] - values).pow(2).mean()
            entropy = -(log_probs.exp() * log_probs).sum(-1).mean()
            loss = (
                policy_loss
                + trainer.value_coef * value_loss
                - trainer.entropy * entropy
            )

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                network.parameters(), trainer.max_grad_norm
            )
            optimizer.step()

            with torch.no_grad():
                totals["policy_loss"] += float(policy_loss)
                totals["value_loss"] += float(value_loss)
                totals["entropy"] += float(entropy)
                totals["approx_kl"] += float(((ratio - 1) - log_ratio).mean())
                totals["clip_fraction"] += float(
                    ((ratio - 1).abs() > trainer.clip).float().mean()
                )
            batches += 1
    network.eval()
    return UpdateStats(
        **{name: total / batches for name, total in totals.items()}
    )
