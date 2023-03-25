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
		Display version of the program.
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
		Create a configuration file for nsync.

		Parameters:
		----------
		repo : Path
			Path to the repository.
		config_file : Path
			Path to the configuration file.
		verbose : bool
			Whether or not to run the command in verbose mode.
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
	"""
	Load configuration file.

	Parameters:
	----------
	config_file : Path
		Path to the configuration file.
	
	Returns:
	-------
	tuple
		A tuple containing the repository, translations and local translations.
	"""
	with open(config_file, 'r') as fh:
		data = json.load(fh)
		local_trans = {}
		for key, value in data['translations'].items():
			local_trans[value] = key

		return data['repo'], data['translations'], local_trans


def translate_to_repo(repo, local_trans, path):
	"""
	Translate local file path to remote path in the repo.

	Args:
		repo (str): Remote repo path.
		local_trans (dict): Dictionary containing local path and its translations to remote.
		path (Path): Local path to file.

	Returns:
		Tuple containing remote path and its translation.
	"""
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
	"""
	Translate remote file path to local file path.

	Args:
		repo_rel (str): Remote path to file.
		repo_trans (dict): Dictionary containing remote path and its translations to local.

	Returns:
		Local path to the file.
	"""
	for base, trans in repo_trans.items():
		if repo_rel.startswith(base):
			new_path = repo_rel.replace(base + os.path.sep, "", 1)
			return Path(trans) / new_path


def vprint(message, verbose, rich=True):
	"""
	Print a message to the console based on whether verbose mode is enabled.

	Args:
		message (str): The message to print.
		verbose (bool): Whether verbose mode is enabled.
		rich (bool, optional): Whether to use rich print. Defaults to True.
	"""
	if verbose:
		if rich:
			rprint(message)
		else:
			print(message)


def confirm_apply(yes, question, func, *args, **kwargs):
	"""Confirm with user before applying a function.

	Args:
		yes (bool): If True, automatically apply the function.
		question (str): The confirmation question to ask the user.
		func (callable): The function to apply if confirmed.
		*args: Any positional arguments for the function.
		**kwargs: Any keyword arguments for the function.

	Returns:
		bool: Whether the function was applied or not.
	"""
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
	"""
	Execute a Git command.

	Args:
		repo (str): The path to the Git repository.
		command (str): The Git command to execute.
		*args: Any positional arguments for the command.
		verbose (bool, optional): Whether verbose mode is enabled. Defaults to False.
	"""
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
	"""
	Returns the path to the 'nsync-links.json' file.

	Args:
	repo (str): The path of the repository.
	rel (bool): If True, return the filename only. If False, return the full path.

	Returns:
	Path: The path to the 'nsync-links.json' file.
	"""

	filename = 'nsync-links.json'

	if rel:
		return Path(filename)

	return Path(repo) / filename


def perms_data_file(repo, rel=False):
	"""
	Returns the path to the 'nsync-perms.json' file.

	Args:
	repo (str): The path of the repository.
	rel (bool): If True, return the filename only. If False, return the full path.

	Returns:
	Path: The path to the 'nsync-perms.json' file.
	"""
	filename = 'nsync-perms.json'

	if rel:
		return Path(filename)

	return Path(repo) / filename


def update_links(repo, to_path):
	"""
	Updates the 'nsync-links.json' file by appending the relative path of the added file to it.

	Args:
	repo (str): The path of the repository.
	to_path (str): The path of the file that was added to the repository.
	"""
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
	"""
	Removes the specified path, either a file or directory.

	Args:
	path (Path): The path to be removed.
	"""
	if path.is_dir():
		shutil.rmtree(path)

	else:
		path.unlink()


