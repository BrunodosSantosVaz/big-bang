"""Isolate confirmed owners in git worktrees; session receipts stay in Git metadata, never in tracked files."""
import json
import os
import subprocess

from . import github, ownership, pipeline
from .errors import EXIT_EXTERNAL_COMMAND, EXIT_INVALID_STATE, BbError


def git(root, *args):
    result = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise BbError("git falhou: " + result.stderr.strip(), EXIT_EXTERNAL_COMMAND)
    return result.stdout.strip()


def isolate(root, config, receipt, folder=None):
    repo, number = config["projeto"]["repositorio"], receipt["issue"]
    branches = []
    for kind in ("feature", "teste", "docs", "bugfix", "hotfix"):
        refs = ownership.listing(f"repos/{repo}/git/matching-refs/heads/{kind}/{number}-")
        branches.extend(ref["ref"][len("refs/heads/"):] for ref in refs)
    if len(branches) != 1 or pipeline.branch_issue(branches[0])[1] != number:
        raise BbError(f"#{number}: precisa de exatamente uma branch da tarefa criada pela esteira", EXIT_INVALID_STATE)
    folder = os.path.abspath(folder or os.path.join(os.path.dirname(root),
                                                  os.path.basename(root) + "-" + receipt["name"]))
    if os.path.exists(folder):
        raise BbError(f"pasta de trabalho já existe: {folder}", EXIT_INVALID_STATE)
    git(root, "fetch", "origin", "--prune")
    git(root, "worktree", "add", folder, branches[0])
    receipt_path = git(folder, "rev-parse", "--git-path", "bb-posse.json")
    with open(receipt_path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle)
    return folder


def receipt(root):
    path = git(root, "rev-parse", "--git-path", "bb-posse.json")
    if not os.path.isabs(path):
        path = os.path.join(root, path)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
