FROM python:3.8-buster

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE 1

RUN adduser --disabled-password --gecos '' newuser \
    && adduser newuser sudo \
    && echo '%sudo ALL=(ALL:ALL) ALL' >> /etc/sudoers

RUN mkdir -p /octochain
RUN chown newuser /octochain
USER newuser
WORKDIR /octochain

COPY . .

USER root

RUN apt-get update && apt-get install -y postgresql-client
RUN apt-get install -y \
      gcc libc-dev memcached

RUN pip install --upgrade pip
RUN pip install -r requirements.txt