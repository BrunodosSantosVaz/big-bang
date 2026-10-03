"""Template rendering: `{{secao.chave}}` markers and the "generated file" notice (spec 3.3 and 5.1).

Templates have no conditional logic; variation comes from composing folders (sempre + nucleo + perfil + alvo).
"""
import json
import os
import re

from .errors import EXIT_INVALID_STATE, BbError

TEMPLATE_SUFFIX = ".tmpl"
# `${{ github.x }}` (GitHub Actions) is never a Big Bang marker, hence the negative lookbehind.
MARKER = re.compile(r"(?<!\$)\{\{([a-z_]+(?:\.[A-Za-z0-9_-]+)+)\}\}")
NOTICE = "Gerado pelo Big Bang v{version} a partir de {source}. Não edite: personalize em bigbang.toml."

HASH_COMMENT_SUFFIXES = (".yml", ".yaml", ".toml", ".sh", ".py", ".txt", ".cfg", ".ini")
HASH_COMMENT_NAMES = ("Dockerfile", ".gitignore", ".dockerignore", "CODEOWNERS")
NO_COMMENT_SUFFIXES = (".json",)  # JSON has no comments; integrity comes from regeneration (ADR-0007)


def format_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def substitute(text, context, source):
    """Replace every marker with its value; unknown markers are an error naming the template."""
    missing = []

    def replace(match):
        node = context
        for part in match.group(1).split("."):
            if not isinstance(node, dict) or part not in node:
                missing.append(match.group(1))
                return match.group(0)
            node = node[part]
        return format_value(node)

    result = MARKER.sub(replace, text)
    if missing:
        raise BbError(f"{source}: marcador sem valor no bigbang.toml: {', '.join(sorted(set(missing)))}",
                      EXIT_INVALID_STATE)
    return result


def notice_text(version, source):
    return NOTICE.format(version=version, source=source)


def add_notice(content, destination, version, source):
    """Insert the notice as a comment in the language of the destination file."""
    name = os.path.basename(destination)
    text = notice_text(version, source)
    if name.endswith(".md"):
        return _after_header(content, f"<!-- {text} -->\n", frontmatter=True)
    if name.endswith(HASH_COMMENT_SUFFIXES) or name in HASH_COMMENT_NAMES or content.startswith("#!"):
        return _after_header(content, f"# {text}\n", frontmatter=False)
    if name.endswith(NO_COMMENT_SUFFIXES):
        return content
    raise BbError(f"{source}: tipo de arquivo sem formato de comentário conhecido para o aviso de gerado",
                  EXIT_INVALID_STATE)


def _after_header(content, line, frontmatter):
    """Put the notice first, except after a shebang or a YAML frontmatter that must stay on line 1."""
    if content.startswith("#!"):
        first, _, rest = content.partition("\n")
        return f"{first}\n{line}{rest}"
    if frontmatter and content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            cut = end + len("\n---\n")
            return content[:cut] + line + content[cut:]
    return line + content


def has_notice(content):
    head = "\n".join(content.splitlines()[:6])
    return "Gerado pelo Big Bang v" in head and "Não edite: personalize em bigbang.toml." in head
