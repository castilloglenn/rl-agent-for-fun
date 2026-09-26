"""Car health and wall hits (roadmap step 5a4)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.envs.maze_car.env import MazeCarEnv  # noqa: E402
from src.render import theme  # noqa: E402
from src.render.renderer import Renderer  # noqa: E402
from src.sim.components import (  # noqa: E402
    ActionInput,
    Eliminated,
    Health,
    Motion,
    Renderable,
    Transform,
)
from src.sim.factories import create_start_car, create_world  # noqa: E402
import re  # noqa: E402

from src.sim.resources import (  # noqa: E402
    EventLog,
    Field,
    SimClock,
    SimConfig,
)
from src.sim.rules import Collisions, Rules, RulesError, load_rules  # noqa
from src.utils.types import Colors  # noqa: E402

COAST = ActionInput()
GAS = ActionInput(gas=True)
SPS = 120  # simulation steps per second


def _world(rules="standard"):
    config = get_maze_car_config()
    config.rules = rules
    world = create_world(config)
    car = create_start_car(world, label="Tester")
    return world, car


def _aim_at_right_wall(world, car, speed, angle=0.0, gap=30.0):
    """Puts the car `gap` px (nose to wall) from the right wall, moving at
    `speed` px/s with heading `angle`.
    """
    field = world.resource(Field).rect
    transform = world.component(car, Transform)
    transform.x, transform.y, transform.angle = (
        field.right - 12 - gap,
        field.centery,
        angle,
    )
    world.component(car, Motion).speed = speed / SPS


def _until_contact(world, car, action=COAST, steps=600):
    health = world.component(car, Health)
    world.add_component(car, action)
    for _ in range(steps):
        world.step()
        if health.contact_step is not None:
            return
    raise AssertionError("never touched the wall")


def _texts(world):
    return [event.text for event in world.resource(EventLog).events]


# The damage rule


def test_damage_rises_from_safe_to_lethal_speed():
    collisions = Collisions(health=100, safe_speed=60, lethal_speed=240)
    assert collisions.damage(30) == 0
    assert collisions.damage(60) == 0
    assert collisions.damage(150) == pytest.approx(50)
    assert collisions.damage(240) == 100
    assert collisions.damage(400) == 100


def test_classic_rules_make_any_hit_lethal():
    collisions = load_rules("classic").collisions
    assert collisions.damage(0.01) == collisions.health


@pytest.mark.parametrize(
    "change, message",
    [
        ({"health": 0}, "health must be positive"),
        ({"safe_speed": 300}, "safe_speed <= lethal_speed"),
        ({"safe_speed": -1}, "safe_speed <= lethal_speed"),
    ],
)
def test_invalid_collisions_are_rejected(change, message):
    data = load_rules("standard").to_dict()
    data["collisions"] = {**data["collisions"], **change}
    with pytest.raises(RulesError, match=message):
        Rules.from_dict(data)


def test_rules_need_collisions():
    data = load_rules("standard").to_dict()
    del data["collisions"]
    with pytest.raises(RulesError, match="need collisions"):
        Rules.from_dict(data)


# Hits in the simulation


def test_a_head_on_hit_costs_health_by_impact_speed():
    world, car = _world()
    _aim_at_right_wall(world, car, speed=150)
    _until_contact(world, car)  # coasting: it slows down a little first
    health = world.component(car, Health)
    (text,) = _texts(world)
    impact = float(re.search(r"at ([\d.]+) px/s", text).group(1))
    assert 100 < impact < 150
    expected = world.resource(Rules).collisions.damage(impact)
    assert 100 - health.current == pytest.approx(expected, abs=0.6)
    assert world.component(car, Motion).speed == 0  # it stops
    assert not world.try_component(car, Eliminated)


def test_grazing_a_wall_hurts_less_than_hitting_it_head_on():
    lost = {}
    for angle in (0, 60):
        world, car = _world()
        _aim_at_right_wall(world, car, speed=200, angle=angle)
        _until_contact(world, car)
        lost[angle] = 100 - world.component(car, Health).current
    # 200 px/s at 60°: about 100 px/s into the wall.
    assert 0 < lost[60] < lost[0] / 2


def test_a_slow_bump_does_no_damage_and_is_logged_once():
    world, car = _world()
    _aim_at_right_wall(world, car, speed=40, gap=2)
    _until_contact(world, car)
    world.add_component(car, GAS)
    for _ in range(120):  # keep pushing into the wall
        world.step()
    health = world.component(car, Health)
    assert health.current == 100 and health.last_hit_step is None
    assert _texts(world) == ["Tester bumped the wall"]
    assert health.contacts == 1  # pushing on is the same contact


def test_after_a_hit_the_car_can_back_away():
    world, car = _world()
    _aim_at_right_wall(world, car, speed=150)
    _until_contact(world, car)
    x = world.component(car, Transform).x
    world.add_component(car, ActionInput(reverse=True))
    for _ in range(60):
        world.step()
    assert world.component(car, Transform).x < x - 5


def test_hits_add_up_to_a_wreck():
    world, car = _world()
    health = world.component(car, Health)
    for _ in range(3):  # about -50 each
        _aim_at_right_wall(world, car, speed=150)
        health.contact_step = None
        _until_contact(world, car)
    assert health.current == 0
    assert world.component(car, Eliminated).reason == "wrecked"
    assert _texts(world)[-2:] == [
        "Tester was wrecked",
        "Round over: every car is out",
    ]


def test_a_lethal_hit_wrecks_at_once():
    world, car = _world()
    _aim_at_right_wall(world, car, speed=300)
    _until_contact(world, car)
    assert world.component(car, Health).current == 0
    assert world.component(car, Eliminated).reason == "wrecked"


# The agent's view


def test_health_is_observed_and_damage_is_rewarded():
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config)
    env.reset(seed=0)
    _aim_at_right_wall(env.world, env.car, speed=150)
    rewards, observation = [], None
    for _ in range(600):
        observation, reward, *_, info = env.step((False,) * 5)
        rewards.append(reward - info["points"])
        if info["health"] < 100:
            break
    lost = (100 - info["health"]) / 100
    assert observation[-1] == pytest.approx(1 - lost)
    # The default profile: -100 for the contact, -500 per full health,
    # and -0.25 for ending the step stopped against the wall.
    assert rewards[-1] == pytest.approx(-100 - 500 * lost - 0.25)
    assert all(r == 0 for r in rewards[:-1])


# The window


def _renderer_and_world():
    config = get_maze_car_config()
    world, car = _world()
    return Renderer(config), world, car


def test_a_hit_car_blinks_red_then_returns_to_its_color():
    renderer, world, car = _renderer_and_world()
    renderable = world.component(car, Renderable)
    sim = world.resource(SimConfig)
    _aim_at_right_wall(world, car, speed=150)
    _until_contact(world, car)
    hit = world.resource(SimClock).step

    def color_at(step):
        return renderer._car_color(world, car, renderable, step, sim)

    assert color_at(hit) == theme.HIT
    assert color_at(hit + 12) == Colors.SKY_BLUE  # 0.1 s later: off
    assert color_at(hit + 24) == theme.HIT  # on again
    assert color_at(hit + 60) == Colors.SKY_BLUE  # 0.5 s later: done


def test_a_wrecked_car_is_dark_red():
    renderer, world, car = _renderer_and_world()
    renderable = world.component(car, Renderable)
    _aim_at_right_wall(world, car, speed=300)
    _until_contact(world, car)
    step = world.resource(SimClock).step
    sim = world.resource(SimConfig)
    assert renderer._car_color(world, car, renderable, step, sim) == (
        theme.WRECKED
    )


def test_leaving_and_touching_again_is_a_new_contact():
    world, car = _world()
    health = world.component(car, Health)
    _aim_at_right_wall(world, car, speed=40, gap=2)
    _until_contact(world, car)
    world.add_component(car, ActionInput(reverse=True))
    for _ in range(30):  # back away
        world.step()
    assert health.contacts == 1
    world.add_component(car, GAS)
    for _ in range(120):  # and touch it again
        world.step()
    assert health.contacts == 2


# Scraping


def _scrape(world, car, steps=30, angle=45):
    """Drives into the right wall at an angle, then keeps going along it."""
    _aim_at_right_wall(world, car, speed=40, angle=angle, gap=2)
    _until_contact(world, car)
    health = world.component(car, Health)
    start_y = world.component(car, Transform).y
    world.add_component(car, GAS)
    for _ in range(steps):
        world.step()
    return health, abs(world.component(car, Transform).y - start_y)


def test_scraping_costs_health_by_distance():
    world, car = _world()
    health, slid = _scrape(world, car)
    assert slid > 5
    rate = world.resource(Rules).collisions.scrape_damage  # 0.1 per px
    assert 100 - health.current == pytest.approx(rate * slid, rel=0.1)
    assert health.contacts == 1  # one scrape, one contact


def test_a_head_on_push_scrapes_nothing():
    world, car = _world()
    _aim_at_right_wall(world, car, speed=40, gap=2)
    _until_contact(world, car)
    world.add_component(car, GAS)
    for _ in range(120):
        world.step()
    assert world.component(car, Health).current == 100


def test_a_scrape_is_logged_once_when_it_ends():
    world, car = _world()
    _scrape(world, car)
    assert not any("scraped" in text for text in _texts(world))  # ongoing
    world.add_component(car, ActionInput(reverse=True))
    for _ in range(30):
        world.step()
    scrapes = [text for text in _texts(world) if "scraped" in text]
    assert len(scrapes) == 1
    pattern = r"Tester scraped the wall for \d+ px: -\d+ health"
    assert re.match(pattern, scrapes[0])


def test_a_long_scrape_wrecks_the_car():
    world, car = _world()
    health, _ = _scrape(world, car, steps=0, angle=60)  # on the wall
    health.current = 1.0  # one health left: 10 px of scraping
    world.add_component(car, GAS)
    for _ in range(240):
        world.step()
        if world.try_component(car, Eliminated):
            break
    assert world.component(car, Eliminated).reason == "wrecked"
    assert health.current == 0
    assert any("scraped" in text for text in _texts(world))


def test_classic_rules_have_no_scraping():
    assert load_rules("classic").collisions.scrape_damage == 0


def test_scrape_damage_cant_be_negative():
    data = load_rules("standard").to_dict()
    data["collisions"]["scrape_damage"] = -0.1
    with pytest.raises(RulesError, match="scrape_damage"):
        Rules.from_dict(data)
