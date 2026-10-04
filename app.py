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
    if not config.window.settings_file:  # your settings (7c5), display only
        from src.utils.settings import SETTINGS_PATH

        config.window.settings_file = str(SETTINGS_PATH)

    # Every command's arguments are checked first (7h): a plain message,
    # not a crash halfway in. -check stops there.
    from src.app_checks import problems

    found = problems(cl_args, config)
    if found:
        raise SystemExit("\n".join(found))
    if cl_args.check:
        print("check: ok", flush=True)
        return

    if _heavy(cl_args):
        _share_the_machine()
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
    elif cl_args.stop_all:
        from src.control.guard import stop_every_job

        stopped = stop_every_job()
        for job in stopped:
            print(f"  stopped {job.pid}: {' '.join(job.argv[1:])}")
        print(f"Stopped {len(stopped)} job{'s' if len(stopped) != 1 else ''}")
    elif cl_args.control:
        from src.config import get_control_config
        from src.control.jobs import JobLimits
        from src.control.vitals import LOGS_DIR
        from src.control.window import ControlCenter

        limits = JobLimits(**get_control_config().jobs)
        ControlCenter(
            logs_dir=LOGS_DIR,
            limits=limits,
            settings_file=config.window.settings_file,
        ).run()
    elif cl_args.edit_map:
        from src.editor.model import NAME
        from src.editor.window import run_editor

        if not NAME.match(cl_args.edit_map):
            raise SystemExit("a stage name uses letters, digits, - and _")
        run_editor(cl_args.edit_map)
    elif cl_args.vitals:
        from src.control.vitals import tail

        print(tail())
    elif cl_args.delete_run or cl_args.delete_agent or cl_args.restore:
        from src.control.trash import Trash, TrashError

        try:
            if cl_args.delete_run or cl_args.delete_agent:
                if cl_args.delete_run:
                    entry = Trash().delete_run(cl_args.delete_run)
                else:
                    entry = Trash().delete_agent(cl_args.delete_agent)
                print(f"Moved {', '.join(entry.paths)} into the trash:")
                print(f"  trash/{entry.name}")
                print(f"Restore it: make restore TRASH={entry.name}")
            else:
                entry = Trash().restore(cl_args.restore)
                print(f"Restored {', '.join(entry.paths)}")
        except TrashError as error:
            raise SystemExit(str(error))
    elif cl_args.keep or cl_args.unkeep:
        from src.replay.recordings import (
            RecordingError,
            keep_file,
            unkeep_file,
        )

        try:
            if cl_args.keep:
                path = keep_file(cl_args.keep)
                print(f"Kept: {path} (the latest-50 limit never removes it)")
            else:
                path = unkeep_file(cl_args.unkeep)
                print(
                    f"Moved back with the recent ones: {path} (the latest-50 "
                    "limit applies at your next saved round)"
                )
        except RecordingError as error:
            raise SystemExit(str(error))
    elif cl_args.delete_recording:
        from src.control.trash import Trash, TrashError

        try:
            entry = Trash().delete_recording(cl_args.delete_recording)
        except TrashError as error:
            raise SystemExit(str(error))
        print(f"Moved {entry.paths[0]} into the trash: trash/{entry.name}")
        print(f"Restore it: make restore TRASH={entry.name}")
    elif cl_args.list_trash:
        from src.control.trash import Trash, format_entries

        print(format_entries(Trash().entries()))
    elif cl_args.empty_trash:
        from src.control.trash import Trash

        gone = Trash().empty()
        noun = "entry" if len(gone) == 1 else "entries"
        print(f"Deleted {len(gone)} trash {noun} for good.")
    elif cl_args.showcase:
        from src.experiments.showcase import Showcase

        # The window opens at once, and gets ready in it (7c8): scoring
        # what isn't scored yet shows each step there.
        Showcase.prepare(
            cl_args.showcase,
            config,
            everything=cl_args.showcase_all,
            skill=cl_args.showcase_skill,
        ).run()
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
        from src.experiments.runs import best_replay, best_replays
        from src.replay.viewer import ReplayViewer

        path = best_replay(cl_args.best_replay)
        print(f"Playing {path}")
        viewer = ReplayViewer.open(path, config)
        viewer.offer_bests(best_replays(cl_args.best_replay))  # a mix: M
        viewer.run()
    elif cl_args.replay:
        from src.replay.viewer import ReplayViewer

        ReplayViewer.open(cl_args.replay, config).run()
    elif cl_args.run:
        _experiment_run(cl_args, config)
    elif cl_args.record_rounds:
        _record_rounds(cl_args, config)
    elif game := cl_args.demo:
        match game:
            case "maze_car":
                from src.envs.maze_car.demo import MazeCarDemo

                MazeCarDemo(
                    config,
                    driver=_correcting(cl_args),
                    player=cl_args.player,
                    reward=cl_args.reward,
                    round_seconds=cl_args.round_seconds,
                    record=cl_args.record,
                    corrections=cl_args.corrections,
                )
            case _:
                pass
    else:
        Main()


