# One word per command, at most one parameter. `make help` lists them.

.PHONY: help main test test_file fixtures maze_car maze_car_heuristic \
	maze_car_random maze_car_driver maze_car_player maze_car_stage \
	maze_car_reward maze_car_rules maze_car_seconds maze_car_fps replay \
	runs run_heuristic run_random run_driver run_episodes run_reward \
	run_rules run_stage run_seconds run_best recordings replay_last \
	maze_car_norecord new_agent maze_car_agent run_agent train resume \
	resume_last

require = $(if $($(1)),,$(error $(1) is required, e.g. make $@ $(1)=$(2)))

help:
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
	@echo "  make resume RUN=folder               resume a stopped training run exactly"
	@echo "  make resume_last                     resume the newest stopped training run"
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
	$(call require,REWARD,time_bonus)
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

resume:
	$(call require,RUN,2026-09-26_120000_train-rookie_seed0)
	python app.py -resume $(RUN)

resume_last:
	python app.py -resume_last
