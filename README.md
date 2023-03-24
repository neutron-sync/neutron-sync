# Neutron Sync

A command line utility to sync your personal dotfiles to an encrypted Github. This allows you to share your personal secrets across multiple machines and keep them in sync.

### [Sponsor This Project](https://github.com/sponsors/neutron-sync)

## Installation

`pipx install neutron-sync`

*[See pipx](https://pypa.github.io/pipx/)*

## Additional Docs

- [How Neutron Sync Works](https://github.com/neutron-sync/neutron-sync/blob/main/docs/how-it-works.md)

## Primary Setup

### Requirements

- Private Github repository
- git-crypt installed, see https://github.com/AGWA/git-crypt/blob/master/INSTALL.md
    - Ubuntu/Debian: `sudo apt install git-crypt`
    - Redhat: `sudo yum install git-crypt`
    - Mac: `brew install git-crypt`

### Setup

```
git clone git@github.com:{github-user}/{repo-name}.git
cd {repo-name}
git-crypt init
nsync init `pwd`
git-crypt export-key ~/.dotfiles.key
git-crypt unlock ~/.dotfiles.key
# you may get an error if you have no files initially which is OK
```

### Add files

*adds to encrypted repo and creates link at original location*

```bash
# link a directory
nsync link ~/.ssh

# link a file
nsync link ~/.tmux.conf
```

### Commit and Push

*when files are changed*

`nsync save`

### Pull Changes from Remote

`nsync pull`


## Setup on Another Machine

### Transfer Keys to Secondary

While files are synced via the git repository, you need to transfer keys to the secondary machine so you can decrypt the repository. By default, it will transfer you encryption key and ssh key.

**On Primary:**

```bash
nsync start-transfer
# follow prompts
```

**On Secondary:**
```bash
nsync complete-transfer
# follow prompts
mv {output-dir}/.dotfiles.key ~
mkdir .ssh
chmod 700 .ssh
mv {output-dir}/id_rsa ~/.ssh
mv {output-dir}/id_rsa.pub ~/.ssh
```

### Setup - Secondary

```
git clone git@github.com:{github-user}/{repo-name}.git
cd {repo-name}
nsync init `pwd`
nsync pull
```

## Transfer Server

The transfer server can be used to help assist in setting up a new machine. After initial setup, all transactions are stored in your git repository. All files stored on the transfer server are encrypted on device before being sent and only stored temporarily.

File transfers default to using https://www.neutronsync.com/. You can host your own server by running:

`nsync server`