def _correcting(cl_args) -> str:
    """The driver. Correcting an agent (7g) watches its newest checkpoint,
    the one the next training continues, not its best.
    """
    driver = cl_args.driver
    if not cl_args.corrections or "@" in driver:
        return driver
    from src.agents.store import AgentError, load_agent

    agent = driver.removeprefix("agent:")
    try:
        newest = load_agent(agent).checkpoint
    except AgentError as error:
        raise SystemExit(str(error))
    print(f"Correcting {agent}@{newest} (its newest checkpoint)", flush=True)
    return f"agent:{agent}@{newest}"


def _heavy(cl_args) -> bool:
    """Commands that keep the CPU busy for minutes."""
    from src.utils.resources import HEAVY

    return any(getattr(cl_args, name) for name in HEAVY)


def _share_the_machine() -> None:
    from src.utils.resources import FREE_CORES, share_the_machine

    niceness, threads = share_the_machine()
    print(
        f"Low priority (nice {niceness}), torch threads {threads}: "
        f"at least {FREE_CORES} cores stay free for your system",
        flush=True,
    )
    _guard()


def _guard() -> None:
    """The job's own safety gate (decision 038): it doesn't start past
    the heavy jobs' limit or on a red reading, and then stops itself when
    the machine or its parent calls for it.
    """
    import sys

    from src.config import get_control_config
    from src.control import guard

    jobs = get_control_config().jobs
    limits = guard.GuardLimits(
        jobs.max_heavy, jobs.memory_trip_gb, jobs.memory_trip_seconds
    )
    why = guard.start_problem(sys.argv, limits)
    if why:
        raise SystemExit(f"Not started: {why}")
    expected = guard.estimate_gb(sys.argv)
    guard.JobGuard(limits, expected_gb=expected).start()
    print(
        f"Guard: on (about {expected:.1f} GB expected, up to "
        f"{guard.job_limit_gb(expected):.1f} GB; at most "
        f"{limits.heavy_cap} heavy jobs; memory, disk, battery, parent)",
        flush=True,
    )


def _train(cl_args, config) -> None:
    import torch

    from src.agents.store import AgentError
    from src.agents.trainer import TrainerError, load_trainer_spec
    from src.experiments.training import train_agent
    from src.sim.rules import load_rules

    torch.set_num_threads(1)  # as fast at this size, and reproducible
    from src.utils.test_maps import warning

    test_map = warning(config.stage)
    if test_map:
        print(f"Warning: {test_map}.", flush=True)
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
            on_start=_announce_run,
            games=cl_args.games,
            adapt=True,
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
            run,
            base_config=config,
            on_update=_training_progress,
            on_start=_announce_run,
            adapt=True,
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
            cl_args.imitate,
            trainer,
            dataset,
            config,
            on_epoch=progress,
            on_start=_announce_run,
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
    print(
        "Improve it with reinforcement learning: "
        f"make train AGENT={summary.agent}"
    )


def _announce_run(folder) -> None:
    """The run's folder, as soon as it exists: the control center links
    the job to its run by this line (step 6b1).
    """
    print(f"Run: {folder.name}", flush=True)


def _training_progress(report) -> None:
    if report.update % 10 and not report.saved:
        if report.decisions < report.total:
            return
    score = "" if report.score_mean is None else f"{report.score_mean:,.0f}"
    line = (
        f"  {report.decisions:>9,}/{report.total:,} decisions  "
        f"{report.episodes:>4} episodes  score {score:>6}  "
        f"entropy {report.stats.entropy:.2f}  {report.seconds:,.0f} s"
        + (f"  {report.games} games" if report.games > 1 else "")
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


def _record_rounds(cl_args, config) -> None:
    from src.drivers.registry import DriverError
    from src.experiments.driver_rounds import (
        RecordError,
        player_of,
        record_rounds,
    )
    from src.sim.rules import load_rules
    from src.utils.test_maps import warning

    test_map = warning(config.stage)
    if test_map:  # a dataset from a test map teaches the test
        print(f"Warning: {test_map}.", flush=True)
    rules = load_rules(config.rules)
    if cl_args.round_seconds > 0:
        rules = rules.with_round_seconds(cl_args.round_seconds)
    driver, rounds = cl_args.record_rounds, cl_args.rounds
    print(
        f"Recording {rounds} rounds of {driver} on {config.stage} into "
        f"recordings/{player_of(driver)}/",
        flush=True,
    )

    def progress(i, stage, result):
        if (i + 1) % 10 == 0 or i + 1 == rounds:
            print(
                f"  round {i + 1}/{rounds} on {stage}  "
                f"score {result.score:,.0f}  ended by {result.ended_by}",
                flush=True,
            )

    try:
        saved = record_rounds(
            driver,
            config,
            rounds,
            first_seed=cl_args.seed,
            rules=rules,
            on_round=progress,
        )
    except (DriverError, RecordError) as error:
        raise SystemExit(str(error))
    print(f"Saved {len(saved)} rounds.")


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
        on_start=_announce_run,
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
