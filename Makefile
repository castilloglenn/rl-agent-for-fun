# One word per command, at most one parameter. `make help` lists them.

.PHONY: help main test test_file fixtures maze_car maze_car_heuristic \
	maze_car_random maze_car_driver maze_car_player maze_car_stage \
	maze_car_reward maze_car_rules maze_car_seconds maze_car_fps replay \
	runs run_heuristic run_random run_driver run_episodes run_reward \
	run_rules run_stage run_seconds run_best recordings replay_last \
	maze_car_norecord new_agent maze_car_agent run_agent train resume \
	resume_last eval eval_baselines agents agent dataset imitate \
	showcase showcase_all control vitals stop_all delete_run trash restore \
	empty_trash delete_agent keep unkeep delete_recording edit_map \
	record_heuristic imitate_heuristic train_curriculum correct \
	imitate_corrections record_navigator imitate_navigator finetune

require = $(if $($(1)),,$(error $(1) is required, e.g. make $@ $(1)=$(2)))

help:
	@echo "Control center"
	@echo "  make control                         every command below, in a window"
	@echo "  make vitals                          the machine's readings while it was open"
	@echo "  make stop_all                        stop every job of this project (Ctrl+C first)"
	@echo "Play"
	@echo "  make maze_car                        drive with the keyboard (recorded)"
	@echo "  make maze_car_norecord               drive without recording"
	@echo "  make maze_car_heuristic              watch the heuristic baseline"
	@echo "  make maze_car_random                 watch the random baseline"
	@echo "  make maze_car_driver DRIVER=name     keyboard, random, heuristic"
	@echo "  make maze_car_player PLAYER=name     drive, with your player name"
	@echo "  make maze_car_stage STAGE=name       another stage (name or path)"
	@echo "  make maze_car_reward REWARD=name     another reward profile"
	@echo "  make maze_car_rules RULES=name       other game rules (standard, sprint, marathon)"
	@echo "  make maze_car_seconds SECONDS=n      another round length (renames the rules)"
	@echo "  make maze_car_fps FPS=n              cap the frame rate"
	@echo "Replays"
	@echo "  make replay FILE=path                watch a replay (.jsonl, .jsonl.gz)"
	@echo "  make replay_last                     watch your newest recording"
	@echo "  make recordings                      list recorded rounds per player"
	@echo "Experiment runs (headless, 100 episodes, saved in runs/)"
	@echo "  make runs                            list all runs"
	@echo "  make run_heuristic                   run the heuristic baseline"
	@echo "  make run_random                      run the random baseline"
	@echo "  make run_driver DRIVER=name          run any driver"
	@echo "  make run_episodes EPISODES=n         heuristic, n episodes"
	@echo "  make run_reward REWARD=name          heuristic, another reward profile"
	@echo "  make run_rules RULES=name            heuristic, other game rules"
	@echo "  make run_stage STAGE=name            heuristic, another stage"
	@echo "  make run_seconds SECONDS=n           heuristic, another round length"
	@echo "  make run_best RUN=folder             watch a run's best replay"
	@echo "Agents (saved in agents/)"
	@echo "  make new_agent AGENT=id              create an untrained agent (small model)"
	@echo "  make maze_car_agent AGENT=id         watch an agent drive"
	@echo "  make run_agent AGENT=id              run an agent for 100 episodes"
	@echo "  make train AGENT=id                  train an agent (trainers/default.json)"
	@echo "  make train_curriculum AGENT=id       train it up the skills curriculum (easy, then hard, by itself)"
	@echo "  make finetune AGENT=id               continue a clone with RL, gently (trainers/finetune.json), on the curriculum"
	@echo "  make resume RUN=folder               resume a stopped training run exactly"
	@echo "  make resume_last                     resume the newest stopped training run"
	@echo "  make eval AGENT=id                   score an agent's checkpoints (suites/skills.json)"
	@echo "  make eval_baselines                  score the heuristic and random baselines"
	@echo "  make agents                          list agents: best score, milestone"
	@echo "  make agent AGENT=id                  an agent's digest: lineage, scores, trend"
	@echo "  make showcase AGENT=id               watch its progression: highlight checkpoints"
	@echo "  make edit_map STAGE=name             the map editor: open a stage, or start a new one"
	@echo "  make showcase_all AGENT=id           watch every scored checkpoint"
	@echo "  make dataset                         preview your recordings as an imitation dataset"
	@echo "  make imitate AGENT=id                clone your driving into an agent (datasets/mine.json)"
	@echo "  make record_heuristic STAGE=basics   record 50 heuristic rounds (a stage or mix) for imitation"
	@echo "  make imitate_heuristic AGENT=id      clone the heuristic's recorded driving (datasets/heuristic.json)"
	@echo "  make record_navigator STAGE=name     record 50 navigator rounds (default mix route_lessons) to clone"
	@echo "  make imitate_navigator AGENT=id      clone the navigator's driving (datasets/navigator.json)"
	@echo "  make correct AGENT=id                watch it with REC corrections: take over where it goes wrong"
	@echo "  make imitate_corrections AGENT=id    learn your corrections (then train again)"
	@echo "Files"
	@echo "  make delete_run RUN=folder           move a run into the trash (its checkpoints stay)"
	@echo "  make delete_agent AGENT=id           move an agent and its runs into the trash"
	@echo "  make keep FILE=path                  keep a recording (never removed by the limit)"
	@echo "  make unkeep FILE=path                move a kept recording back with the recent ones"
	@echo "  make delete_recording FILE=path      move a recording into the trash"
	@echo "  make trash                           list what's in the trash"
	@echo "  make restore TRASH=entry             put a trash entry back where it was"
	@echo "  make empty_trash                     delete the trash for good"
	@echo "Develop"
	@echo "  make test                            run all tests"
	@echo "  make test_file FILE=path             run one test file"
	@echo "  make fixtures                        regenerate behavior fixtures"
	@echo "  make main                            agent entry point (stub)"

