"""`bb init`: Foundation step F0 (spec 10/F0 and 14.6)."""
import datetime
import json
import os
import re
import unicodedata

from . import generator, github
from . import config as config_module
from .errors import EXIT_INVALID_CONFIG, EXIT_INVALID_STATE, EXIT_USAGE, BbError
from .paths import config_path, framework_dir, framework_version, read_text, write_text
from .render import substitute

FOUNDATION_LABEL = ("fundacao", "1D76DB", "Etapa da Fundação (F0 a F5)")
F0_TITLE = "F0 · Ligar ao GitHub e escolher a visibilidade"
F0_BODY = """Etapa F0 da Fundação (`.bigbang/processo/02-fundacao.md`).

## Decisão registrada
- Visibilidade: {visibilidade}
- Licença do sistema: {licenca}

## Feito por `bb init`
- `bigbang.toml` criado a partir do modelo
- README e LICENSE do framework movidos para `.bigbang/`
- README do sistema criado{licenca_criada}

## Link do PR
<!-- preenchido pela IA ao abrir o PR fundacao/... -->
"""
LICENSE_HOLDERS = ("[fullname]", "[name of copyright owner]", "[owner]")
LICENSE_YEARS = ("[year]", "[yyyy]")


def hook_python_problem():
    """The Claude Code hooks run `python` (exec form, no shell). None when it is Python 3.11+, else how to fix it.

    On Ubuntu/Debian only `python3` exists by default; a hook that cannot start blocks nothing."""
    import shutil
    import subprocess
    executable = shutil.which("python")
    if not executable:
        return ("o comando `python` não existe: os hooks do Claude Code não vão rodar. No Ubuntu/Debian: "
                "sudo apt install python-is-python3; no Windows: instale o Python 3.11+ marcando 'Add to PATH'")
    try:
        version = subprocess.run([executable, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
                                 capture_output=True, text=True, timeout=10, check=True).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return "o comando `python` não respondeu: confira a instalação do Python 3.11+"
    if (int(version[0]), int(version[1])) < (3, 11):
        return f"`python` é a versão {'.'.join(version)}; os hooks precisam de Python 3.11+ como `python`"
    return None


def slugify(text):
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def set_value(text, section, key, value):
    """Replace `key = ...` inside `[section]` keeping the trailing comment (the example's comments are docs)."""
    header = re.search(rf"^\[{re.escape(section)}\]\s*(#.*)?$", text, re.M)
    if not header:
        raise BbError(f"modelo do bigbang.toml sem a seção [{section}]", EXIT_INVALID_STATE)
    following = re.search(r"^\[", text[header.end():], re.M)
    end = header.end() + following.start() if following else len(text)
    pattern = re.compile(rf'^({re.escape(key)}\s*=\s*)("(?:[^"\\]|\\.)*"|[^#\n]*?)([ \t]*(?:#.*)?)$', re.M)
    def keep_comment_column(match):
        new = match.group(1) + json.dumps(value, ensure_ascii=False)
        comment = match.group(3).strip()
        if not comment:
            return new
        column = len(match.group(1) + match.group(2)) + len(match.group(3)) - len(match.group(3).lstrip())
        return new + " " * max(1, column - len(new)) + comment

    body, count = pattern.subn(keep_comment_column, text[header.end():end], count=1)
    if count != 1:
        raise BbError(f"modelo do bigbang.toml sem a chave {section}.{key}", EXIT_INVALID_STATE)
    return text[:header.end()] + body + text[end:]


def _repository_from_git(root):
    path = os.path.join(root, ".git", "config")
    if not os.path.exists(path):
        return None
    match = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*\S*github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?\s*$',
                      read_text(path), re.M)
    return match.group(1) if match else None


def resolve_options(root, nome, slug=None, dono=None, repositorio=None, visibilidade="privado", licenca=""):
    if not nome or not nome.strip():
        raise BbError("informe o nome do sistema (--nome)", EXIT_USAGE)
    repositorio = repositorio or _repository_from_git(root)
    dono = dono or (repositorio.split("/")[0] if repositorio else github.run("api", "user", "--jq", ".login"))
    slug = slug or slugify(nome)
    repositorio = repositorio or f"{dono}/{slug}"
    if visibilidade == "publico" and not licenca:
        raise BbError("repositório público precisa de licença (--licenca, identificador SPDX como MIT)", EXIT_USAGE)
    return {"nome": nome.strip(), "slug": slug, "dono": dono, "repositorio": repositorio,
            "visibilidade": visibilidade, "licenca": licenca if visibilidade == "publico" else ""}


