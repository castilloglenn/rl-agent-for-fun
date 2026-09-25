from pygame import Vector2

from src.ecs import World
from src.sim.components import Sensors, Transform
from src.sim.geometry import direction, distance_to_bounds
from src.sim.resources import Field, SimConfig

# Name and angle (degrees, counterclockwise from the heading) of each ray,
# going around the car.
RAY_LAYOUT = (
    ("front", 0),
    ("front_left", 45),
    ("left", 90),
    ("back_left", 135),
    ("back", 180),
    ("back_right", -135),
    ("right", -90),
    ("front_right", -45),
)


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
    """Each ray starts at the car's body edge (distance 0 = touching) and
    stops at the field border, or at ray_length.
    """
    for ray in sensors.rays:
        dx, dy = direction(transform.angle + ray.angle)
        start_x = transform.x + dx * ray.offset
        start_y = transform.y + dy * ray.offset
        ray.distance = min(
            distance_to_bounds(start_x, start_y, dx, dy, field.rect),
            ray_length,
        )
        ray.start = Vector2(start_x, start_y)
        ray.end = Vector2(
            start_x + dx * ray.distance, start_y + dy * ray.distance
        )
