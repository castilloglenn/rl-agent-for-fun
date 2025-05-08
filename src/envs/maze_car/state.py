from dataclasses import dataclass
from dataclasses import field as field_
from dataclasses import fields

from src.envs.maze_car.models.action_state import ActionState
from src.envs.maze_car.models.car_state import CarState
from src.envs.maze_car.models.collision_distance_state import CollisionDistanceState
from src.envs.maze_car.models.display_state import DisplayState
from src.envs.maze_car.models.field_state import FieldState


@dataclass
class State:
    display: DisplayState = field_(default_factory=DisplayState)
    action: ActionState = field_(default_factory=ActionState)
    field: FieldState = field_(default_factory=FieldState)
    car: CarState = field_(default_factory=CarState)
    collision_distances: dict[str, CollisionDistanceState] = field_(
        default_factory=dict,
    )

    def __setattr__(self, name, value):
        if name not in {field.name for field in fields(self)}:
            cname = self.__class__.__name__
            error = f"{cname} does not allow adding new attributes."
            raise AttributeError(error)
        super().__setattr__(name, value)


class StateSingleton:
    _instance = None

    @classmethod
    def get_instance(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = State(*args, **kwargs)
        return cls._instance
