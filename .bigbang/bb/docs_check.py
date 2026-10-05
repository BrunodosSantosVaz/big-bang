"""Markdown sanity and relative links (DOC-14), and the system README (DOC-15). External links are not fetched:
network makes the CI flaky (TST-04)."""
import os
import re
import subprocess
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


# DOC-15: sections every system README has once a version is in production (modelos/README-sistema.md).
README_SECTIONS = ("Estado atual", "Para que serve", "Recursos", "Instalação", "Como usar", "Para desenvolvedores",
                   "Versões e releases", "Segurança", "Limitações", "Licença")
README_LEFTOVERS = (("Em **Fundação**", "ainda diz que o sistema está na Fundação"),
                    ("Sistema em construção", "ainda diz que o sistema está em construção"),
                    ("(a preencher)", "ainda tem seções \"(a preencher)\""))


def has_release(root):
    """True once a production version exists (a vX.Y.Z tag, not a candidate)."""
    try:
        tags = subprocess.run(["git", "-C", root, "tag", "-l", "v*"], capture_output=True, text=True, check=False).stdout
    except OSError:
        return False
    return any(re.fullmatch(r"v\d+\.\d+\.\d+", tag.strip()) for tag in tags.splitlines())


def readme_problems(root):
    """DOC-15: after the first release the README is complete and current (only for founded systems)."""
    if not os.path.exists(os.path.join(root, "bigbang.toml")) or not has_release(root):
        return []
    path = os.path.join(root, "README.md")
    if not os.path.exists(path):
        return ["README.md: não existe (DOC-15)"]
    text = read_text(path)
    lines, _ = outside_code(text)
    headings = [HEADING.match(line).group(2).lower() for line in lines if HEADING.match(line)]
    result = [f"README.md: falta a seção \"{section}\" (DOC-15, modelo em .bigbang/modelos/README-sistema.md)"
              for section in README_SECTIONS if not any(section.lower() in heading for heading in headings)]
    visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    result += [f"README.md: {why} (DOC-15: atualize a cada épico e release)"
               for mark, why in README_LEFTOVERS if mark in visible]
    if "badge.svg" not in text:
        result.append("README.md: sem o selo da CI (DOC-15)")
    return result


def problems(root):
    """Problems of the project's own Markdown (the framework layer is checked in the Big Bang repository)."""
    result = readme_problems(root)
    for path in markdown_files(root):
        relative = to_posix(os.path.relpath(path, root))
        _, closed = outside_code(read_text(path))
        if not closed:
            result.append(f"{relative}: bloco de código aberto sem fechamento")
        result += [f"{relative}: link quebrado: {target}" for target in broken_links(path)]
    return result
