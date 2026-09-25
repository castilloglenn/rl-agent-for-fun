import math

from src.ecs import World
from src.sim.components import Eliminated, Motion, Score
from src.sim.elimination import round_active
from src.sim.rules import Rules


def reward_system(world: World) -> None:
    """+1 point per `distance_step` px driven forward. Runs right after
    movement, and starts each car's `last_step` tally for this step.
    """
    if not round_active(world):
        return
    distance_step = world.resource(Rules).scoring.distance_step
    for _, (score,) in world.query(Score):
        score.last_step = 0.0
    for _, (motion, score) in world.query(
        Motion, Score, exclude=(Eliminated,)
    ):
        if motion.moved <= 0:  # stopped or reversing earns nothing
            continue
        score.distance_carry += motion.moved
        points = math.floor(score.distance_carry / distance_step)
        if points:
            score.distance_carry -= points * distance_step
            score.distance_points += points
            score.total += points
            score.last_step += points
