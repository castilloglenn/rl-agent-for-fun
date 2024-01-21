from dataclasses import dataclass, field, fields

from envs.maze_car.models.action_state import ActionState
from envs.maze_car.models.field_state import GameFieldState


@dataclass
class State:
    action: ActionState = field(default_factory=ActionState)
    game_field: GameFieldState = field(default_factory=GameFieldState)

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
