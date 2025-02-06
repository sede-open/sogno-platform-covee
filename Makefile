SHELL := /bin/bash

init:
	pip install --upgrade pip
	pip install .
clean:
	sudo rm -R -f covee_env
	rm -R -f __pycache__
	rm -R -f covee_env.egg-info
	rm -R -f covee.egg-info
	rm -R -f dist
	rm -R -f build