def build_config_text(root, options):
    text = read_text(os.path.join(framework_dir(root), "modelos", "bigbang.toml.exemplo"))
    text = set_value(text, "bigbang", "versao", framework_version(root))
    for key in ("nome", "slug", "dono", "repositorio", "visibilidade", "licenca"):
        text = set_value(text, "projeto", key, options[key])
    text = set_value(text, "paineis", "owner", options["dono"])
    text = set_value(text, "deploy", "imagem", f"ghcr.io/{options['dono'].lower()}/{options['slug']}")
    errors = config_module.validate(config_module.parse(text), framework_version(root))
    if errors:
        raise BbError("bigbang.toml gerado ficou inválido:\n" + "\n".join(f"  - {e}" for e in errors),
                      EXIT_INVALID_CONFIG)
    return text


def plan_steps(options, with_github):
    steps = []
    if with_github:
        steps += [f"criar (ou atualizar) a label {FOUNDATION_LABEL[0]} em {options['repositorio']}",
                  f"abrir a issue \"{F0_TITLE}\" (se ainda não existir)"]
    steps += ["criar bigbang.toml a partir de .bigbang/modelos/bigbang.toml.exemplo",
              "mover README.md e LICENSE do framework para .bigbang/",
              "criar o README.md do sistema",
              "criar CODE_OF_CONDUCT.md, CONTRIBUTING.md e SECURITY.md do sistema (DOC-16)"]
    if options["visibilidade"] == "publico":
        steps.append(f"criar o LICENSE do sistema ({options['licenca']})")
    steps.append("rodar bb gerar (o AGENTS.md passa para o modo do projeto fundado)")
    return steps


def run(root, options, with_github=True, today=None):
    """Execute F0. Returns the issue URL or number (None without GitHub)."""
    if os.path.exists(config_path(root)):
        raise BbError("bigbang.toml já existe: este projeto já passou pelo bb init", EXIT_INVALID_STATE)
    config_text = build_config_text(root, options)
    license_text = _license_text(options, today or datetime.date.today()) if options["licenca"] else None
    issue = _github_steps(options) if with_github else None

    for name in ("README.md", "LICENSE"):
        source, target = os.path.join(root, name), os.path.join(framework_dir(root), name)
        if os.path.exists(source) and not os.path.exists(target):
            os.replace(source, target)
    readme = read_text(os.path.join(framework_dir(root), "modelos", "README-sistema.md"))
    write_text(os.path.join(root, "README.md"),
               substitute(readme, {"projeto": options}, ".bigbang/modelos/README-sistema.md"))
    for name in ("CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "SECURITY.md"):  # the framework's own are replaced
        source = f".bigbang/modelos/comunidade/{name}"
        write_text(os.path.join(root, name), substitute(read_text(os.path.join(framework_dir(root), "modelos",
                                                                               "comunidade", name)),
                                                        {"projeto": options}, source))
    if license_text:
        write_text(os.path.join(root, "LICENSE"), license_text)
    write_text(config_path(root), config_text)
    generator.apply(generator.build_plan(root), root)
    return issue


def _license_text(options, today):
    body = github.run("api", f"licenses/{options['licenca'].lower()}", "--jq", ".body")
    holder = github.run("api", f"users/{options['dono']}", "--jq", ".name // .login") or options["dono"]
    for marker in LICENSE_YEARS:
        body = body.replace(marker, str(today.year))
    for marker in LICENSE_HOLDERS:
        body = body.replace(marker, holder)
    return body.rstrip("\n") + "\n"


def _github_steps(options):
    repository = options["repositorio"]
    name, color, description = FOUNDATION_LABEL
    github.run("label", "create", name, "--color", color, "--description", description, "--force", "-R", repository)
    existing = json.loads(github.run("issue", "list", "-R", repository, "--label", name, "--state", "all",
                                     "--json", "number,title", "--limit", "100") or "[]")
    for issue in existing:
        if issue["title"].startswith("F0 "):
            return issue["number"]
    body = F0_BODY.format(visibilidade=options["visibilidade"], licenca=options["licenca"] or "nenhuma (privado)",
                          licenca_criada=f"\n- LICENSE do sistema ({options['licenca']})" if options["licenca"] else "")
    return github.run("issue", "create", "-R", repository, "--label", name, "--title", F0_TITLE, "--body", body)
