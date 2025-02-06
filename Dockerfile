FROM ubuntu:18.04
FROM python:3.11.2
LABEL author="Edoardo De Din ededin@eonerc.rwth-aachen.de"

RUN apt-get update -y \
    && apt-get upgrade -y \ 
    && apt-get install build-essential -y \
    && apt install python3-pip -y  \
    && apt-get install python3-venv -y \
    && apt-get install sudo -y 
