from absl import app, flags
from ml_collections import config_flags

from src.config import get_agent_config, get_maze_car_config
from src.envs.maze_car import MazeCarEnv
from src.main import Main


def run(_):
    cl_args = flags.FLAGS
    if cl_args.tests:
        print("TODO: Run unittests")
    elif game := cl_args.demo:
        match game:
            case "maze_car":
                MazeCarEnv()
            case _:
                pass
    else:
        Main()


if __name__ == "__main__":
    config_flags.DEFINE_config_dict("agent", get_agent_config())
    config_flags.DEFINE_config_dict("maze_car", get_maze_car_config())

    app.run(run)
