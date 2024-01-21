from dataclasses import dataclass


@dataclass
class ActionState:
    turn_left: bool = False
    turn_right: bool = False
    move_forward: bool = False
    move_backward: bool = False

    @staticmethod
    def from_tuple(data: tuple) -> "ActionState":
        return ActionState(*data)

    @property
    def is_moving(self):
        return self.move_forward or self.move_backward

    def to_tuple(self) -> tuple:
        return tuple(self.__dict__.values())
