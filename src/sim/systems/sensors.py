from pygame import Rect, Vector2

from src.ecs import World
from src.sim.components import Hitbox, Sensors, Transform
from src.sim.resources import Field, SimConfig
from src.utils.common import get_extended_point


def sensor_system(world: World) -> None:
    field = world.resource(Field)
    ray_length = world.resource(SimConfig).ray_length
    for _, (transform, hitbox, sensors) in world.query(
        Transform, Hitbox, Sensors
    ):
        cast_rays(sensors, hitbox.rect, transform.angle, field, ray_length)


def cast_rays(
    sensors: Sensors,
    rect: Rect,
    angle: float,
    field: Field,
    ray_length: int,
) -> None:
    for ray in sensors.rays:
        heading = (angle + ray.angle) % 360
        ray.start = get_extended_point(
            start_point=Vector2(rect.center),
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
