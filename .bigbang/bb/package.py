"""The framework package of each Big Bang release (spec 5.2, 5.7): bigbang-vX.Y.Z.tar.gz with the .bigbang/ folder,
its .sha256, and the migration notes between versions (MIGRACAO.md).

The tarball is reproducible: sorted entries, fixed date, owner and modes, gzip without timestamp. Building it twice
from the same content gives the same SHA-256."""
import gzip
import hashlib
import io
import os
import re
import tarfile

from . import checksums
from .errors import EXIT_INVALID_STATE, EXIT_USAGE, BbError
from .paths import framework_dir, framework_version, read_text, to_posix

FIXED_MTIME = 1767225600  # 2026-01-01T00:00:00Z
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SECTION = re.compile(r"^## \[(\d+\.\d+\.\d+)\][^\n]*$", re.M)
MANUAL_HEADING = "### O que o projeto precisa fazer"


def package_name(version):
    return f"bigbang-v{version}.tar.gz"


def _files(root):
    """Framework files that ship in the package (what CHECKSUMS lists, plus CHECKSUMS itself)."""
    paths = [relative for relative, _ in checksums.framework_files(root)] + [checksums.CHECKSUMS_FILE]
    return sorted(paths)


def build(root, out_dir):
    """Write the tarball and its .sha256 to out_dir; returns (tarball path, sha256)."""
    problems = checksums.problems(root)
    if problems:
        raise BbError("o framework não confere com o CHECKSUMS; nada foi empacotado:\n" +
                      "\n".join(f"  - {p}" for p in problems), EXIT_INVALID_STATE)
    version = framework_version(root)
    os.makedirs(out_dir, exist_ok=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for relative in _files(root):
            path = os.path.join(framework_dir(root), *relative.split("/"))
            with open(path, "rb") as handle:
                data = handle.read()
            info = tarfile.TarInfo(f".bigbang/{relative}")
            info.size, info.mtime, info.uid, info.gid, info.uname, info.gname = len(data), FIXED_MTIME, 0, 0, "", ""
            info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
            tar.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0) as gz:
        gz.write(buffer.getvalue())
    name = package_name(version)
    target = os.path.join(out_dir, name)
    with open(target, "wb") as handle:
        handle.write(compressed.getvalue())
    digest = hashlib.sha256(compressed.getvalue()).hexdigest()
    with open(target + ".sha256", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{digest}  {name}\n")
    return target, digest


def _key(version):
    match = SEMVER.match(version)
    if not match:
        raise BbError(f"versão inválida: {version}", EXIT_USAGE)
    return tuple(int(part) for part in match.groups())


def migration_sections(text):
    """{version: section text} of MIGRACAO.md."""
    marks = list(SECTION.finditer(text))
    return {m.group(1): text[m.start():(nxt.start() if nxt else len(text))].strip()
            for m, nxt in zip(marks, marks[1:] + [None])}


def migration_between(text, current, target):
    """Sections of the versions after `current` up to `target`, oldest first."""
    low, high = _key(current), _key(target)
    sections = migration_sections(text)
    return [sections[v] for v in sorted(sections, key=_key) if low < _key(v) <= high]


def manual_steps(section):
    """The text under "O que o projeto precisa fazer", or "" when it says the project does nothing."""
    if MANUAL_HEADING not in section:
        return ""
    text = section.split(MANUAL_HEADING, 1)[1].split("\n### ", 1)[0].strip()
    return "" if text.rstrip(".").lower() in ("nada", "") else text


def release_notes(root, version):
    path = os.path.join(framework_dir(root), "MIGRACAO.md")
    section = migration_sections(read_text(path)).get(version)
    if not section:
        raise BbError(f"MIGRACAO.md não tem a seção [{version}]", EXIT_INVALID_STATE)
    return section


def tarball_members_ok(tar):
    """Refuse absolute paths, '..' and links: the package only has regular files under .bigbang/."""
    for member in tar.getmembers():
        name = to_posix(member.name)
        if not name.startswith(".bigbang/") or ".." in name.split("/") or not (member.isfile() or member.isdir()):
            raise BbError(f"pacote recusado: entrada suspeita {member.name}", EXIT_INVALID_STATE)
