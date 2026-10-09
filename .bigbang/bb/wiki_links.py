"""Validate GitHub Wiki navigation, Markdown links, images and anchors without executing prose."""
import re
import urllib.parse
from pathlib import Path

from .docs_check import anchors, outside_code

LINK_START = re.compile(r'\[!\[(?:\\.|[^\]\\])*\]\(|!?\[(?:\\.|[^\]\\])*\]\(')
WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
HTML_LINK = re.compile(r'(?:src|href)=["\']([^"\']+)["\']', re.I)


def _closing_parenthesis(text, start):
    depth, quote, angle, escaped = 1, None, False, False
    for index in range(start + 1, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif angle:
            if char == ">":
                angle = False
        elif char == "<":
            angle = True
        elif char in ("'", '"') and text[index - 1].isspace():
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _destination(text):
    text = text.strip()
    if text.startswith("<") and ">" in text:
        target = text[1:text.index(">")]
    else:
        target = text.split()[0] if text else ""
    return re.sub(r"\\([\\()\[\]])", r"\1", target)


def markdown_targets(text):
    """Read inline links/images and both badge destinations without evaluating prose."""
    targets, cursor = [], 0
    while match := LINK_START.search(text, cursor):
        start = match.end() - 1
        end = _closing_parenthesis(text, start)
        if end is None:
            cursor = match.end()
            continue
        targets.append(_destination(text[start + 1:end]))
        cursor = end + 1
        if match.group().startswith("[![") and text[cursor:cursor + 2] == "](":
            start = cursor + 1
            end = _closing_parenthesis(text, start)
            if end is not None:
                targets.append(_destination(text[start + 1:end]))
                cursor = end + 1
    return targets


def _target(root, source, target, repository):
    parsed = urllib.parse.urlsplit(target)
    if repository and parsed.netloc == 'github.com' and parsed.path.startswith('/' + repository + '/wiki/'):
        parsed = parsed._replace(scheme='', netloc='', path=parsed.path.split('/wiki/', 1)[1])
    elif repository and parsed.netloc == 'raw.githubusercontent.com' and parsed.path.startswith('/wiki/' + repository + '/'):
        parsed = parsed._replace(scheme='', netloc='', path=parsed.path[len('/wiki/' + repository + '/'):])
    if parsed.scheme or parsed.netloc:
        return True  # External URLs are reviewed separately; no unstable network in unit tests.
    name = urllib.parse.unquote(parsed.path)
    path = source if not name else (source.parent / name)
    if not path.is_file() and not Path(name).suffix:
        path = path.with_suffix(".md")
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or not path.is_file():
        return False
    return not parsed.fragment or path.suffix != ".md" or urllib.parse.unquote(parsed.fragment) in anchors(str(path))


def problems(folder, repository=None):
    root = Path(folder)
    found = [f"Wiki sem navegação obrigatória: {name}" for name in ("Home.md", "_Sidebar.md")
             if not (root / name).is_file()]
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            found.append(f"Wiki com link simbólico: {path.name}")
            continue
        lines, closed = outside_code(path.read_text(encoding="utf-8"))
        if not closed:
            found.append(f"{path.name}: bloco de código sem fechamento")
        text = "\n".join(lines)
        targets = markdown_targets(text) + HTML_LINK.findall(text)
        targets += [link.split("|", 1)[-1].strip() for link in WIKILINK.findall(text)]
        for target in targets:
            if not _target(root, path, target, repository):
                found.append(f"{path.name}: link ou imagem inválido: {target}")
    return found
