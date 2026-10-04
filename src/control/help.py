"""The control center's help texts (decision 030): what each field,
chart, skill, column, badge, and vital sign means, and each file field's
unit. One place for the words, so the tabs only point at them.

File fields are keyed by their path in the file ("collisions.safe_speed",
"scenarios.*.episodes": * stands for any scenario). A test checks that
every key here matches a field that exists.
"""

import re

# The simulation's pace, for texts that turn steps into time.
STEPS_PER_SECOND = 120

# Files: folder -> path -> (unit, text).
FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "rules": {
        "name": ("", "The file's name. Duplicate as… makes a copy under a "
                 "new one."),
        "description": ("", "What these rules are for, in plain words. "
                        "Shown in lists and run headers."),
        "round_seconds": ("s", "How long a round lasts. When the timer "
                          "hits 0, the round ends on time."),
        "rounds": ("rounds", "Rounds per game. Only 1 is played so far "
                   "(multiple rounds come later)."),
        "scoring.distance_step": ("px per point", "Driving forward this far "
                                  "earns +1 game point."),
        "scoring.checkpoint": ("points", "Game points for reaching a "
                               "checkpoint."),
        "collisions.health": ("health", "A car's full health. At 0 it's "
                              "wrecked and the round ends for it."),
        "collisions.safe_speed": ("px/s", "Hits at or below this speed into "
                                  "the wall do no damage. 0 with lethal "
                                  "speed 0: any hit wrecks."),
        "collisions.lethal_speed": ("px/s", "Hits at or above this speed "
                                    "into the wall wreck the car. Between "
                                    "safe and lethal, damage rises "
                                    "linearly."),
        "collisions.scrape_damage": ("health per px", "Health lost for each "
                                     "px the car slides along a wall."),
    },
    "trainers": {
        "name": ("", "The file's name."),
        "description": ("", "What this trainer is for, in plain words."),
        "algorithm": ("", "How it learns: ppo (reinforcement learning) or "
                      "imitation (cloning a player's recordings). Fixed: "
                      "the other fields depend on it."),
        "learning_rate": ("", "How big each step of learning is. Too high "
                          "and learning becomes unstable, too low and it's "
                          "slow. 0.0003 is a common start."),
        "gamma": ("0 to 1", "How much future reward counts. 0.99 looks "
                  "about 100 decisions ahead (a few seconds of driving)."),
        "gae_lambda": ("0 to 1", "How far the estimate of an action's worth "
                       "looks ahead before trusting the value guess. 0.95 "
                       "is common."),
        "clip": ("", "PPO's safety limit: one update can change an "
                 "action's chance by at most this share (0.2 = 20 %)."),
        "entropy": ("", "A bonus for staying random, so it keeps exploring. "
                    "Higher explores more, and settles slower."),
        "value_coef": ("", "How much the value guess (future reward) counts "
                       "in the loss, next to choosing actions."),
        "max_grad_norm": ("", "Caps the size of one learning step, so a "
                          "surprising batch can't wreck the network."),
        "reward_scale": ("×", "Rewards are multiplied by this before "
                         "learning (0.01 turns -500 into -5). It keeps "
                         "numbers in a range networks learn well."),
        "rollout": ("decisions", "Decisions collected before each update."),
        "minibatch": ("decisions", "Decisions per learning step within an "
                      "update. At most the rollout."),
        "epochs": ("passes", "Passes over each rollout per update "
                   "(imitation: passes over all the recordings)."),
        "total_decisions": ("decisions", "How long one training phase runs. "
                            "2,000,000 is about 9 min here, with scoring."),
        "checkpoint_every": ("decisions", "Weights are saved (and scored, "
                             "if evaluate is on) this often."),
        "seed": ("", "Seeds the random parts of learning, so a run can be "
                 "repeated exactly."),
        "evaluate": ("", "Score each checkpoint on the evaluation suite as "
                     "it's saved (the dots on the Runs tab's score chart)."),
        "validation": ("share", "Imitation: the share of whole rounds held "
                       "out to check the clone on rounds it never saw."),
        "value": ("", "Imitation: also learn the value guess from the "
                  "rounds' rewards, so a later reinforcement learning "
                  "phase starts smoothly."),
    },
    "models": {
        "name": ("", "The file's name. Agents keep their own copy, so "
                 "editing this never changes an existing agent."),
        "description": ("", "What this model is for, in plain words."),
        "hidden": ("neurons per layer", "The network's hidden layers, one "
                   "number each: 64, 64 is two layers of 64."),
        "activation": ("", "The function between layers: tanh (smooth, "
                       "bounded) or relu."),
        "observation_version": ("", "Which inputs the network reads "
                                "(sensor rays, speed, heading, health, the "
                                "checkpoint's direction). Fixed by the "
                                "code."),
        "actions": ("", "The action set: canonical12 is 12 combinations of "
                    "gas, brake, reverse, and steering. Fixed by the "
                    "code."),
        "action_repeat": ("steps per decision", "The agent decides every "
                          f"this many steps ({STEPS_PER_SECOND} steps/s: 4 "
                          "is 30 decisions/s), holding its action "
                          "between."),
    },
    "datasets": {
        "name": ("", "The file's name."),
        "description": ("", "What this dataset is for, in plain words."),
        "player": ("", "Whose recordings: the folder name under "
                   "recordings/ (You, by default)."),
        "include": ("", "all: recent and kept recordings. kept: only the "
                    "ones you kept (K after a round)."),
        "min_score": ("points", "Rounds that scored below this are left "
                      "out, so the clone learns from good driving."),
        "also": ("", "More players' recordings in the same dataset, for "
                 "example the heuristic's with your corrections."),
        "correction_weight": ("times", "How many times a corrected moment "
                              "counts: a few would be lost among the "
                              "heuristic's thousands."),
    },
    "curricula": {
        "name": ("", "The file's name. Pick it as the Stage (\"curriculum: "
                 "...\") to train up its levels by itself."),
        "description": ("", "What this curriculum teaches, in plain words."),
        "earlier_share": ("share", "The share of episodes on maps only "
                          "earlier levels had, 0 to under 1: practice "
                          "against forgetting."),
        "window": ("episodes", "How many recent episodes on each map make "
                   "its smoothed rate."),
        "levels.*.mix": ("", "The level's maps: a mix, or one stage."),
        "levels.*.goal": ("share", "On every map of the level, its "
                          "checkpoints a minute over the heuristic's there "
                          "(1.0: as good). Reached and leveled off: up."),
        "levels.*.min_decisions": ("decisions", "The least it stays in the "
                                   "level, so luck doesn't move it up."),
        "levels.*.max_decisions": ("decisions", "The most it stays: then up "
                                   "anyway. Leave it out on the last level."),
    },
    "mixes": {
        "name": ("", "The file's name. Pick it as the Stage to train on all "
                 "its maps."),
        "description": ("", "What this mix practices, in plain words."),
        "stages": ("", "The maps, played in turn: episode 1 on the first, "
                   "episode 2 on the second, and so on, then from the "
                   "start again. Names of stages, separated by commas."),
    },
    "suites": {
        "name": ("", "The file's name."),
        "description": ("", "What this suite measures, in plain words."),
        "version": ("", "Goes up by one on each saved change, so scores of "
                    "different versions never mix."),
        "scenarios.*.name": ("", "The skill's name, in results "
                             "(skill:<name>): one per scenario."),
        "scenarios.*.label": ("", "The skill as shown: \"Open field\"."),
        "scenarios.*.group": ("", "The skill's group: Handling, Hunting, "
                              "or Walls."),
        "scenarios.*.kind": ("", "round: rounds scored by their mean game "
                             "score. braking: starts at speed, aimed at a "
                             "wall, scored by the share of clean stops."),
        "scenarios.*.floor": ("", "The least the heuristic's value counts "
                              "as, for this skill's share (default: 100 "
                              "points for a round, 0.1 for braking), so a "
                              "skill the heuristic can't do can't divide by "
                              "about 0."),
        "scenarios.*.stage": ("", "The stage it's played on."),
        "scenarios.*.rules": ("", "The rules it's played with."),
        "scenarios.*.first_seed": ("", "Round i uses seed first_seed + i: "
                                   "every agent gets the same rounds, so "
                                   "scores compare fairly."),
        "scenarios.*.episodes": ("rounds", "How many rounds are played. "
                                 "More is fairer, and slower to score."),
        "scenarios.*.round_seconds": ("s", "The round length for this "
                                      "scenario, instead of the rules' "
                                      "own."),
        "scenarios.*.start.speed": ("px/s", "Braking: the car's speed at "
                                    "the start."),
        "scenarios.*.start.min_distance": ("px", "Braking: the closest the "
                                           "wall starts. Pure braking from "
                                           "300 px/s takes about 75 px."),
        "scenarios.*.start.max_distance": ("px", "Braking: the farthest "
                                           "the wall starts."),
        "scenarios.*.start.max_angle": ("°", "Braking: how far off "
                                        "straight at the wall the car can "
                                        "point."),
    },
    "rewards": {
        "name": ("", "The file's name."),
        "description": ("", "What this profile rewards, in plain words."),
    },
}

