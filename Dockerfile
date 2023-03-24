FROM bitnami/python:3.10

ENV PYTHONUNBUFFERED 1

ARG userid
ARG groupid

WORKDIR /opt/neutron-sync

RUN install_packages git-crypt sudo openssh-client nano
RUN pip3 install --upgrade pip && pip3 install --upgrade pdm

# User setup
RUN addgroup nsync --gid $groupid
RUN useradd -ms /bin/bash -u $userid -g $groupid nsync
RUN echo 'nsync ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER nsync

ENV HOME /home/nsync
ENV USER nsync

RUN ln -s /opt/neutron-sync/.bash_history /home/nsync/.bash_history
