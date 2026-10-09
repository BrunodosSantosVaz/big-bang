"""Validate GitHub Wiki navigation, Markdown links, images and anchors without executing prose."""
import re
import urllib.parse
from pathlib import Path

from .docs_check import anchors, outside_code

LINK = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^\"]*")?\)')
WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
HTML_LINK = re.compile(r'(?:src|href)=["\']([^"\']+)["\']', re.I)


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
        targets = LINK.findall(text) + HTML_LINK.findall(text)
        targets += [link.split("|", 1)[-1].strip() for link in WIKILINK.findall(text)]
        for target in targets:
            if not _target(root, path, target, repository):
                found.append(f"{path.name}: link ou imagem inválido: {target}")
    return found
