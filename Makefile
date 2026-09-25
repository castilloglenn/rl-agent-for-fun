# One word per command, at most one parameter. `make help` lists them.

.PHONY: help run test test_file fixtures maze_car maze_car_heuristic \
	maze_car_random maze_car_driver maze_car_player maze_car_stage \
	maze_car_reward maze_car_rules maze_car_seconds maze_car_fps replay

require = $(if $($(1)),,$(error $(1) is required, e.g. make $@ $(1)=$(2)))

help:
	@echo "Play"
	@echo "  make maze_car                        drive with the keyboard"
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
	@echo "Develop"
	@echo "  make test                            run all tests"
	@echo "  make test_file FILE=path             run one test file"
	@echo "  make fixtures                        regenerate behavior fixtures"
	@echo "  make run                             agent entry point (stub)"

run:
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
