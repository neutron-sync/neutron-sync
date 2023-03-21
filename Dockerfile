FROM bitnami/python:3.10

ENV PYTHONUNBUFFERED 1

ARG userid
ARG groupid

RUN mkdir /opt/neutron-sync
WORKDIR /opt/neutron-sync

RUN install_packages git-crypt
RUN pip3 install --upgrade pip && pip3 install --upgrade pdm

COPY . /opt/neutron-sync
RUN pdm install

# User setup
RUN addgroup nsync --gid $groupid
RUN useradd -ms /bin/bash -u $userid -g $groupid nsync
RUN chown -R nsync:nsync /opt/neutron-sync
RUN echo 'nsync ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER nsync

ENV HOME /home/nsync
ENV USER nsync
