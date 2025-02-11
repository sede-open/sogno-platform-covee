SHELL := /bin/bash

init:
	pip install --upgrade pip --root-user-action=ignore
	pip install . --root-user-action=ignore
clean:
	sudo rm -R -f covee_env
	rm -R -f __pycache__
	rm -R -f covee_env.egg-info
	rm -R -f covee.egg-info
	rm -R -f dist
	rm -R -f build