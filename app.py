from absl import app, flags
from ml_collections import config_flags

from src.config import get_agent_config, get_maze_car_config
from src.main import Main


def run(_):
    from src.drivers.registry import DriverError

    try:
        _dispatch(flags.FLAGS)
    except DriverError as error:
        raise SystemExit(str(error))


def _dispatch(cl_args) -> None:
    config = cl_args.maze_car
    if cl_args.stage:
        config.stage = cl_args.stage
    if cl_args.rules:
        config.rules = cl_args.rules

    if cl_args.tests:
        print("TODO: Run unittests")
    elif cl_args.new_agent:
        from src.agents.model import load_model_spec
        from src.agents.store import AgentError, create_agent

        try:
            folder = create_agent(
                cl_args.new_agent, load_model_spec(cl_args.model), cl_args.seed
            )
        except AgentError as error:
            raise SystemExit(str(error))
        print(f"Created agent {cl_args.new_agent!r} ({cl_args.model})")
        print(f"  {folder}")
        print(f"Watch it: make maze_car_agent AGENT={cl_args.new_agent}")
    elif cl_args.list_recordings:
        from src.replay.recordings import format_recordings, list_recordings

        print(format_recordings(list_recordings()))
    elif cl_args.replay_last:
        from src.replay.recordings import latest_recording
        from src.replay.viewer import ReplayViewer

        try:
            path = latest_recording()
        except FileNotFoundError as error:
            raise SystemExit(str(error))
        print(f"Playing {path}")
        ReplayViewer.open(path, config).run()
    elif cl_args.list_runs:
        from src.experiments.runs import format_runs, list_runs

        print(format_runs(list_runs()))
    elif cl_args.best_replay:
        from src.experiments.runs import best_replay
        from src.replay.viewer import ReplayViewer

        path = best_replay(cl_args.best_replay)
        print(f"Playing {path}")
        ReplayViewer.open(path, config).run()
    elif cl_args.replay:
        from src.replay.viewer import ReplayViewer

        ReplayViewer.open(cl_args.replay, config).run()
    elif cl_args.run:
        _experiment_run(cl_args, config)
    elif game := cl_args.demo:
        match game:
            case "maze_car":
                from src.envs.maze_car.demo import MazeCarDemo

                MazeCarDemo(
                    config,
                    driver=cl_args.driver,
                    player=cl_args.player,
                    reward=cl_args.reward,
                    round_seconds=cl_args.round_seconds,
                    record=cl_args.record,
                )
            case _:
                pass
    else:
        Main()


def _experiment_run(cl_args, config) -> None:
    from src.drivers.registry import make_driver
    from src.experiments.runner import run_experiment
    from src.sim.rules import load_rules

    if cl_args.driver == "keyboard":
        raise SystemExit(
            "A run is headless: pick --driver random, heuristic, or agent:<id>."
        )
    rules = load_rules(config.rules)
    if cl_args.round_seconds > 0:
        rules = rules.with_round_seconds(cl_args.round_seconds)

    def progress(episode, result):
        if (episode + 1) % 10 == 0 or episode + 1 == cl_args.episodes:
            print(
                f"  episode {episode + 1}/{cl_args.episodes}  "
                f"score {result.score:,.0f}  ended by {result.ended_by}"
            )

    print(f"Run {cl_args.run!r}: {cl_args.driver}, {cl_args.episodes} episodes")
    summary = run_experiment(
        cl_args.run,
        make_driver(cl_args.driver),
        config,
        episodes=cl_args.episodes,
        first_seed=cl_args.seed,
        reward=cl_args.reward,
        rules=rules,
        on_episode=progress,
    )
    state = "interrupted, " if summary.interrupted else ""
    print(
        f"Done ({state}{summary.episodes} episodes, {summary.seconds:.1f} s): "
        f"mean score {summary.mean_score:,.0f}, best {summary.best_score:,.0f} "
        f"(episode {summary.best_episode}), "
        f"checkpoints {summary.mean_checkpoints:.1f}/round, "
        f"survived {summary.survival_rate:.0%}"
    )
    print(f"Saved in {summary.folder}")


if __name__ == "__main__":
    config_flags.DEFINE_config_dict("agent", get_agent_config())
    config_flags.DEFINE_config_dict("maze_car", get_maze_car_config())

    app.run(run)
