#!/usr/bin/env python3

import json
import os
import shutil
from pathlib import Path
from typing import List

import typer

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
			trans = repo + os.path.sep + trans
			if base.endswith(os.path.sep):
				trans += os.path.sep

			new_path = str(path).replace(base, trans, 1)
			return new_path

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
		config_file: Path = CONFIG_OPTION
	):
	repo, repo_trans, local_trans = load_config(config_file)

	for from_path in paths:
		to_path = translate_to_repo(repo, local_trans, from_path)

		print(f"mv {from_path} {to_path}")
		shutil.move(from_path, to_path)
		print(f"ln -s {to_path} {from_path}")
		os.symlink(to_path, from_path)

@app.command()
def pull(config_file: Path = CONFIG_OPTION):
	pass

if __name__ == "__main__":
	app()
