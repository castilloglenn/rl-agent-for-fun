from absl import app, flags
from ml_collections import config_flags

from src.config import get_agent_config, get_maze_car_config
from src.envs.maze_car.demo import MazeCarDemo
from src.main import Main


def run(_):
    cl_args = flags.FLAGS
    if cl_args.tests:
        print("TODO: Run unittests")
    elif cl_args.replay:
        from src.replay.viewer import ReplayViewer

        ReplayViewer.open(cl_args.replay, cl_args.maze_car).run()
    elif game := cl_args.demo:
        match game:
            case "maze_car":
                MazeCarDemo(cl_args.maze_car)
            case _:
                pass
    else:
        Main()


if __name__ == "__main__":
    config_flags.DEFINE_config_dict("agent", get_agent_config())
    config_flags.DEFINE_config_dict("maze_car", get_maze_car_config())

    app.run(run)
