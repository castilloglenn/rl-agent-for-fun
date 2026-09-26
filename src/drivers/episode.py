from dataclasses import dataclass

from src.drivers.base import Driver


@dataclass(frozen=True)
class EpisodeResult:
    seed: int | None
    steps: int
    score: float
    distance_points: float
    checkpoints: int
    reward: float  # agent reward total, from the env's reward profile
    ended_by: str | None  # "wrecked", "time", or None if cut short


def run_episode(
    env, driver: Driver, seed: int | None = None, max_steps: int | None = None
) -> EpisodeResult:
    """Plays one game with `driver`, headless. The runner (4h) and the
    evaluation suite (5a) build on this.
    """
    observation, _ = env.reset(seed=seed)
    driver.reset(seed)
    steps = 0
    terminated = truncated = False
    info = {}
    while not (terminated or truncated):
        observation, _, terminated, truncated, info = env.step(
            driver.act(observation)
        )
        steps += 1
        if max_steps is not None and steps >= max_steps:
            break
    return episode_result(env, seed, steps, truncated, info)


def episode_result(
    env, seed: int | None, steps: int, truncated: bool, info: dict
) -> EpisodeResult:
    """The result of the env's current game, after `steps` steps."""
    from src.sim.components import Score

    score = env.world.component(env.car, Score)
    ended_by = info.get("eliminated") or ("time" if truncated else None)
    return EpisodeResult(
        seed=seed,
        steps=steps,
        score=score.total,
        distance_points=score.distance_points,
        checkpoints=score.checkpoints,
        reward=env.round_reward,
        ended_by=ended_by,
    )
