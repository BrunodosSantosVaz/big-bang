"""The generated layer (spec 5.1): what `bb gerar` writes and `bb verificar` compares (ADR-0007).

Sources, in composition order (a later layer may replace a file of an earlier one):
  .bigbang/esteira/sempre/arquivos/                 always (also before the Foundation)
  .bigbang/esteira/nucleo/arquivos/                 once the pipeline is installed (F5)
  .bigbang/esteira/perfis/<perfil>/arquivos/        idem
  .bigbang/esteira/perfis/deploy/alvos/<alvo>/arquivos/   idem, deploy profile only
  .bigbang/skills/bb-*/                             always, written to .agents/skills/ and .claude/skills/
plus the marked blocks of AGENTS.md (always) and STACK.md (when it exists).
"""
import difflib
import os
import re
import tomllib

from . import config as config_module
from . import deploy_catalog, pipeline
from .errors import EXIT_INVALID_STATE, BbError
from .paths import framework_dir, framework_version, read_text, to_posix, write_text
from .render import TEMPLATE_SUFFIX, add_notice, has_notice, notice_text, substitute

AGENTS_FILE = "AGENTS.md"
STACK_FILE = "STACK.md"
AGENTS_BLOCK = re.compile(r"<!-- bigbang:inicio v[^ ]+ -->\n.*?<!-- bigbang:fim -->", re.S)
STACK_BLOCK_START = "<!-- bb:config:inicio -->"
STACK_BLOCK_END = "<!-- bb:config:fim -->"
SKILL_TARGETS = (".agents/skills", ".claude/skills")
FRAMEWORK_WORKFLOW_PREFIX = "bb-framework-"
IGNORED_NAMES = ("__pycache__", ".DS_Store")
ALWAYS_SENSITIVE = (".github/**", "tests/aceite/**", ".bigbang-docs.json", ".bigbang-producao.json", "STACK.md", "DESIGN.md", "PRODUTO.md", "bigbang.toml",
                    "flags.toml")


class Plan:
    """Expected content of every generated file, plus the generated files that must no longer exist."""

    def __init__(self, installed):
        self.installed = installed
        self.expected = {}  # relative posix path -> content
        self.sources = {}  # relative posix path -> where it comes from
        self.stale = []

    def add(self, path, content, source):
        self.expected[path] = content
        self.sources[path] = source


def pipeline_installed(root):
    """The pipeline counts as installed once .github/ holds any generated file other than the framework's own CI.

    Only the pipeline layers write into .github/ (the "sempre" layer is forbidden to), so this needs no state file.
    """
    return any(path.startswith(".github/") for path in _generated_candidates(root, installed=False))


def initial_context(root):
    """Values available before bigbang.toml exists: only the [bigbang] section."""
    example = os.path.join(framework_dir(root), "modelos", "bigbang.toml.exemplo")
    with open(example, "rb") as handle:
        origin = tomllib.load(handle)["bigbang"]["origem"]
    return {"bigbang": {"versao": framework_version(root), "origem": origin}}


def dependabot_entries(ecosystems):
    """YAML entries of the stack ecosystems: grouped, monthly, into main (they ship in a maintenance release)."""
    entries = []
    for ecosystem in ecosystems:
        entries.append(f"""  - package-ecosystem: "{ecosystem}"
    directory: "/"
    target-branch: "main"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
    labels: ["dependencies"]
    groups:
      {ecosystem}:
        patterns: ["*"]""")
    return "\n".join(entries)


def with_computed(config, root):
    """Config plus `gerado.*`: values computed in code, so templates stay free of conditional logic."""
    context = dict(config)
    systems = config.get("compilado", {}).get("sistemas", []) if config["entrega"]["perfil"] == "compilado" else []
    context["gerado"] = {"dependabot": dependabot_entries(config["entrega"].get("ecossistemas", [])),
                         "matriz_compilado": pipeline.build_matrix(systems),
                         "modo_trabalho": (
                             "**Modo Flash.** Escreva os testes antes do código e preserve a ordem teste → tarefas. "
                             "Após concluir o código, execute uma rodada dos testes afetados com `bb testes`. "
                             "Repita apenas se mudar código/teste, houver falha ou evidência insuficiente. "
                             "Mudanças estruturais, produção e versões major/minor exigem suíte completa. "
                             "Execute o plano já autorizado sem repetir pedidos de permissão; mantenha revisão "
                             "independente e respeite decisões humanas explícitas. Veja `.bigbang/processo/17-flash.md`."
                             if config_module.get(config, "projeto.modo") == "flash" else
                             "**Modo padrão.** Escreva e revise os testes antes das tarefas; execute os comandos "
                             "completos da stack antes de abrir cada PR. Veja `.bigbang/processo/06-execucao.md`."
                         )}
    context['gerado'].update(env_alvo='          # Perfil compilado: sem credenciais de deploy.', runner_deploy='ubuntu-24.04', preparar_alvo=':')
    if config['entrega']['perfil'] == 'deploy':
        target, artifact = deploy_catalog.resolve(root, config)
        context['gerado']['preparar_alvo'] = 'bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh'
        context['gerado']['env_alvo'] = '\n'.join(
            '          ' + name + ': ${{ ' + kind + '.' + name + ' }}'
            for kind, names in (('vars', target.variables), ('secrets', target.secrets)) for name in names)
        context['gerado']['runner_deploy'] = config_module.get(config, 'deploy.runner')
        context['gerado']['artefato_construir'] = artifact.scripts['construir']
        context['gerado']['artefato_candidata'] = artifact.scripts['candidata']
    return context


