"""Guard direct file-tool writes; this is a local aid, not a shell sandbox."""
import os
from pathlib import Path
import re
import sys

from _common import project_root, run

SENSITIVE = {"PRODUTO.md", "STACK.md", "DESIGN.md", "bigbang.toml", "flags.toml",
             ".bigbang-docs.json", ".bigbang-producao.json"}
TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BLOCKS = {
    "AGENTS.md": re.compile(r"<!-- bigbang:inicio v[^ ]+ -->.*?<!-- bigbang:fim -->", re.S),
    "STACK.md": re.compile(r"<!-- bb:config:inicio -->.*?<!-- bb:config:fim -->", re.S),
}


def guarded_path(relative):
    parts = relative.parts
    if parts[:1] == (".bigbang",):
        return ".bigbang/ é imutável no projeto; peça uma nova versão do framework."
    if parts[:2] == ("tests", "aceite"):
        return "tests/aceite/ é protegido; use bb aceite liberar para as marcas da sua tarefa."
    if relative.as_posix() == ".claude/settings.json":
        return "settings.json é gerado; personalize no bigbang.toml e use bb gerar."
    if len(parts) >= 3 and parts[:2] in ((".agents", "skills"), (".claude", "skills"), (".claude", "agents")):
        if parts[2].startswith("bb-"):
            return "Arquivo bb-* gerado; use bb gerar, não edição manual."
    if ".github" in parts[:1] and relative.name.startswith("bb-"):
        return "Arquivo bb-* gerado; use bb gerar, não edição manual."
    return None


def changed_block(event, text, pattern):
    before = pattern.findall(text)
    if not before:
        return False
    if event["tool_name"] == "Write":
        content = event["tool_input"].get("content")
        if not isinstance(content, str):
            raise ValueError("conteúdo ausente")
        return before != pattern.findall(content)
    edits = event["tool_input"].get("edits", [event["tool_input"]])
    for edit in edits:
        old, new = edit.get("old_string"), edit.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str) or not old or old not in text:
            return True  # Cannot prove that this edit preserves the generated block.
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return before != pattern.findall(text)


def inspect(event):
    if event.get("tool_name") not in TOOLS:
        return None
    root = project_root(event)
    name = event["tool_input"].get("file_path") or event["tool_input"].get("notebook_path")
    if not isinstance(name, str) or not name:
        raise ValueError("caminho ausente")
    # Path uses the native host's separators; normalize event spellings before resolving aliases.
    target = Path(name.replace("\\", "/"))
    if not target.is_absolute():
        target = Path(event["cwd"]) / target
    lexical = Path(os.path.abspath(target))
    resolved = target.resolve()
    relatives = []
    for candidate in (lexical, resolved):
        try:
            current = candidate.relative_to(root)
        except ValueError:
            continue
        relatives.append(current)
        reason = guarded_path(current)
        if reason:
            return "deny", reason
    if not relatives:
        return "ask", "Arquivo fora da raiz Big Bang; confirme o escopo com o dono."
    text = resolved.read_text(encoding="utf-8") if resolved.is_file() else ""
    patterns = [BLOCKS[p.as_posix()] for p in relatives if p.as_posix() in BLOCKS]
    if any(changed_block(event, text, pattern) for pattern in patterns):
        return "deny", "Bloco gerado protegido; altere a configuração e rode bb gerar."
    if not patterns and "Gerado pelo Big Bang v" in "\n".join(text.splitlines()[:8]):
        return "deny", "Arquivo gerado protegido; use bb gerar."
    if any(p.as_posix() in SENSITIVE for p in relatives):
        return "ask", "Documento de decisão do dono; confirme a mudança antes de editar."
    return None


if __name__ == "__main__":
    sys.exit(run(inspect))
