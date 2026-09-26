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
        from src.agents.store import AgentError, branch_agent, create_agent

        source = getattr(cl_args, "from")
        try:
            if source:
                parent, _, checkpoint = source.partition("@")
                folder = branch_agent(
                    cl_args.new_agent, parent, checkpoint or None
                )
                made = f"branched from {source}"
            else:
                folder = create_agent(
                    cl_args.new_agent,
                    load_model_spec(cl_args.model),
                    cl_args.seed,
                )
                made = cl_args.model
        except AgentError as error:
            raise SystemExit(str(error))
        print(f"Created agent {cl_args.new_agent!r} ({made})")
        print(f"  {folder}")
        print(f"Watch it: make maze_car_agent AGENT={cl_args.new_agent}")
    elif cl_args.train:
        _train(cl_args, config)
    elif cl_args.resume or cl_args.resume_last:
        _resume(cl_args, config)
    elif cl_args.eval or cl_args.eval_baselines:
        _evaluate(cl_args, config)
    elif cl_args.preview_dataset:
        from src.agents.model import load_model_spec
        from src.experiments.datasets import (
            DatasetError,
            build_dataset,
            format_dataset,
            load_dataset_spec,
        )

        try:
            spec = load_dataset_spec(cl_args.dataset)
        except DatasetError as error:
            raise SystemExit(str(error))
        repeat = load_model_spec("small").action_repeat
        print(format_dataset(build_dataset(spec, repeat)))
    elif cl_args.imitate:
        _imitate(cl_args, config)
    elif cl_args.list_agents:
        from src.experiments.agents import format_agents, list_agents

        print(format_agents(list_agents()))
    elif cl_args.show_agent:
        from src.experiments.agents import AgentError, agent_summary

        try:
            print(agent_summary(cl_args.show_agent))
        except AgentError as error:
            raise SystemExit(str(error))
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


def _train(cl_args, config) -> None:
    import torch

    from src.agents.store import AgentError
    from src.agents.trainer import TrainerError, load_trainer_spec
    from src.experiments.training import train_agent
    from src.sim.rules import load_rules

    torch.set_num_threads(1)  # as fast at this size, and reproducible
    rules = load_rules(config.rules)
    if cl_args.round_seconds > 0:
        rules = rules.with_round_seconds(cl_args.round_seconds)

    try:
        trainer = load_trainer_spec(cl_args.trainer)
        print(
            f"Training {cl_args.train!r} with trainer {trainer.name!r} "
            f"(Ctrl+C stops and keeps the weights)"
        )
        summary = train_agent(
            cl_args.train,
            trainer,
            config,
            first_seed=cl_args.seed,
            reward=cl_args.reward,
            rules=rules,
            on_update=_training_progress,
        )
    except AgentError as error:
        raise SystemExit(
            f"{error}\nCreate it with: make new_agent AGENT={cl_args.train}"
        )
    except TrainerError as error:
        raise SystemExit(str(error))
    _training_done(summary)


def _resume(cl_args, config) -> None:
    import torch

    from src.agents.store import AgentError
    from src.experiments.training import (
        TrainingError,
        last_stopped_run,
        resume_training,
    )

    torch.set_num_threads(1)
    try:
        run = cl_args.resume or last_stopped_run()
        print(f"Resuming {run} (Ctrl+C stops again)")
        summary = resume_training(
            run, base_config=config, on_update=_training_progress
        )
    except (AgentError, TrainingError) as error:
        raise SystemExit(str(error))
    _training_done(summary)


def _evaluate(cl_args, config) -> None:
    import torch

    from src.agents.store import AGENTS_DIR, AgentError
    from src.experiments.evaluation import (
        SuiteError,
        baseline_scores,
        evaluate_agent,
        format_results,
        load_suite,
    )

    torch.set_num_threads(1)
    try:
        suite = load_suite(cl_args.suite)
        print(f"Suite {suite.label}: {suite.description}")
        baselines = baseline_scores(suite, AGENTS_DIR, config)
        rows = []
        if cl_args.eval:
            rows = evaluate_agent(
                cl_args.eval,
                suite,
                base_config=config,
                on_checkpoint=lambda row: print(
                    f"  scored {row['checkpoint']}"
                ),
            )
    except (AgentError, SuiteError) as error:
        raise SystemExit(str(error))
    print(format_results(rows, baselines))


