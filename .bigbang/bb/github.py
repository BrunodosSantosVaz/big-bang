"""Thin wrapper over the GitHub CLI. BB_GH replaces the command (tests use a fake gh)."""
import os
import shlex
import subprocess

from .errors import EXIT_EXTERNAL_COMMAND, BbError


def gh_command():
    return shlex.split(os.environ.get("BB_GH", "gh"), posix=os.name != "nt")


def run(*args):
    """Run gh and return its stdout (stripped); any failure becomes a BbError with gh's message."""
    command = gh_command() + list(args)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    except FileNotFoundError as exc:
        raise BbError("GitHub CLI (gh) não encontrado; instale e rode gh auth login", EXIT_EXTERNAL_COMMAND) from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        raise BbError(f"gh {' '.join(args[:2])} falhou: {message}", EXIT_EXTERNAL_COMMAND)
    return completed.stdout.strip()