def build_plan(root, install_pipeline=False):
    config = config_module.load(root, required=False)
    if install_pipeline and config is None:
        raise BbError("a esteira só pode ser gerada depois do bb init (falta o bigbang.toml)", EXIT_INVALID_STATE)
    installed = config is not None and (install_pipeline or pipeline_installed(root))
    if config is not None and config['entrega']['perfil'] == 'deploy':
        deploy_catalog.resolve(root, config)
    context = with_computed(config, root) if config is not None else initial_context(root)
    version = framework_version(root)
    plan = Plan(installed)

    for layer in _layers(config, installed):
        _add_tree(plan, root, os.path.join(framework_dir(root), *layer.split("/"), "arquivos"), "", context, version)
        if layer == "esteira/sempre" and any(path.startswith(".github/") for path in plan.expected):
            raise BbError(".bigbang/esteira/sempre/ não pode gerar arquivos em .github/ (só a esteira gera)",
                          EXIT_INVALID_STATE)
    _add_skills(plan, root, context, version)
    _add_agents_md(plan, root, context, version, founded=config is not None)
    if config is not None:
        _add_stack_md(plan, root, config, version)
    plan.stale = sorted(set(_generated_candidates(root, installed)) - set(plan.expected))
    return plan


def _layers(config, installed):
    layers = ["esteira/sempre"]
    if installed:
        perfil = config["entrega"]["perfil"]
        layers += ["esteira/nucleo", f"esteira/perfis/{perfil}"]
        if perfil == "deploy":
            artifact = config['deploy'].get('artefato', 'imagem')
            layers.append(f"esteira/perfis/deploy/artefatos/{artifact}")
            layers.append(f"esteira/perfis/deploy/alvos/{config['entrega']['alvo']}")
    return layers


def _walk(folder):
    for current, subfolders, names in os.walk(folder):
        subfolders[:] = sorted(s for s in subfolders if s not in IGNORED_NAMES)
        for name in sorted(names):
            if name not in IGNORED_NAMES:
                yield os.path.join(current, name)


def _add_tree(plan, root, folder, destination_prefix, context, version):
    for path in _walk(folder):
        relative = to_posix(os.path.relpath(path, folder))
        source = to_posix(os.path.relpath(path, root))
        destination = destination_prefix + relative
        content = read_text(path)
        if destination.endswith(TEMPLATE_SUFFIX):
            destination = destination[:-len(TEMPLATE_SUFFIX)]
            content = substitute(content, context, source)
        plan.add(destination, add_notice(content, destination, version, source), source)


def _add_skills(plan, root, context, version):
    skills = os.path.join(framework_dir(root), "skills")
    for name in sorted(os.listdir(skills)):
        folder = os.path.join(skills, name)
        if not os.path.isdir(folder) or name in IGNORED_NAMES:
            continue
        if not name.startswith("bb-"):
            raise BbError(f".bigbang/skills/{name}: skills do framework precisam do prefixo bb-", EXIT_INVALID_STATE)
        for target in SKILL_TARGETS:
            _add_tree(plan, root, folder, f"{target}/{name}/", context, version)


def agents_block(root, context, version, founded):
    source = ".bigbang/AGENTS.base.md" if founded else ".bigbang/AGENTS.inicial.md"
    body = substitute(read_text(os.path.join(root, *source.split("/"))), context, source)
    return (f"<!-- bigbang:inicio v{version} -->\n<!-- {notice_text(version, source)} -->\n\n"
            f"{body.rstrip()}\n\n<!-- bigbang:fim -->")


def _add_agents_md(plan, root, context, version, founded):
    block = agents_block(root, context, version, founded)
    path = os.path.join(root, AGENTS_FILE)
    if os.path.exists(path):
        current = read_text(path)
        found = AGENTS_BLOCK.findall(current)
        if len(found) > 1:
            raise BbError("AGENTS.md tem mais de um bloco do Big Bang; deixe só um", EXIT_INVALID_STATE)
        content = AGENTS_BLOCK.sub(lambda _: block, current) if found else f"{block}\n\n{current}"
    else:
        project = read_text(os.path.join(framework_dir(root), "modelos", "AGENTS.projeto.md"))
        content = f"{block}\n\n{project}"
    plan.add(AGENTS_FILE, content, "bloco do .bigbang/AGENTS.*.md")


