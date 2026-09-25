from dataclasses import dataclass

import pytest

from src.ecs import World


@dataclass
class Position:
    x: int = 0


@dataclass
class Velocity:
    dx: int = 0


@dataclass
class Tag:
    pass


@dataclass
class Config:
    speed: int = 1


def test_create_entity_assigns_increasing_ids():
    world = World()
    assert [world.create_entity() for _ in range(3)] == [1, 2, 3]


def test_component_access():
    world = World()
    position = Position(5)
    entity = world.create_entity(position)

    assert world.component(entity, Position) is position
    assert world.try_component(entity, Velocity) is None
    assert world.has_components(entity, Position)
    assert not world.has_components(entity, Position, Velocity)
    with pytest.raises(KeyError):
        world.component(entity, Velocity)


def test_query_matches_all_types_in_ascending_id_order():
    world = World()
    a = world.create_entity(Position(1), Velocity(1))
    world.create_entity(Position(2))
    c = world.create_entity(Velocity(3))
    world.add_component(c, Position(3))

    result = world.query(Position, Velocity)

    assert [entity for entity, _ in result] == [a, c]
    assert [pos.x for _, (pos, _) in result] == [1, 3]


def test_query_order_ignores_insertion_order():
    world = World()
    first = world.create_entity(Tag())
    second = world.create_entity(Tag())
    world.remove_component(first, Tag)
    world.add_component(first, Tag())

    assert [entity for entity, _ in world.query(Tag)] == [first, second]


def test_query_exclude():
    world = World()
    a = world.create_entity(Position(1))
    world.create_entity(Position(2), Tag())
    c = world.create_entity(Position(3))

    result = world.query(Position, exclude=(Tag,))

    assert [entity for entity, _ in result] == [a, c]
    assert world.query(Position, exclude=(Velocity,)) == world.query(Position)


def test_query_unknown_type_is_empty():
    world = World()
    world.create_entity(Position())
    assert world.query(Position, Velocity) == []
    assert world.query(Velocity) == []


def test_remove_component():
    world = World()
    velocity = Velocity(2)
    entity = world.create_entity(Position(), velocity)

    assert world.remove_component(entity, Velocity) is velocity
    assert world.query(Velocity) == []
    assert world.has_components(entity, Position)


def test_delete_entity():
    world = World()
    entity = world.create_entity(Position(), Velocity())
    world.delete_entity(entity)

    assert not world.entity_exists(entity)
    assert world.query(Position) == []
    assert world.create_entity() == entity + 1  # IDs are never reused


def test_delete_while_iterating_query():
    world = World()
    for x in range(3):
        world.create_entity(Position(x))

    for entity, _ in world.query(Position):
        world.delete_entity(entity)

    assert world.query(Position) == []


def test_resources_are_keyed_by_type():
    world = World()
    config = Config(speed=3)
    world.add_resource(config)

    assert world.resource(Config) is config
    world.add_resource(Config(speed=4))
    assert world.resource(Config).speed == 4


def test_systems_run_in_added_order():
    world = World()
    calls = []
    world.add_system(lambda w: calls.append("steer"))
    world.add_system(lambda w: calls.append("move"))
    world.add_system(lambda w: calls.append("sense"))

    world.step()
    world.step()

    assert calls == ["steer", "move", "sense"] * 2


def test_system_mutates_components():
    def movement(world: World) -> None:
        speed = world.resource(Config).speed
        for _, (pos, vel) in world.query(Position, Velocity):
            pos.x += vel.dx * speed

    world = World()
    world.add_resource(Config(speed=2))
    entity = world.create_entity(Position(0), Velocity(3))
    world.add_system(movement)
    world.step()

    assert world.component(entity, Position).x == 6


def test_worlds_are_isolated():
    one, two = World(), World()
    one.create_entity(Position())
    one.add_resource(Config(speed=9))

    assert two.query(Position) == []
    assert two.create_entity() == 1
    with pytest.raises(KeyError):
        two.resource(Config)
