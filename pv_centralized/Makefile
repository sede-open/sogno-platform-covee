SHELL := /bin/bash

init:
	python3 ./setup/createEnv.py -y
	source covee/bin/activate -y && \
	pip install --upgrade pip && \
	pip install -r ./setup/requirements.txt
clean:
	sudo rm -R -f covee
	rm -R -f __pycache__
	rm -R -f covee.egg-info