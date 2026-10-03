"""Integrity of the framework layer: .bigbang/CHECKSUMS lists the sha256 of every framework file (ADR-0007).

Text is hashed with CRLF normalized to LF, so a Windows checkout (core.autocrlf) verifies the same as Linux.
"""
import hashlib
import os

from .paths import framework_dir, to_posix

CHECKSUMS_FILE = "CHECKSUMS"
IGNORED_NAMES = ("__pycache__", ".DS_Store")
# Moved into .bigbang/ by `bb init` (F0); they are the framework's own README and license, not in the package.
ADDED_BY_INIT = ("README.md", "LICENSE")


def file_hash(path):
    with open(path, "rb") as handle:
        data = handle.read()
    try:
        data = data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        pass  # binary: hash the bytes as they are
    return hashlib.sha256(data).hexdigest()


def framework_files(root):
    base = framework_dir(root)
    for current, subfolders, names in os.walk(base):
        subfolders[:] = sorted(s for s in subfolders if s not in IGNORED_NAMES)
        for name in sorted(names):
            path = os.path.join(current, name)
            relative = to_posix(os.path.relpath(path, base))
            if name in IGNORED_NAMES or name.endswith(".pyc") or relative == CHECKSUMS_FILE:
                continue
            if relative in ADDED_BY_INIT:
                continue
            yield relative, path


def compute(root):
    return "".join(f"{file_hash(path)}  {relative}\n" for relative, path in framework_files(root))


def write(root):
    content = compute(root)
    with open(os.path.join(framework_dir(root), CHECKSUMS_FILE), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return content.count("\n")


def _parse(text):
    entries = {}
    for line in text.splitlines():
        if line.strip():
            digest, _, relative = line.partition("  ")
            entries[relative] = digest
    return entries


def problems(root):
    path = os.path.join(framework_dir(root), CHECKSUMS_FILE)
    if not os.path.exists(path):
        return [".bigbang/CHECKSUMS não existe"]
    with open(path, encoding="utf-8") as handle:
        recorded = _parse(handle.read())
    actual = _parse(compute(root))
    result = []
    for relative in sorted(set(recorded) | set(actual)):
        if relative not in actual:
            result.append(f".bigbang/{relative}: arquivo do framework ausente")
        elif relative not in recorded:
            result.append(f".bigbang/{relative}: arquivo que não faz parte do framework")
        elif recorded[relative] != actual[relative]:
            result.append(f".bigbang/{relative}: alterado (o framework não pode ser editado no projeto)")
    return result
