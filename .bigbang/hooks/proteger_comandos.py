"""Inspect ordinary Git/GitHub command forms without executing them. Not a general shell interpreter."""
import os
import re
import shlex
import subprocess
import sys

from _common import run

DECISIONS = {"refinamento-aprovado", "prototipo-aprovado", "testes-aprovados", "teste-alterado-aprovado",
             "homologado", "reprovado", "dono:revisao-ia", "pr-aprovado"}
PROTECTED = re.compile(r"^(?:refs/heads/)?(?:main|develop|epico/.*)$")
CONTROL = {";", "&&", "||", "|", "&", "\n"}


def branch(cwd):
    result = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=cwd,
                            capture_output=True, text=True, timeout=5, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def git_check(args, cwd):
    # Resolve common global options; custom aliases/configs can change execution semantics.
    while args and args[0].startswith("-"):
        option = args.pop(0)
        if option == "-C" and args:
            cwd = os.path.abspath(os.path.join(cwd, args.pop(0)))
        elif option in ("--no-pager", "--literal-pathspecs"):
            continue
        else:
            return "ask", "Opção global do Git exige conferência do dono. Use comando explícito."
    if not args:
        return None
    command, rest = args[0], args[1:]
    if command == "reset" and any(a == "--hard" or a.startswith("--hard=") for a in rest):
        return "deny", "git reset --hard é proibido pelo Big Bang."
    if command == "tag" and any(a in ("-d", "--delete", "-f", "--force") or
                                (a.startswith("-") and not a.startswith("--") and ("d" in a or "f" in a))
                                for a in rest):
        return "deny", "Apagar ou mover tag é proibido pelo Big Bang."
    if command == "update-ref" and any(a.startswith("refs/tags/") for a in rest):
        return "deny", "Apagar ou mover tag via update-ref é proibido."
    if command != "push":
        if command not in {"add", "branch", "checkout", "cherry-pick", "clean", "commit", "config", "diff", "fetch",
                           "for-each-ref", "init", "log", "merge", "merge-base", "pull", "rebase", "remote", "reset",
                           "restore", "rev-parse", "show", "show-ref", "stash", "status", "switch", "symbolic-ref",
                           "tag", "update-ref", "worktree"}:
            return "ask", "Comando ou alias Git não reconhecido; confira com o dono."
        return None
    if any(a.startswith(("--force", "+")) or a in ("-f", "--all", "--mirror") or
           (a.startswith("-") and not a.startswith("--") and "f" in a) for a in rest):
        return "deny", "Push forçado ou de múltiplas branches protegidas é proibido."
    if any(a in ("--delete", "-d") or a.startswith(":") for a in rest):
        for arg in rest:
            if arg.startswith(":refs/tags/") or arg.startswith("refs/tags/") or PROTECTED.fullmatch(arg.lstrip(":")):
                return "deny", "Tags e branches protegidas não podem ser apagadas."
        return "ask", "Exclusão remota exige conferir o alvo; tags e branches protegidas não podem ser apagadas."
    # Skip flags and their arguments, leaving remote plus refspecs.
    values = []
    skip = False
    for arg in rest:
        if skip:
            skip = False
            continue
        if arg in ("-o", "--push-option", "--repo"):
            skip = True
        elif not arg.startswith("-"):
            values.append(arg)
    refspecs = values[1:]  # With no explicit refspec, inspect the current branch conservatively.
    if not refspecs:
        current = branch(cwd)
        if not current or PROTECTED.fullmatch(current):
            return "deny", "Push sem destino explícito em branch protegida ou desconhecida; use branch própria."
        return "ask", "Push sem refspec depende da configuração remota; informe origem e destino explicitamente."
    for refspec in refspecs:
        destination = refspec.rsplit(":", 1)[-1]
        if destination == "HEAD":
            destination = branch(cwd)
            if not destination:
                return "ask", "HEAD não pode ser resolvido; use destino explícito."
        if PROTECTED.fullmatch(destination):
            return "deny", "Push direto para main, develop ou epico/* é proibido; abra PR."
        if any(c in refspec for c in "$`*{}"):
            return "ask", "Refspec dinâmico não pode ser conferido; use destino explícito."
    return None


def gh_check(args):
    text = " ".join(args)
    if args[:2] == ["release", "delete"] and "--cleanup-tag" in args:
        return "deny", "Apagar tag junto com a release é proibido."
    if len(args) >= 2 and args[0] in ("issue", "pr") and args[1] == "edit":
        for index, arg in enumerate(args):
            if arg == "--add-label" or arg.startswith("--add-label="):
                value = arg.partition("=")[2] if "=" in arg else (args[index + 1] if index + 1 < len(args) else "")
                if DECISIONS.intersection(value.split(",")):
                    return "deny", "Label de decisão só via bb decisao ou bb revisao aprovar."
                if not value or any(c in value for c in "$`"):
                    return "ask", "Labels dinâmicas exigem conferência do dono."
    if args and args[0] == "api":
        mutation = any(a in ("POST", "PATCH", "PUT", "DELETE") or a in (
            "--method=POST", "--method=PATCH", "--method=PUT", "--method=DELETE",
            "-XPOST", "-XPATCH", "-XPUT", "-XDELETE") for a in args) or any(
            a in ("-f", "-F", "--field", "--raw-field", "--input") or a.startswith(("--field=", "--raw-field="))
            for a in args)
        labels = any("/labels" in a or a.startswith("labels") or "addLabelsToLabelable" in a for a in args)
        if mutation and labels:
            if any(label in text for label in DECISIONS):
                return "deny", "Label de decisão só via bb decisao ou bb revisao aprovar."
            return "ask", "Mutação de labels pela API exige conferência; não use IDs ou payload para contornar decisões."
        if mutation and any("git/refs/tags" in a or "git/refs/heads/main" in a or
                            "git/refs/heads/develop" in a or "git/refs/heads/epico" in a for a in args):
            return "deny", "Não mova/apague tags ou branches protegidas via API."
    return None


def inspect(event):
    if event.get("tool_name") not in {"Bash", "PowerShell"}:
        return None
    command = event["tool_input"].get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("comando ausente")
    # Shell expansions, scripts and PowerShell are not fully interpreted; unresolved Git/GitHub forms ask.
    try:
        lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return "ask", "Comando não pôde ser analisado; confira com o dono."
    segments, segment = [], []
    for token in tokens:
        if token in CONTROL or token in ("(", ")"):
            if segment:
                segments.append(segment)
                segment = []
        else:
            segment.append(token)
    if segment:
        segments.append(segment)
    pending = None
    for args in segments:
        # Wrappers never exempt another segment, even when a bb helper is present.
        while args and ("=" in args[0] or args[0] in ("env", "command", "exec", "&")):
            args = args[1:]
        if not args:
            continue
        executable = args[0].replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
        result = git_check(args[1:], event["cwd"]) if executable == "git" else (
            gh_check(args[1:]) if executable == "gh" else None)
        if result and result[0] == "deny":
            return result
        pending = result or pending
        if executable in {"bash", "sh", "zsh", "pwsh", "powershell"} and any(
                option in args for option in ("-c", "-lc", "-Command")):
            nested = args[-1]
            if "git" in nested or "gh" in nested:
                pending = "ask", "Comando Git/GitHub dentro de shell exige conferência; use chamada explícita."
    if not pending and re.search(r"(?:\bgit\b|\bgh\b)", command) and any(c in command for c in "$`"):
        return "ask", "Comando Git/GitHub usa expansão; confira a operação com o dono."
    return pending


if __name__ == "__main__":
    sys.exit(run(inspect))
