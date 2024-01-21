from typing import TypedDict

from envs.maze_car.models.action import ActionState


class State(TypedDict):
    action: ActionState


state: State = {}
