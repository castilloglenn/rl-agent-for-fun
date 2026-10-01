from pygame import Vector2

from src.ecs import World
from src.sim.components import Sensors, Transform
from src.sim.geometry import direction, distance_to_bounds
from src.sim.resources import Field, SimConfig, Walls
from src.sim.walls import ray_to_walls

# Name and angle (degrees, counterclockwise from the heading) of each ray,
# going around the car. Denser in front (7f3, decision 059): a ray every
# 15 degrees across the front 90, so a 48 px gap or a 30 px pillar shows
# from 184 and 115 px away (45 degrees apart: from 63 and 39 px, closer
# than the car needs to brake from full speed). Sides and back stay 45.
RAY_LAYOUT = (
    ("front", 0),
    ("front_left_15", 15),
    ("front_left_30", 30),
    ("front_left", 45),
    ("left", 90),
    ("back_left", 135),
    ("back", 180),
    ("back_right", -135),
    ("right", -90),
    ("front_right", -45),
    ("front_right_30", -30),
    ("front_right_15", -15),
)


def sensor_system(world: World) -> None:
    field = world.resource(Field)
    walls = world.resource(Walls).boxes
    ray_length = world.resource(SimConfig).ray_length
    for _, (transform, sensors) in world.query(Transform, Sensors):
        cast_rays(sensors, transform, field, ray_length, walls)


def cast_rays(
    sensors: Sensors,
    transform: Transform,
    field: Field,
    ray_length: int,
    walls: tuple = (),
) -> None:
    """Each ray starts at the car's body edge (distance 0 = touching) and
    stops at the field border, a wall, or at ray_length.
    """
    for ray in sensors.rays:
        dx, dy = direction(transform.angle + ray.angle)
        start_x = transform.x + dx * ray.offset
        start_y = transform.y + dy * ray.offset
        ray.distance = min(
            distance_to_bounds(start_x, start_y, dx, dy, field.rect),
            ray_to_walls(start_x, start_y, dx, dy, walls),
            ray_length,
        )
        ray.start = Vector2(start_x, start_y)
        ray.end = Vector2(
            start_x + dx * ray.distance, start_y + dy * ray.distance
        )
