"""Acceptance tests as a contract (spec 11.7, TST-02): releasing a task's pending marks, the lock on tests/aceite/
and the marks left pending for tasks already merged or closed."""
import os
import re

from .paths import read_text, to_posix, write_text
from .pipeline import _acceptance_changes, _released, only_own_marks_released

ACCEPTANCE_DIR = os.path.join("tests", "aceite")
ISSUE_MARK = re.compile(r"#(\d+)\b")


def _acceptance_files(root):
    folder = os.path.join(root, ACCEPTANCE_DIR)
    for current, folders, names in os.walk(folder):
        folders[:] = sorted(f for f in folders if f != "__pycache__")
        for name in sorted(names):
            path = os.path.join(current, name)
            try:
                yield path, read_text(path)
            except UnicodeDecodeError:
                continue


def release_marks(root, issue, marker):
    """Remove the pending marks that cite `#issue` (a mark-only line is deleted; an inline mark such as
    `test.failing(` becomes `test(`). Returns [(relative path, line number)] of what changed."""
    changed = []
    for path, text in _acceptance_files(root):
        out, touched = [], False
        for number, line in enumerate(text.splitlines(keepends=True), start=1):
            if marker in line and re.search(rf"#{issue}\b", line):
                touched = True
                changed.append((to_posix(os.path.relpath(path, root)), number))
                if line.lstrip().startswith("@"):
                    continue  # a decorator mark (@unittest.expectedFailure, @pytest.mark.xfail(...)): drop the line
                out.append(_released(line.rstrip("\n"), marker, issue) + ("\n" if line.endswith("\n") else ""))
                continue
            out.append(line)
        if touched:
            write_text(path, "".join(out))
    return changed


def lock_problems(diff, kind, issue, marker, change_approved):
    """Why a PR breaks the lock on tests/aceite/ (empty = allowed).

    teste/bugfix/hotfix PRs may add tests, never change or delete existing lines; feature/docs PRs may only release
    their own marks. The owner's `teste-alterado-aprovado` allows any change."""
    changes = _acceptance_changes(diff)
    if not changes or change_approved:
        return []
    if kind in ("teste", "bugfix", "hotfix"):
        changed = sorted(path for path, (removed, _) in changes.items() if removed)
        return [f"{path}: linha existente alterada ou apagada em tests/aceite/ (precisa de teste-alterado-aprovado)"
                for path in changed]
    if issue is not None and only_own_marks_released(diff, issue, marker):
        return []
    return [f"{path}: um PR de {kind or 'tarefa'} só pode retirar as marcas de pendente da própria issue "
            "(bb aceite liberar); outra mudança precisa de teste-alterado-aprovado" for path in sorted(changes)]


def pending_marks(root, marker):
    """[(issue, 'path:line')] of every pending mark in tests/aceite/."""
    found = []
    for path, text in _acceptance_files(root):
        for number, line in enumerate(text.splitlines(), start=1):
            if marker in line:
                for issue in ISSUE_MARK.findall(line):
                    found.append((int(issue), f"{to_posix(os.path.relpath(path, root))}:{number}"))
    return found
