SHELL := /bin/bash

all:
	$(MAKE) -C pv_centralized init
	$(MAKE) -C powerflow init

clean:
	$(MAKE) -C pv_centralized clean
	$(MAKE) -C powerflow clean

ext:
	python3 ./setup_ext/createEnv.py -y 
	source venv_ext/bin/activate -y && \
	sudo apt-get install python3-venv && \
	pip install --upgrade pip && \
	pip install -r ./setup_ext/requirements.txt 

clean_ext:
	rm -R -f venv_ext
	rm -R -f __pycache__
	rm -R -f venv_ext.egg-info
