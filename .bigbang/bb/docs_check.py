"""Markdown sanity and relative links (DOC-14). External links are not fetched: network makes the CI flaky (TST-04)."""
import os
import re
import urllib.parse

from .paths import read_text, to_posix

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SKIPPED_FOLDERS = (".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".bigbang")


def outside_code(text):
    """Lines outside fenced code blocks (inline code removed), and whether every fence was closed."""
    lines, open_fence = [], None
    for line in text.splitlines():
        fence = FENCE.match(line)
        if fence:
            mark = fence.group(1)
            if open_fence is None:
                open_fence = mark
                continue
            if mark[0] == open_fence[0] and len(mark) >= len(open_fence):
                open_fence = None
                continue
        if open_fence is None:
            lines.append(re.sub(r"`[^`]*`", "", line))
    return lines, open_fence is None


def anchor(title):
    """GitHub-style heading anchor."""
    title = re.sub(r"`|\*\*|\*|_", "", title).strip().lower()
    title = re.sub(r"[^\w\- ]", "", title)
    return title.replace(" ", "-")


def anchors(path):
    lines, _ = outside_code(read_text(path))
    seen, result = {}, set()
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            base = anchor(heading.group(2))
            count = seen.get(base, 0)
            result.add(base if count == 0 else f"{base}-{count}")
            seen[base] = count + 1
    return result


def broken_links(path):
    lines, _ = outside_code(read_text(path))
    broken = []
    for line in lines:
        for target in LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue  # external (https:, mailto:)
            file_part, _, fragment = target.partition("#")
            destination = path if not file_part else os.path.normpath(
                os.path.join(os.path.dirname(path), urllib.parse.unquote(file_part)))
            if not os.path.exists(destination):
                broken.append(target)
            elif fragment and destination.endswith(".md") and fragment not in anchors(destination):
                broken.append(target)
    return broken


def markdown_files(root):
    for current, folders, names in os.walk(root):
        folders[:] = sorted(f for f in folders if f not in SKIPPED_FOLDERS)
        for name in sorted(names):
            if name.endswith(".md"):
                yield os.path.join(current, name)


def problems(root):
    """Problems of the project's own Markdown (the framework layer is checked in the Big Bang repository)."""
    result = []
    for path in markdown_files(root):
        relative = to_posix(os.path.relpath(path, root))
        _, closed = outside_code(read_text(path))
        if not closed:
            result.append(f"{relative}: bloco de código aberto sem fechamento")
        result += [f"{relative}: link quebrado: {target}" for target in broken_links(path)]
    return result
