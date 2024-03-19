FROM docker.io/bitnami/minideb:bookworm

RUN install_packages bash python3 pipx git-crypt redis-server

RUN groupadd -r web && useradd -ms /bin/bash -g web web
RUN mkdir -p /app

COPY . /app
RUN chown -R web:web /app

USER web
WORKDIR /app

RUN pipx ensurepath
ENV PATH="${PATH}:/home/web/.local/bin"
ENV PYTHONUNBUFFERED=1
RUN pipx install pdm
RUN pipx install honcho
RUN pdm install

CMD honcho start