# Reward terms: each is measured every step and multiplied by its
# weight. (unit of one, text).
TERMS: dict[str, tuple[str, str]] = {
    "points": ("per game point", "Game points gained: distance and "
               "checkpoints, as the rules score them."),
    "distance_points": ("per game point", "Game points from driving only "
                        "(no checkpoints)."),
    "checkpoints": ("per checkpoint", "Checkpoints reached."),
    "checkpoint_speed": ("per quick checkpoint", "1 for a checkpoint "
                         "reached at once, down to 0 when it took window "
                         "seconds."),
    "damage": ("per full health", "Health lost, as a share of full health: "
               "a 25 % hit is 0.25."),
    "wrecked": ("per wreck", "1 on the step health reaches 0."),
    "contact": ("per contact", "New wall contacts: each hit or scrape "
                "counts once, however long it lasts, and a new one only "
                "after the car was clear of walls for `clear` seconds."),
    "stopped": ("per step stopped", f"1 for each step at speed 0 (idle or "
                f"pinned): {STEPS_PER_SECOND} steps/s."),
    "stuck": ("per step stuck", "0 until the car has gone `grace` seconds "
              "without getting closer along the route than its best, then "
              "rising to 1 at `full` seconds: circling or pushing into a "
              "wall costs more the longer it lasts."),
    "time_up": ("per round", "1 on the step the round ends on time."),
    "per_step": ("per step", f"1 every step ({STEPS_PER_SECOND}/s): a "
                 "negative weight is a time cost."),
    "distance": ("per px", "Px moved forward (0 when stopped or "
                 "reversing)."),
    "progress": ("per px closer", "Px closer to the checkpoint along a "
                 "drivable path around the walls (negative when farther). "
                 "It can't be farmed: circling or rocking nets 0 or less."),
    "speed": ("per max speed", "Speed as a share of max speed, negative "
              "while reversing."),
    "steering_change": ("per full turn", "How far the steering wheel "
                        "moved this step (0 to 2)."),
    "closest_wall": ("per 980 px", "The shortest sensor ray, as a share "
                     "of 980 px (the box's diagonal, on every map): bigger "
                     "is farther from walls."),
}
TERM_PARAMS: dict[str, tuple[str, str]] = {
    "progress.reverse": ("share", "What a gain while reversing counts, 0 "
                         "to 1 (0: nothing, 0.5: half); a loss always counts "
                         "in full."),
    "checkpoint_speed.window": ("s", "After this long, a checkpoint is "
                                "worth 0 of this term."),
    "contact.clear": ("s", "How long the car must be clear of walls before "
                      "a touch counts as a new contact: wiggling against a "
                      "wall counts once."),
    "stuck.grace": ("s", "How long without progress costs nothing: time to "
                    "back out or turn around."),
    "stuck.full": ("s", "When the cost reaches its full weight per step "
                   "(rising from the grace)."),
}

