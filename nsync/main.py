#!/usr/bin/env python3

import datetime
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List

import typer
import uvicorn

from git import Repo
from rich import print as rprint

import nsync
from nsync.client import ApiClient


app = typer.Typer(pretty_exceptions_enable=False)

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
def version():
		"""
		Display version
		"""
		print(f'Version: {nsync.__version__}')


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
		),
		verbose: bool = VERBOSE_OPTION,
	):
		"""
		Create an nsync configuration file
		"""
		if repo is None:
			print('repo argument is required')
			sys.exit(1)

		if not config_file.parent.exists():
			config_file.parent.mkdir(parents=True)

		if config_file.exists():
			print('Using existing config:', config_file)
			with config_file.open('r') as fh:
				config = json.load(fh)

			config['repo'] = str(repo)

		else:
			config = {
				'repo': str(repo),
				'translations': {
					'_home': os.environ['HOME'],
					'_root': '/',
				}
			}
			print('Creating config:', config_file)

		with config_file.open('w') as fh:
			json.dump(config, fh, indent=2)

		attr_file = repo / '.gitattributes'
		if not attr_file.exists():
			with attr_file.open('w') as fh:
				for d, path in config['translations'].items():
					fh.write(f'{d}/** filter=git-crypt diff=git-crypt\n')

			print('Wrote new attributes:', attr_file)
			git_command(repo, "add", str(attr_file), verbose=verbose)
			git_command(repo, "commit", "-m", "initial .gitattributes", str(attr_file), verbose=verbose)

		rprint('[bold]Sponsor this project: https://github.com/sponsors/neutron-sync[/bold]')


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


def translate_to_fs(repo_rel, repo_trans):
	for base, trans in repo_trans.items():
		if repo_rel.startswith(base):
			new_path = repo_rel.replace(base + os.path.sep, "", 1)
			return Path(trans) / new_path


def vprint(message, verbose, rich=True):
	if verbose:
		if rich:
			rprint(message)
		else:
			print(message)


def confirm_apply(yes, question, func, *args, **kwargs):
	do_apply = False
	if yes:
		do_apply = True

	else:
		do_apply = typer.confirm(question)

	if do_apply:
		if func:
			func(*args, **kwargs)

	return do_apply


def git_command(repo, command, *args, verbose=False):
	repo = Repo(repo)
	message = f"[green]Command: git {command}"
	if args:
		message += " " + " ".join(args)

	message += "[/green]"

	rprint(message)
	out = getattr(repo.git, command)(*args)
	rprint("[bold blue]Output:[/bold blue]\n")
	print(out)


def link_data_file(repo, rel=False):
	filename = 'nsync-links.json'

	if rel:
		return Path(filename)

	return Path(repo) / filename


def perms_data_file(repo, rel=False):
	filename = 'nsync-perms.json'

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


def remove_path(path):
	if path.is_dir():
		shutil.rmtree(path)

	else:
		path.unlink()


def relink(repo, repo_trans, verbose=False, yes=False):
	with open(link_data_file(repo), 'r') as fh:
		links = json.load(fh)
		for link in links:
			src_path = Path(repo) / link
			dst_path = translate_to_fs(link, repo_trans)

			recreate = False
			remove = False
			if dst_path.exists():
				if dst_path.is_symlink():
					if not os.readlink(str(dst_path)) == str(src_path):
						remove = True
						recreate = True

				else:
					remove = True
					recreate = True

			else:
				recreate = True

			if remove:
				if confirm_apply(yes, f"Remove {dst_path} before relinking?", remove_path, dst_path):
					pass

				else:
					vprint(f"[red]Skipped Link:[/red] {dst_path} -> {src_path}", True)
					continue

			if recreate:
				vprint(f"[green]Recreate Link:[/green] {dst_path} -> {src_path}", True)
				if not dst_path.parent.exists():
					dst_path.parent.mkdir(parents=True)

				os.symlink(src_path, dst_path)


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

	save_permissions(repo)
	git_command(repo, "add", str(perms_data_file(repo, rel=True)), verbose=verbose)
	message = f"nsync perms updated @ {now.isoformat()}"
	git_command(repo, "commit", "-m", message, str(perms_data_file(repo, rel=True)), verbose=verbose)

	confirm_apply(yes, "Push changes?", git_command, repo, "push", verbose=verbose)


@app.command()
def pull(
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
		yes: bool = YES_OPTION,
	):
	"""
	Pull files from remote and re-link
	"""

	repo, repo_trans, local_trans = load_config(config_file)
	git_command(repo, "pull", verbose=True)
	relink(repo, repo_trans, verbose, yes)
	apply_perms(config_file, verbose)


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
	save_permissions(repo)
	message = f"nsync save @ {now.isoformat()}"
	git_command(repo, "add", ".", verbose=verbose)
	git_command(repo, "commit", "-a", "-m", message, verbose=verbose)
	git_command(repo, "push", verbose=verbose)


