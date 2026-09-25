from src.ecs import World
from src.sim.components import (
    Eliminated,
    Hitbox,
    Renderable,
    Respawn,
    Score,
    ScoreReward,
    Transform,
    Trigger,
)
from src.sim.elimination import round_active
from src.sim.geometry import circle_touches_car
from src.sim.resources import EventLog, SimClock, SpawnSchedules


def trigger_system(world: World) -> None:
    """Fires every trigger a car touches, and applies its effects (score,
    respawn). Checkpoints now; fuel and hazards later.
    """
    if not round_active(world):
        return
    cars = world.query(Transform, Hitbox, Score, exclude=(Eliminated,))
    for trigger_id, (trigger, spot) in world.query(Trigger, Transform):
        for car, (transform, hitbox, score) in cars:
            touching = circle_touches_car(
                spot.x,
                spot.y,
                trigger.radius,
                transform.x,
                transform.y,
                transform.angle,
                hitbox.width,
                hitbox.height,
            )
            if touching:
                _fire(world, trigger_id, car, score)
                break  # one car per trigger per step, lowest ID first


def _fire(world: World, trigger_id: int, car: int, score: Score) -> None:
    reward = world.try_component(trigger_id, ScoreReward)
    if reward:
        score.total += reward.points
        score.checkpoint_points += reward.points
        score.checkpoints += 1
        score.last_step += reward.points
        renderable = world.try_component(car, Renderable)
        name = renderable.label if renderable else f"Car {car}"
        world.resource(EventLog).add(
            world.resource(SimClock).step,
            f"{name} reached a {reward.label} +{reward.points:g}",
            kind=reward.label,
        )
    respawn = world.try_component(trigger_id, Respawn)
    if respawn:
        spot = world.component(trigger_id, Transform)
        spot.x, spot.y = next_spawn(world, respawn.spawner)


def next_spawn(world: World, spawner: str) -> tuple[float, float]:
    """The next spot of a spawn schedule, kept away from the cars."""
    cars = [
        (transform.x, transform.y)
        for _, (transform, _) in world.query(Transform, Hitbox)
    ]
    return world.resource(SpawnSchedules).get(spawner).next_spot(cars)