# Everything else, by topic.
TOPICS: dict[str, str] = {
    # Runs tab charts
    "chart:score": "Game points per round. The line is the training score "
    "(mean of the last 20 episodes, on its own map). Dots are each "
    "checkpoint's mean score on the skills' maps (fixed rounds, a fair "
    "comparison): click one to watch it or branch from it. The ring is the "
    "best checkpoint by share, and the dashed line is the heuristic's score.",
    "chart:Skills": "Each skill's share of the heuristic's score, per scored "
    "checkpoint (1.0: as good as the heuristic). The dashed skill is the "
    "one on the map it trains on. Dots are the average share (the "
    "ranking), the ring is the best checkpoint.",
    "chart:accuracy": "How often the clone picks the action you picked: on "
    "the rounds it learned from, and on held-out rounds it never saw. A gap "
    "between them means it memorizes more than it learns.",
    "chart:episodes": "Game points of each episode, and the mean of the "
    "last 20.",
    "chart:Reward by term": "What the agent reward is made of: each term's "
    "sum per episode (mean of the last 20), gains above 0 and costs below. "
    "A shrinking contact cost means it learns to avoid walls; a cost that "
    "grows while the total rises can be a loophole. Rest on a term for "
    "what it counts.",
    "chart:Agent reward": "The agent's reward per episode (mean of the last "
    "20): what it actually optimizes, from its reward profile. It should "
    "rise and level off.",
    "chart:Driving style": "How each scored checkpoint drives, over the "
    "suite's rounds: the share of steps on each pedal (forward, brake, "
    "coast, reverse). A good mix is mostly forward, with some braking, "
    "coasting, and reversing (7c9).",
    "chart:Entropy": "How random its choices are. Fully random is about "
    "2.48 (12 actions). It should fall slowly; a fast drop to near 0 means "
    "it stopped exploring early.",
    "chart:Policy loss": "PPO's objective for choosing actions. Noisy by "
    "design: watch it for sudden blow-ups, not for a trend.",
    "chart:Value loss": "How wrong its guess of future reward is. High early, "
    "then lower; spikes when it finds new behavior.",
    "chart:KL divergence": "How much the policy changed in one update "
    "(Kullback-Leibler divergence). Small and steady is healthy, about 0.005 "
    "to 0.03; spikes mean an update was too big.",
    "chart:Clip fraction": "The share of samples where PPO's safety limit "
    "(clip) kicked in. About 0.1 to 0.3 is normal; always high means updates "
    "keep hitting the cap.",
    "chart:Loss": "How far the clone's choices are from yours: lower is "
    "closer. Held-out rising while train falls means overfitting.",
    "chart:Checkpoints": "Checkpoints reached in each episode.",
    "chart:Distance points": "Game points from driving only, per episode.",
    "chart:Steps": f"How long each episode lasted, in steps "
    f"({STEPS_PER_SECOND}/s).",
    "legend:suite": "The checkpoint's mean game score on the skills' maps. "
    "Click a dot to watch it drive, or branch from it.",
    "legend:average": "The checkpoint's average share of the heuristic's "
    "score across the skills: the ranking.",
    "legend:best": "The checkpoint with the best average share, used by "
    "'Watch best'.",
    "legend:heuristic": "The heuristic: its game score on the score chart, "
    "1.0 (its own share) on Skills. Above the line is better than it.",
    "compare": "Draws another run of the same kind on both charts, muted.",
    # Run statuses
    "status:starting": "Started, but its run isn't written yet (an "
    "imitation builds its dataset first, a plan creates the agent first). "
    "It turns into the run when it is.",
    "status:running": "Running as a job of this control center.",
    "status:paused": "Frozen in place (Pause): it continues exactly where "
    "it was on Resume.",
    "status:running elsewhere": "Running outside this control center, for "
    "example make train in a terminal.",
    "status:stopped": "Stopped with Ctrl+C or Stop. A training run can "
    "resume exactly (Resume training).",
    "status:done": "Finished.",
    "status:ended unexpectedly": "It has no summary and isn't running: it "
    "crashed or was killed. A training run can still resume.",
    # Agents tab
    "skills": "The best checkpoint's share of the heuristic's score on each "
    "skill. The outline is the heuristic (1.0), the rim is 1.5.",
    "skill:Braking": "Starts at 300 px/s aimed at a wall 80 to 140 px away, "
    "on the box: the share of stops with no damage.",
    "skill:Threading": "skill_gaps: three wall columns, each with one gap "
    "about 2.5 cars wide, checkpoints in order through them.",
    "skill:Open field": "The box: checkpoints anywhere, no walls. Fast "
    "hunting.",
    "skill:Long range": "skill_long: a big empty map (1600 x 1200), "
    "checkpoints far away.",
    "skill:Obstacles": "skill_pillars: twelve scattered pillars, checkpoints "
    "anywhere.",
    "skill:Corridor": "skill_corridor: a winding lane, checkpoints in order "
    "along it.",
    "skill:Detour": "skill_detour: a checkpoint inside a U that opens away "
    "from the start: the straight line hits its back wall.",
    "column:#": "Its place by share of the heuristic's score. Baselines "
    "aren't ranked.",
    "column:share": "The best checkpoint's average share of the heuristic's "
    "score across the skills (1.00: as good as the heuristic): the ranking.",
    "column:score": "The best checkpoint's mean game score over the skills' "
    "rounds.",
    "column:survive": "The share of each round survived.",
    "column:wrecks": "The share of rounds that ended wrecked.",
    "column:cp/min": "Checkpoints collected per minute.",
    "column:brake": "The share of braking tests passed without damage.",
    "column:best": "Its best checkpoint on the suite.",
    "high scores": "The best single rounds, from runs and your recordings. "
    "One round each, so a lucky seed counts: not a ranking.",
    "badge:TRAINING": "A run is training it right now.",
    "badge:MILESTONE": "It reached the first skilled agent milestone: a "
    "suite score above the heuristic's, wrecking in under half the "
    "rounds.",
    "badge:BRANCHED": "It started from another agent's checkpoint.",
    "badge:FROM YOUR DRIVING": "It learned from your recordings "
    "(imitation).",
    "heuristic ratio": "Its best suite score as a multiple of the "
    "heuristic's: above 1.0 beats it.",
    "history": "One suite result per scored checkpoint. A drop can mean it "
    "forgot a skill while learning something else.",
    # Recordings browser
    "recording:when": "When the round was recorded.",
    "recording:seed": "The round's seed: the same seed gives the same "
    "spawns and checkpoints.",
    "recording:score": "The round's game points.",
    "recording:ended": "time: the timer ran out. all out: the car was "
    "wrecked. stopped: you restarted or quit mid-round.",
    "recording:kept": "Kept rounds are never removed by the latest-50 "
    "limit (the oldest unkept ones go first).",
    "recording:game": "The stage and rules it was played on.",
    "recording:datasets": "The datasets that read it, by their rules "
    "(include, min_score). make dataset shows what's actually usable.",
    # Maps tab
    "driving style": "How the best checkpoint drives, over the suite's "
    "rounds: the share of steps on each pedal (forward, brake, coast, "
    "reverse), turning left or right, and moving backward. It warns when "
    "one habit dominates: backward over 40 %, braking over 50 %, coasting "
    "over 70 %, or turning one way over 80 %.",
    "map:BUILT-IN": "Ships with the app and changes only in code, so tests "
    "and suites can rely on it. Edit opens it to save as a new map of yours; "
    "Duplicate makes a copy.",
    "map:YOURS": "Yours, in user/stages/ (out of git): edit, duplicate, or "
    "delete it.",
    "map:DEFAULT": "The default map: the code and new stages start from "
    "it, so it can't be deleted.",
    "map:SUITE": "An evaluation suite plays on it, so it can't be deleted "
    "(scores would lose their map).",
    "map:BIG": "Bigger than the game's view: the game follows the car on "
    "it, with a map card.",
    "map:used by": "The runs that played on it (training, cloning, and "
    "episode runs, by agent or driver) and the suites that use it.",
    # Training tab
    "estimate": "From how long your last finished runs of the same kind "
    "took, per decision (or per epoch for imitation).",
    # Vital signs
    "stat:CPU": "The whole machine's CPU use, and our jobs' share. A "
    "training uses one core (10 % of a 10-core Mac). Amber at 70 %, red "
    "at 85 %.",
    "stat:MEMORY": "Memory in use (total minus available, as macOS counts "
    "it), and our jobs' share. macOS keeps about 80 % in use even when "
    "idle, so amber is at 88 % and red at 95 %.",
    "stat:BATTERY": "Battery left. Training drains it fast: amber whenever "
    "it's unplugged, red under 20 %.",
    "stat:DISK": "Free disk where the project lives. Amber under 20 GB, red "
    "under 5 GB.",
    "stat:JOBS": "Jobs running from this control center.",
}