def _imitate(cl_args, config) -> None:
    import torch

    from src.agents.store import AgentError
    from src.agents.trainer import TrainerError, load_imitation_spec
    from src.experiments.datasets import DatasetError, load_dataset_spec
    from src.experiments.imitation import imitate

    torch.set_num_threads(1)

    def progress(report):
        if report.epoch % 5 and report.epoch != report.epochs:
            return
        held = report.held_out_accuracy
        print(
            f"  epoch {report.epoch:>3}/{report.epochs}  accuracy "
            f"{report.train_accuracy:.0%}"
            + ("" if held is None else f", held-out rounds {held:.0%}")
            + f"  {report.seconds:,.1f} s"
        )

    try:
        trainer = load_imitation_spec(cl_args.imitation_trainer)
        dataset = load_dataset_spec(cl_args.dataset)
        print(
            f"Cloning {dataset.player!r} (dataset {dataset.name!r}) into "
            f"{cl_args.imitate!r} with trainer {trainer.name!r}"
        )
        summary = imitate(
            cl_args.imitate, trainer, dataset, config, on_epoch=progress
        )
    except (AgentError, TrainerError, DatasetError) as error:
        raise SystemExit(str(error))
    held = summary.held_out_accuracy
    print(
        f"Done ({summary.rounds} rounds, {summary.samples:,} samples, "
        f"{summary.seconds:,.1f} s): accuracy {summary.train_accuracy:.0%}"
        + ("" if held is None else f", held-out rounds {held:.0%}")
    )
    if summary.evaluation:
        e = summary.evaluation
        print(
            f"The clone on the suite: score {e['score_mean']:,.0f}, "
            f"survival {e['survival']:.0%}, wrecks {e['wreck_rate']:.0%}, "
            f"braking {e['braking']:.0%}. Your recordings' mean score: "
            f"{summary.player_mean_score:,.0f} (other seeds)"
        )
    print(f"Saved as {summary.agent}@{summary.checkpoint} ({summary.folder})")
    print(
        f"Watch it: make maze_car_driver "
        f"DRIVER=agent:{summary.agent}@{summary.checkpoint}"
    )
    print(f"Improve it with RL: make train AGENT={summary.agent}")


def _training_progress(report) -> None:
    if report.update % 10 and not report.saved:
        if report.decisions < report.total:
            return
    score = "" if report.score_mean is None else f"{report.score_mean:,.0f}"
    line = (
        f"  {report.decisions:>9,}/{report.total:,} decisions  "
        f"{report.episodes:>4} episodes  score {score:>6}  "
        f"entropy {report.stats.entropy:.2f}  {report.seconds:,.0f} s"
    )
    print(line + (f"  saved {report.saved}" if report.saved else ""))
    if report.evaluation:
        r = report.evaluation
        print(
            f"      scored {report.saved}: score {r['score_mean']:,.0f}, "
            f"survival {r['survival']:.0%}, wrecks {r['wreck_rate']:.0%}, "
            f"braking {r['braking']:.0%}"
        )


def _training_done(summary) -> None:
    state = "interrupted, " if summary.interrupted else ""
    print(
        f"Done ({state}{summary.decisions:,} decisions, "
        f"{summary.episodes} episodes, {summary.seconds:,.0f} s): "
        f"last {min(summary.episodes, 100)} episodes mean score "
        f"{summary.mean_score:,.0f}, survived {summary.survival_rate:.0%}"
    )
    print(f"Checkpoints: {', '.join(summary.checkpoints) or 'none'}")
    print(f"Saved in {summary.folder}")
    if summary.interrupted:
        print("Resume it exactly: make resume_last")
    print(f"Watch it: make maze_car_agent AGENT={summary.agent}")


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
