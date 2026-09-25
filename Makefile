run:
	clear
	python app.py

test:
	clear
	python -m pytest

maze_car:
	clear
	python app.py -demo maze_car

replay:
	clear
	python app.py -replay $(FILE)