# Form fields outside the Files tab: the Commands and Training tabs.
FORM_FIELDS: dict[str, tuple[str, str]] = {
    "Mode": ("", "Reinforcement learning: learn by trial and error from "
             "rewards. Imitation: copy your recorded driving. Or clone "
             "first, then improve with reinforcement learning."),
    "Agent": ("", "Who learns: an existing agent continues from its newest "
              "checkpoint, or a new one."),
    "Name": ("", "A new agent's name: letters, digits, - and _."),
    "Start": ("", "Fresh: random weights from the model. Or branch: start "
              "from any agent's checkpoint, keeping what it learned."),
    "Model": ("", "The network's shape (models/): small is two layers of "
              "64."),
    "Seed": ("", "The first episode's seed (and a new agent's first "
             "weights). The same seed repeats a run exactly."),
    "Trainer": ("", "How it learns (trainers/): learning rate, length, and "
                "the rest. Edit or duplicate one in the Files tab."),
    "Imitation trainer": ("", "How cloning learns (trainers/): epochs, "
                          "held-out share, and the rest."),
    "Dataset": ("", "Which of your recordings the clone learns from "
                "(datasets/)."),
    "Stage": ("", "The map it drives on (stages/)."),
    "Rules": ("", "Round length, scoring, and what wall hits do (rules/)."),
    "Round seconds": ("s", "A round length instead of the rules' own."),
    "From step": ("", "Start the replay at this step (120 a second): "
                  "it plays on unshown to there. Blank: the start."),
    "Rounds": ("", "Which of the dataset's rounds to teach (7g2): opens a "
               "list to tick them. Ticked at first: all but rounds on a "
               "test map and corrections of other agents."),
    "Recordings": ("", "Only these of the dataset's rounds (file names, "
                   "comma-separated). Blank: every round. The Training "
                   "tab fills it from the rounds you tick."),
    "Games": ("", "The most games played at once, each in its own small "
                      "process (step 8). The run starts with as many as "
                      "fit and drops one while memory or the CPU is busy, "
                      "so your other work comes first."),
    "Reward profile": ("", "What the agent is rewarded for, per step "
                       "(rewards/). Game points are the rules'; reward is "
                       "the agent's."),
    "Driver": ("", "Who drives: the keyboard, a baseline (heuristic, "
               "random), or an agent (its best scored checkpoint)."),
    "Episodes": ("rounds", "How many rounds to play."),
    "Rounds": ("rounds", "How many rounds to record. Each is saved, like "
               "your own, for an imitation dataset."),
    "Record": ("", "Save your rounds (recordings/), for replays and "
               "imitation."),
    "Player": ("", "Your recordings go under this name "
               "(recordings/<player>)."),
    "FPS cap": ("fps", "Frames per second at most. 0 matches the "
                "display."),
    "Branch from": ("", "Start a new agent from this checkpoint instead of "
                    "random weights."),
    "Suite": ("", "The fixed scenarios agents are scored on (suites/)."),
    "Checkpoints": ("", "highlights: the key checkpoints. all: every scored "
                    "one."),
    "Skill": ("", "The skill whose map and round the showcase starts on "
              "(the round the evaluation scored). M in the window changes "
              "it."),
    "Run": ("", "A run folder in runs/, newest first."),
    "Map": ("", "A stage's name: an existing one in stages/ opens, a new "
            "one starts from the box's size."),
    "File": ("", "A replay or recording file (or, for tests, a test file)."),
    "Entry": ("", "A trash entry: one per delete, holding everything that "
              "delete moved."),
}


def field(folder: str, path: str) -> tuple[str, str]:
    """(unit, text) for a file's field, or ("", "") if there's none."""
    if folder == "rewards" and path.startswith("terms."):
        rest = path[len("terms."):]
        if rest in TERMS:
            unit, text = TERMS[rest]
            return unit, f"{text} Its weight multiplies it, every step."
        return TERM_PARAMS.get(rest, ("", ""))
    generic = re.sub(r"\.\d+(\.|$)", r".*\1", path)
    table = FIELDS.get(folder, {})
    return table.get(path) or table.get(generic) or ("", "")


def form(name: str) -> tuple[str, str]:
    """(unit, text) for a Commands or Training tab field."""
    return FORM_FIELDS.get(name, ("", ""))


def topic(key: str) -> str:
    return TOPICS.get(key, "")
