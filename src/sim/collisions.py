"""Wall hits: a car that touches a wall loses the part of its motion into
the wall and slides along it with the rest (head-on, it stops). The first
step of a contact costs health by the impact speed (the rules'
collisions). At 0 health it is wrecked.

    bump     a hit at or below the safe speed: no damage
    hit      a hit that costs health
    scrape   sliding along a wall: costs health by the distance slid
    wrecked  health reached 0: the car is out of the round
"""

from src.ecs import World
from src.sim.components import Health, Motion, Renderable
from src.sim.elimination import eliminate
from src.sim.resources import EventLog, SimClock
from src.sim.rules import Rules


def hit_wall(
    world: World, car: int, impact: float, keep: float = 0.0
) -> None:
    """The car touched a wall at `impact` px/s (its speed into the wall).
    keep: the share of its motion along the wall (0 head-on, 1 for a
    blocked turn). A new contact shrinks the speed to that share and
    costs health.
    """
    step = world.resource(SimClock).step
    health = world.component(car, Health)
    motion = world.component(car, Motion)
    # Pushing on into the wall is the same contact, not a new one: the
    # wall already took the motion into it, so the car just scrapes
    # along (a head-on push stays stopped), with no more damage.
    new_contact = health.contact_step not in (step, step - 1)
    health.contact_step = step
    if not new_contact:
        if keep == 0:
            motion.speed = 0.0
        return
    motion.speed *= keep
    health.contacts += 1

    damage = min(
        world.resource(Rules).collisions.damage(impact), health.current
    )
    renderable = world.try_component(car, Renderable)
    name = renderable.label if renderable else f"Car {car}"
    log = world.resource(EventLog)
    if damage <= 0:
        log.add(step, f"{name} bumped the wall", kind="bump")
        return

    health.current -= damage
    health.last_hit_step = step
    health.last_hit_damage = damage
    log.add(
        step,
        f"{name} hit the wall at {impact:,.0f} px/s: -{damage:,.0f} health",
        kind="hit",
        danger=True,
    )
    if health.current <= 0:
        health.current = 0.0
        eliminate(world, car, "wrecked")


def scrape_wall(world: World, car: int, distance: float) -> None:
    """The car slid `distance` px along a wall: it costs health (the
    rules' scrape_damage per px), and can wreck it.
    """
    if distance <= 0:
        return
    health = world.component(car, Health)
    rate = world.resource(Rules).collisions.scrape_damage
    damage = min(rate * distance, health.current)
    health.scraped += distance
    if damage <= 0:
        return
    step = world.resource(SimClock).step
    health.current -= damage
    health.scrape_damage += damage
    health.last_hit_step = step  # red while scraping
    health.last_hit_damage = damage
    if health.current <= 0:
        health.current = 0.0
        end_scrape(world, car, force=True)
        eliminate(world, car, "wrecked")


def end_scrape(world: World, car: int, force: bool = False) -> None:
    """Logs a scrape once it's over (the car left the wall), as one event
    rather than one per step.
    """
    health = world.component(car, Health)
    step = world.resource(SimClock).step
    if not health.scraped or (health.contact_step == step and not force):
        return
    if health.scrape_damage > 0:
        renderable = world.try_component(car, Renderable)
        name = renderable.label if renderable else f"Car {car}"
        world.resource(EventLog).add(
            step,
            f"{name} scraped the wall for {health.scraped:,.0f} px: "
            f"-{health.scrape_damage:,.0f} health",
            kind="scrape",
            danger=True,
        )
    health.scraped = health.scrape_damage = 0.0