def relink(repo, repo_trans, verbose=False, yes=False):
	"""
	Relinks all the files in the 'nsync-links.json' file.

	Args:
	repo (str): The path of the repository.
	repo_trans (dict): A dictionary that maps the paths of the local files to their encrypted counterparts.
	verbose (bool): If True, print detailed output. If False, print only important output.
	yes (bool): If True, don't ask for confirmation before removing a symlink. If False, ask for confirmation.
	"""
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

	Args:
	    paths (List[Path], optional): List of paths to move to encrypted repo and link. Defaults to None.
	    config_file (Path, optional): Path to the config file. Defaults to CONFIG_OPTION.
	    verbose (bool, optional): If True, show verbose output. Defaults to VERBOSE_OPTION.
	    yes (bool, optional): If True, answer "yes" to all prompts. Defaults to YES_OPTION.
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

	Args:
	    config_file (Path, optional): Path to the config file. Defaults to CONFIG_OPTION.
	    verbose (bool, optional): If True, show verbose output. Defaults to VERBOSE_OPTION.
	    yes (bool, optional): If True, answer "yes" to all prompts. Defaults to YES_OPTION.
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

	Args:
	    config_file (Path, optional): Path to the config file. Defaults to CONFIG_OPTION.
	"""

	repo, repo_trans, local_trans = load_config(config_file)
	git_command(repo, "push", verbose=True)


@app.command()
def status(
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
	):
	"""
	Get the status of the repository.

	Parameters:
	-----------
	config_file : Path, optional
		The path of the configuration file to load.
	verbose : bool, optional
		Whether to print verbose output.

	"""
	repo, repo_trans, local_trans = load_config(config_file)
	git_command(repo, "status", verbose=True)


@app.command()
def save(
		config_file: Path = CONFIG_OPTION,
		verbose: bool = VERBOSE_OPTION,
	):
	"""
	Commit existing tracked files and push to remote.

	Parameters:
	-----------
	config_file : Path, optional
		The path of the configuration file to load.
	verbose : bool, optional
		Whether to print verbose output.

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
	Remove a file locally and in the repo.

	Parameters:
	-----------
	paths : List[Path], optional
		A list of paths of files or directories to remove.
	config_file : Path, optional
		The path of the configuration file to load.
	verbose : bool, optional
		Whether to print verbose output.
	yes : bool, optional
		Whether to proceed with removal without prompting the user.
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

	Args:
	- paths (List[Path]): Paths to the files to restore. If None, all files will be restored.
	- config_file (Path): Path to the config file.
	- verbose (bool): If True, display more detailed output.
	- yes (bool): If True, automatically answer "yes" to any prompts.

	Returns:
	- None
	"""
	repo, repo_trans, local_trans = load_config(config_file)
	now = datetime.datetime.now(tz=datetime.timezone.utc)


def get_permissions(data, base, link):
	 """
	Recursive function to get file permissions.

	Args:
	- data (dict): A dictionary of file permissions.
	- base (Path): The base directory.
	- link (str): The path of the file relative to the base directory.

	Returns:
	- None
	"""
	src_path = base / link

	data[link] = {'mode': src_path.stat().st_mode}
	if src_path.is_dir():
		data[link]['contents'] = {}
		for p in src_path.iterdir():
			get_permissions(data[link]['contents'], p.parent, p.name)


def save_permissions(repo):
	"""
	Save file permissions in data file.

	Args:
	- repo (str): Path to the repository.

	Returns:
	- None
	"""
	with open(link_data_file(repo), 'r') as fh:
		links = json.load(fh)

		data = {}
		for link in links:
			get_permissions(data, Path(repo), link)

	with open(perms_data_file(repo), 'w') as fh:
		json.dump(data, fh, indent=2)


def apply_permissions(data, base, repo_path, verbose):
	"""
	Recursive function to apply file permissions.

	Args:
	- data (dict): A dictionary of file permissions.
	- base (Path): The base directory.
	- repo_path (str): The path of the repository.
	- verbose (bool): If True, display more detailed output.

	Returns:
	- None
	"""
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
		Reapply file permissions from remote.

		Args:
		- config_file (Path): Path to the config file.
		- verbose (bool): If True, display more detailed output.

		Returns:
		- None
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
		Transfer small text files to another machine.

		Args:
		key_file (Path): The path to the key file to be transferred.
		file (List[Path]): A list of file paths to be transferred.
		server_url (str): The URL of the transfer server.
		encryption_password (str): The encryption password for the transfer.
		yes (bool): Whether to skip confirmation prompts.

		Returns:
		None
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
		Complete a transfer of files on another machine.

		Args:
		server_url (str): The URL of the transfer server.
		encryption_password (str): The encryption password for the transfer.
		storage_key (str): The storage key for the transfer.

		Returns:
		None
		"""
		client = ApiClient(server_url)
		client.download(encryption_password, storage_key)


@app.command()
def server(
		host: str = typer.Argument('127.0.0.1', envvar="HOST"),
		port: int = typer.Argument(8000, envvar="PORT")
	):
		"""
		Run a transfer server.

		Args:
		host (str): The host IP for the server.
		port (int): The port number for the server.

		Returns:
		None
		"""
		config = uvicorn.Config('nsync.server:app', host=host, port=port, log_level="info", reload=True)
		server = uvicorn.Server(config)
		server.run()



if __name__ == "__main__":
	app()