main:
	clear
	python app.py

test:
	clear
	python -m pytest

test_file:
	$(call require,FILE,tests/test_replay.py)
	clear
	python -m pytest $(FILE)

fixtures:
	python -m tests.generate_behavior_fixtures

maze_car:
	clear
	python app.py -demo maze_car

maze_car_norecord:
	clear
	python app.py -demo maze_car --norecord

maze_car_heuristic:
	clear
	python app.py -demo maze_car --driver heuristic

maze_car_random:
	clear
	python app.py -demo maze_car --driver random

maze_car_driver:
	$(call require,DRIVER,heuristic)
	clear
	python app.py -demo maze_car --driver $(DRIVER)

maze_car_player:
	$(call require,PLAYER,zen)
	clear
	python app.py -demo maze_car --player $(PLAYER)

maze_car_stage:
	$(call require,STAGE,box)
	clear
	python app.py -demo maze_car --maze_car.stage=$(STAGE)

maze_car_reward:
	$(call require,REWARD,default)
	clear
	python app.py -demo maze_car --reward $(REWARD)

maze_car_rules:
	$(call require,RULES,sprint)
	clear
	python app.py -demo maze_car --maze_car.rules=$(RULES)

maze_car_seconds:
	$(call require,SECONDS,90)
	clear
	python app.py -demo maze_car --round_seconds $(SECONDS)

maze_car_fps:
	$(call require,FPS,60)
	clear
	python app.py -demo maze_car --maze_car.display.max_fps=$(FPS)

replay:
	$(call require,FILE,path/to/replay.jsonl)
	clear
	python app.py -replay $(FILE)

runs:
	python app.py -list_runs

run_heuristic:
	python app.py -run heuristic --driver heuristic

run_random:
	python app.py -run random --driver random

run_driver:
	$(call require,DRIVER,heuristic)
	python app.py -run $(DRIVER) --driver $(DRIVER)

run_episodes:
	$(call require,EPISODES,500)
	python app.py -run heuristic --driver heuristic --episodes $(EPISODES)

run_reward:
	$(call require,REWARD,default)
	python app.py -run heuristic-$(REWARD) --driver heuristic --reward $(REWARD)

