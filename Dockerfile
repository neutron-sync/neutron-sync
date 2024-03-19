FROM docker.io/bitnami/minideb:bookworm

RUN install_packages bash python3 pipx

RUN groupadd -r web && useradd -ms /bin/bash -g web web
RUN mkdir -p /app

COPY . /app
RUN chown -R web:web /app

USER web
WORKDIR /app

RUN pipx ensurepath
ENV PATH="${PATH}:/home/web/.local/bin"
RUN pipx install pdm
RUN pdm install

CMD pdm run python3 nsync/main.py server 0.0.0.0 8000
