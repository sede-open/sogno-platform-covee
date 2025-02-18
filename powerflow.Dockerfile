FROM ubuntu:latest
MAINTAINER Edoardo De Din ededin@eonerc.rwth-aachen.de

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install build-essential -y \
    && apt install python3-pip -y \
    && apt-get install python3-venv -y \
    && apt-get install sudo -y 

COPY powerflow/setup/requirements_docker.txt .

RUN python3 -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements_docker.txt

ENV PATH="/opt/venv/bin:$PATH"
