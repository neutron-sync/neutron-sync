#!/usr/bin/env python3

import datetime
import json
import os
import shutil
from pathlib import Path
from typing import List

import typer
from git import Repo
from rich import print as rprint

app = typer.Typer()

CONFIG_FILE_PATH = Path(os.environ['HOME']) / '.local' / 'nsync' / 'config.json'
CONFIG_OPTION = typer.Option(
	default=CONFIG_FILE_PATH,
	exists=True,
	file_okay=True,
	dir_okay=False,
	writable=False,
	readable=True,
	resolve_path=True,
	envvar="NSYNC_CONFIG",
)

VERBOSE_OPTION =  typer.Option(False, "-v", help="verbose")
YES_OPTION = typer.Option(False, "-y", help="skip confirmation prompts")

@app.command()
def init(
		repo: Path = typer.Argument(
			None,
			exists=True,
			file_okay=False,
			dir_okay=True,
			writable=True,
			readable=True,
			resolve_path=True,
		),
		config_file: Path = typer.Option(
			default=CONFIG_FILE_PATH,
			exists=False,
			file_okay=True,
			dir_okay=False,
			writable=True,
			readable=False,
			resolve_path=True,
			envvar="NSYNC_CONFIG",
		)
	):
		if not config_file.parent.exists():
			config_file.parent.mkdir(parents=True)

		config = {
			'repo': str(repo),
			'translations': {
				'_home': os.environ['HOME'],
				'_root': '/',
			}
		}
		with open(config_file, 'w') as fh:
			json.dump(config, fh, indent=2)


def load_config(config_file):
	with open(config_file, 'r') as fh:
		data = json.load(fh)
		local_trans = {}
		for key, value in data['translations'].items():
			local_trans[value] = key

		return data['repo'], data['translations'], local_trans


def translate_to_repo(repo, local_trans, path):
	for base, trans in local_trans.items():
		if str(path).startswith(base):
			trans_full = repo + os.path.sep + trans
			if base.endswith(os.path.sep):
				trans_full += os.path.sep

			new_path = str(path).replace(base, trans_full, 1)
			new_rel = os.path.join(trans, path.relative_to(base))
			parent = Path(new_path).parent
			if not parent.exists():
				parent.mkdir(parents=True)

			return new_path, new_rel


def vprint(message, verbose):
	if verbose:
		rprint(message)


def git_command(repo, command, *args, verbose=False):
	repo = Repo(repo)
	message = f"[green]Command: git {command}"
	if args:
		message += " " + " ".join(args)

	message += "[/green]"

	vprint(message, verbose)
	out = getattr(repo.git, command)(*args)
	vprint("[bold blue]Output:[/bold blue]\n" + out, verbose)


def link_data_file(repo, rel=False):
	filename = 'nsync-links.json'

	if rel:
		return Path(filename)

	return Path(repo) / filename


def update_links(repo, to_path):
	lf = link_data_file(repo)
	repo = Path(repo)

	links = []
	rel_path = Path(to_path).relative_to(repo)
	if lf.exists():
		with open(lf, 'r') as fh:
			links = json.load(fh)

	links.append(str(rel_path))
	with open(lf, 'w') as fh:
			json.dump(links, fh, indent=2)


@app.command()
def link(
	paths: List[Path] = typer.Argument(
			None,
			exists=True,
			file_okay=True,
			dir_okay=True,
			writable=False,
			readable=True,
			resolve_path=True,
		),
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
		yes: bool = YES_OPTION,
	):
	"""
	Move a file to encrypted repo and link, commit, and push(optional)
	"""

	repo, repo_trans, local_trans = load_config(config_file)
	now = datetime.datetime.now(tz=datetime.timezone.utc)

	for from_path in paths:
		to_path, to_rel = translate_to_repo(repo, local_trans, from_path)

		vprint(f"mv {from_path} {to_path}", verbose)
		shutil.move(from_path, to_path)

		vprint(f"ln -s {to_path} {from_path}", verbose)
		os.symlink(to_path, from_path)
		update_links(repo, to_path)

		git_command(repo, "add", to_rel, verbose=verbose)

		message = f"nsync link @ {now.isoformat()}"
		git_command(repo, "commit", "-m", message, to_rel, verbose=verbose)

	git_command(repo, "add", str(link_data_file(repo, rel=True)), verbose=verbose)
	message = f"nsync links updated @ {now.isoformat()}"
	git_command(repo, "commit", "-m", message, str(link_data_file(repo, rel=True)), verbose=verbose)

	if yes:
		push = True

	else:
		push = typer.confirm("Push changes?")

	if push:
		git_command(repo, "push", verbose=verbose)


@app.command()
def pull(
		config_file: Path = CONFIG_OPTION,
	):
	"""
	Pull files from remote and re-link
	"""

	repo, repo_trans, local_trans = load_config(config_file)
	git_command(repo, "pull", verbose=True)
	# todo: relink


@app.command()
def push(
		config_file: Path = CONFIG_OPTION,
	):
	"""
	Push files to remote
	"""

	repo, repo_trans, local_trans = load_config(config_file)
	git_command(repo, "push", verbose=True)


@app.command()
def status(
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
	):
	"""
	Get repo status
	"""
	repo, repo_trans, local_trans = load_config(config_file)
	git_command(repo, "status", verbose=True)


@app.command()
def save(
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
	):
	"""
	Commit existing tracked files and push to remote
	"""
	repo, repo_trans, local_trans = load_config(config_file)
	now = datetime.datetime.now(tz=datetime.timezone.utc)
	message = f"nsync save @ {now.isoformat()}"
	git_command(repo, "commit", "-a", "-m", message, verbose=verbose)
	git_command(repo, "push", verbose=verbose)

if __name__ == "__main__":
	app()