def stack_block(config, version):
    entrega, seguranca = config["entrega"], config["seguranca"]
    lines = [STACK_BLOCK_START, f"<!-- {notice_text(version, 'bigbang.toml')} -->", ""]
    alvo = f" · **Alvo:** `{entrega['alvo']}`" if entrega["alvo"] else ""
    lines += [f"**Perfil de entrega:** `{entrega['perfil']}`{alvo}", ""]
    lines += ["**Caminhos do artefato** (mudança aqui exige release):", ""]
    lines += [f"- `{item}`" for item in entrega["caminhos_artefato"]] + [""]
    lines += ["**Zonas sensíveis** (revisão humana):", ""]
    lines += [f"- `{item}`" for item in seguranca["zonas_sensiveis"]]
    lines += ["- Sempre: " + ", ".join(f"`{item}`" for item in ALWAYS_SENSITIVE)
              + " e os arquivos de dependência da stack.", "", STACK_BLOCK_END]
    return "\n".join(lines)


def _add_stack_md(plan, root, config, version):
    if config["projeto"].get("visibilidade") == "publico":
        return  # Public documentation belongs to the separately reviewed Wiki Git history.
    path = os.path.join(root, STACK_FILE)
    if not os.path.exists(path):
        return  # STACK.md is born in F2
    current = read_text(path)
    if current.count(STACK_BLOCK_START) != 1 or current.count(STACK_BLOCK_END) != 1:
        raise BbError(f"STACK.md precisa ter uma vez {STACK_BLOCK_START} e {STACK_BLOCK_END}", EXIT_INVALID_STATE)
    start = current.index(STACK_BLOCK_START)
    end = current.index(STACK_BLOCK_END) + len(STACK_BLOCK_END)
    plan.add(STACK_FILE, current[:start] + stack_block(config, version) + current[end:], "bloco do bigbang.toml")


def _generated_candidates(root, installed):
    """Files on disk that belong to the generated layer (to find the stale ones)."""
    github = os.path.join(root, ".github")
    if os.path.isdir(github):
        for path in _walk(github):
            relative = to_posix(os.path.relpath(path, root))
            name = os.path.basename(path)
            if name.startswith(FRAMEWORK_WORKFLOW_PREFIX) and relative.startswith(".github/workflows/"):
                if installed:
                    yield relative  # F5 removes the framework's own CI from the project
                continue
            if name.startswith("bb-") or _text_has_notice(path):
                yield relative
    for target in SKILL_TARGETS:
        folder = os.path.join(root, *target.split("/"))
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.startswith("bb-"):
                    for path in _walk(os.path.join(folder, name)):
                        yield to_posix(os.path.relpath(path, root))
    agents = os.path.join(root, ".claude", "agents")
    if os.path.isdir(agents):
        for name in os.listdir(agents):
            if name.startswith("bb-"):
                yield f".claude/agents/{name}"
    if os.path.isfile(os.path.join(root, ".claude", "settings.json")):
        yield ".claude/settings.json"  # JSON has no generated notice; this path is reserved by the spec.


def _text_has_notice(path):
    try:
        return has_notice(read_text(path))
    except UnicodeDecodeError:
        return False  # binary files (images) are never generated


def changes(plan, root):
    """List of (kind, path): criar, alterar or remover."""
    result = []
    for path, content in sorted(plan.expected.items()):
        disk = os.path.join(root, *path.split("/"))
        if not os.path.exists(disk):
            result.append(("criar", path))
        elif read_text(disk) != content:
            result.append(("alterar", path))
    result += [("remover", path) for path in plan.stale]
    return result


def diff(plan, root, path):
    disk = os.path.join(root, *path.split("/"))
    before = read_text(disk).splitlines(keepends=True) if os.path.exists(disk) else []
    after = plan.expected.get(path, "").splitlines(keepends=True)
    return "".join(difflib.unified_diff(before, after, f"a/{path}", f"b/{path}"))


def apply(plan, root):
    applied = changes(plan, root)
    for kind, path in applied:
        disk = os.path.join(root, *path.split("/"))
        if kind == "remover":
            os.remove(disk)
            _remove_empty_parents(os.path.dirname(disk), root)
        else:
            write_text(disk, plan.expected[path])
    return applied


def _remove_empty_parents(folder, root):
    root = os.path.abspath(root)
    folder = os.path.abspath(folder)
    while folder != root and os.path.isdir(folder) and not os.listdir(folder):
        os.rmdir(folder)
        folder = os.path.dirname(folder)
