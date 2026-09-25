from pygame import Vector2

from src.ecs import World
from src.sim.components import Sensors, Transform
from src.sim.resources import Field, SimConfig
from src.utils.common import get_extended_point


def sensor_system(world: World) -> None:
    field = world.resource(Field)
    ray_length = world.resource(SimConfig).ray_length
    for _, (transform, sensors) in world.query(Transform, Sensors):
        cast_rays(sensors, transform, field, ray_length)


def cast_rays(
    sensors: Sensors,
    transform: Transform,
    field: Field,
    ray_length: int,
) -> None:
    center = Vector2(transform.x, transform.y)
    for ray in sensors.rays:
        heading = (transform.angle + ray.angle) % 360
        ray.start = get_extended_point(
            start_point=center,
            angle=heading,
            distance=ray.offset,
        )
        far_point = get_extended_point(
            start_point=ray.start,
            angle=heading,
            distance=ray_length,
        )
        hit = field.rect.clipline(ray.start, far_point)
        ray.end = Vector2(hit[1] if hit else ray.start)
        ray.distance = ray.start.distance_to(ray.end)