run_rules:
	$(call require,RULES,sprint)
	python app.py -run heuristic-$(RULES) --driver heuristic --rules $(RULES)

run_stage:
	$(call require,STAGE,box)
	python app.py -run heuristic-$(STAGE) --driver heuristic --stage $(STAGE)

run_seconds:
	$(call require,SECONDS,90)
	python app.py -run heuristic-$(SECONDS)s --driver heuristic --round_seconds $(SECONDS)

run_best:
	$(call require,RUN,runs/<folder>)
	python app.py -best_replay $(RUN)

recordings:
	python app.py -list_recordings

replay_last:
	clear
	python app.py -replay_last


new_agent:
	$(call require,AGENT,my_agent)
	python app.py -new_agent $(AGENT)

maze_car_agent:
	$(call require,AGENT,my_agent)
	clear
	python app.py -demo maze_car --driver agent:$(AGENT)

run_agent:
	$(call require,AGENT,my_agent)
	python app.py -run $(AGENT) --driver agent:$(AGENT)

train:
	$(call require,AGENT,my_agent)
	python app.py -train $(AGENT)

train_curriculum:
	$(call require,AGENT,my_agent)
	python app.py -train $(AGENT) --stage skills

finetune:
	$(call require,AGENT,my_clone)
	python app.py -train $(AGENT) --trainer finetune --stage skills

resume:
	$(call require,RUN,2026-09-26_120000_train-rookie_seed0)
	python app.py -resume $(RUN)

resume_last:
	python app.py -resume_last

eval:
	$(call require,AGENT,my_agent)
	python app.py -eval $(AGENT)

eval_baselines:
	python app.py -eval_baselines

agents:
	python app.py -list_agents

agent:
	$(call require,AGENT,my_agent)
	python app.py -show_agent $(AGENT)

dataset:
	python app.py -preview_dataset

showcase:
	$(call require,AGENT,my_agent)
	clear
	python app.py -showcase $(AGENT)

showcase_all:
	$(call require,AGENT,my_agent)
	clear
	python app.py -showcase $(AGENT) --showcase_all

imitate:
	$(call require,AGENT,my_clone)
	python app.py -imitate $(AGENT)

record_heuristic:
	python app.py -record_rounds heuristic --stage $(or $(STAGE),basics)

imitate_heuristic:
	$(call require,AGENT,my_clone)
	python app.py -imitate $(AGENT) --dataset heuristic

record_navigator:
	python app.py -record_rounds navigator --stage $(or $(STAGE),route_lessons)

imitate_navigator:
	$(call require,AGENT,my_clone)
	python app.py -imitate $(AGENT) --dataset navigator

correct:
	$(call require,AGENT,my_agent)
	clear
	python app.py -demo maze_car --driver agent:$(AGENT) --corrections

imitate_corrections:
	$(call require,AGENT,my_agent)
	python app.py -imitate $(AGENT) --dataset corrections --imitation_trainer correct

control:
	python app.py -control

edit_map:
	$(call require,STAGE,my_map)
	python app.py -edit_map $(STAGE)

vitals:
	python app.py -vitals

stop_all:
	python app.py -stop_all

delete_run:
	$(call require,RUN,2026-09-27_003302_train-rookie_seed0)
	python app.py -delete_run $(RUN)

delete_agent:
	$(call require,AGENT,rookie)
	python app.py -delete_agent $(AGENT)

keep:
	$(call require,FILE,recordings/You/2026-09-27_014237_seed136188_score3733_time.jsonl.gz)
	python app.py -keep $(FILE)

unkeep:
	$(call require,FILE,recordings/You/kept/2026-09-27_014237_seed136188_score3733_time.jsonl.gz)
	python app.py -unkeep $(FILE)

delete_recording:
	$(call require,FILE,recordings/You/2026-09-27_014237_seed136188_score3733_time.jsonl.gz)
	python app.py -delete_recording $(FILE)

trash:
	python app.py -list_trash

restore:
	$(call require,TRASH,2026-09-27_120000_run-2026-09-27_003302_train-rookie_seed0)
	python app.py -restore $(TRASH)

empty_trash:
	python app.py -empty_trash