@app.command()
def remove(
		paths: List[Path] = typer.Argument(
			None,
			exists=True,
			file_okay=True,
			dir_okay=True,
			writable=True,
			readable=True,
			resolve_path=False,
		),
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
		yes: bool = YES_OPTION,
	):
	"""
	Remove a file locally and in the repo
	"""
	repo, repo_trans, local_trans = load_config(config_file)
	now = datetime.datetime.now(tz=datetime.timezone.utc)

	for dst_path in paths:
		src_path, src_rel = translate_to_repo(repo, local_trans, dst_path)

		if confirm_apply(yes, f"Remove and unlink {dst_path}?", None):
			vprint(f"rm {dst_path}", verbose)
			dst_path.unlink()
			git_command(repo, "rm", "-f", str(src_rel), verbose=verbose)
			message = f"nsync remove @ {now.isoformat()}"
			git_command(repo, "commit", "-m", message, str(src_rel), verbose=verbose)

	confirm_apply(yes, "Push changes?", git_command, repo, "push", verbose=verbose)


@app.command()
def restore_local_only(
		paths: List[Path] = typer.Argument(
			None,
			exists=True,
			file_okay=True,
			dir_okay=True,
			writable=True,
			readable=True,
			resolve_path=False,
		),
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
		yes: bool = YES_OPTION,
	):
	"""
	Remove file from repo and put back to the local location
	"""
	repo, repo_trans, local_trans = load_config(config_file)
	now = datetime.datetime.now(tz=datetime.timezone.utc)


def get_permissions(data, base, link):
	src_path = base / link

	data[link] = {'mode': src_path.stat().st_mode}
	if src_path.is_dir():
		data[link]['contents'] = {}
		for p in src_path.iterdir():
			get_permissions(data[link]['contents'], p.parent, p.name)


def save_permissions(repo):
	"""
	Get file permissions and save in data file
	"""

	with open(link_data_file(repo), 'r') as fh:
		links = json.load(fh)

		data = {}
		for link in links:
			get_permissions(data, Path(repo), link)

	with open(perms_data_file(repo), 'w') as fh:
		json.dump(data, fh, indent=2)


def apply_permissions(data, base, repo_path, verbose):
	for p, stats in data.items():
		path = base / p
		relpath = str(path).replace(repo_path, '')
		if path.exists():
			vprint(f"Setting {relpath} {oct(stats['mode'])}", verbose, rich=False)
			path.chmod(stats['mode'])
			if 'contents' in stats:
				apply_permissions(stats['contents'], path, repo_path, verbose)


@app.command()
def apply_perms(
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
	):
		"""
		reapply file permissions from remote
		"""
		repo, repo_trans, local_trans = load_config(config_file)

		with open(perms_data_file(repo), 'r') as fh:
			data = json.load(fh)

		apply_permissions(data, Path(repo), str(Path(repo)) + '/', verbose)


@app.command()
def start_transfer(
		key_file: Path = typer.Argument(
			Path(os.environ['HOME']) / '.dotfiles.key',
			exists=True,
			file_okay=True,
			dir_okay=False,
			writable=False,
			readable=True,
			resolve_path=False,
		),
		file: List[Path] = typer.Option(
			[
				Path(os.environ['HOME']) / '.ssh' / 'id_rsa',
				Path(os.environ['HOME']) / '.ssh' / 'id_rsa.pub'
			],
			exists=True,
			file_okay=True,
			dir_okay=False,
			writable=False,
			readable=True,
			resolve_path=False,
		),
		server_url: str = typer.Option('https://www.neutronsync.com/'),
		encryption_password: str = typer.Option(None, prompt=True),
		yes: bool = YES_OPTION,
	):
		"""
		Transfer small text files to another machine
		"""
		client = ApiClient(server_url)
		files = [key_file] + file
		message = "Transfer files?\n" + "\n".join(str(f) for f in files) + "\n"
		confirm_apply(yes, message, client.transfer_files, encryption_password, *files)
		rprint(f'[bold]Storage Key:[/bold] [green]{client.last_data["key"]}[/green]')
		print(f'Expiration: {client.last_data["expiration"]}')

@app.command()
def complete_transfer(
		server_url: str = typer.Option('https://www.neutronsync.com/'),
		encryption_password: str = typer.Option(None, prompt=True),
		storage_key: str = typer.Option(None, prompt=True),
	):
		"""
		Complete a transfer of files on another machine
		"""
		client = ApiClient(server_url)
		client.download(encryption_password, storage_key)


@app.command()
def server(
		host: str = typer.Argument('127.0.0.1', envvar="HOST"),
		port: int = typer.Argument(8000, envvar="PORT")
	):
		"""
		Run a transfer server
		"""
		config = uvicorn.Config('nsync.server:app', host=host, port=port, log_level="info", reload=True)
		server = uvicorn.Server(config)
		server.run()



if __name__ == "__main__":
	app()
