from src.ecs import World
from src.sim.components import (
    Eliminated,
    Hitbox,
    Refuel,
    Renderable,
    Respawn,
    Score,
    ScoreReward,
    SpawnedAt,
    Tank,
    Transform,
    Trigger,
)
from src.sim.elimination import round_active
from src.sim.geometry import circle_touches_car
from src.sim.resources import EventLog, SimClock, SpawnSchedules


def trigger_system(world: World) -> None:
    """Fires every trigger a car touches, and applies its effects (score,
    refuel, respawn). Fuel now; hazards later.
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
        score.fuel_points += reward.points
        score.fuels += 1
        score.last_step += reward.points
        spawned = world.try_component(trigger_id, SpawnedAt)
        if spawned:
            score.fuel_ages.append(_steps_done(world) - spawned.step)
        renderable = world.try_component(car, Renderable)
        name = renderable.label if renderable else f"Car {car}"
        world.resource(EventLog).add(
            world.resource(SimClock).step,
            f"{name} reached a {reward.label} +{reward.points:g}",
            kind=reward.label,
        )
    refuel = world.try_component(trigger_id, Refuel)
    tank = world.try_component(car, Tank)
    if refuel and tank:  # up to the full tank (9a2)
        tank.level = min(tank.level + refuel.amount, tank.capacity)
    respawn = world.try_component(trigger_id, Respawn)
    if respawn:
        spot = world.component(trigger_id, Transform)
        spot.x, spot.y = next_spawn(world, respawn.spawner, trigger_id)
        spawned = world.try_component(trigger_id, SpawnedAt)
        if spawned:
            spawned.step = _steps_done(world)


def _steps_done(world: World) -> int:
    """Steps completed once the current step ends (the clock counts it
    later in the step).
    """
    return world.resource(SimClock).step + 1


def next_spawn(
    world: World, spawner: str, moving: int | None = None
) -> tuple[float, float]:
    """The next spot of a spawn schedule, kept away from the cars and
    from the other triggers of the same spawner (`moving`: the one
    being moved, not counted).
    """
    cars = [
        (transform.x, transform.y)
        for _, (transform, _) in world.query(Transform, Hitbox)
    ]
    others = [
        (spot.x, spot.y)
        for trigger, (respawn, spot) in world.query(Respawn, Transform)
        if trigger != moving and respawn.spawner == spawner
    ]
    return world.resource(SpawnSchedules).get(spawner).next_spot(
        cars, others
    )
