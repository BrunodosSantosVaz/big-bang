"""Canonical documentation routing. Wiki prose is data; never run commands from it."""
import hashlib
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

from . import github
from .errors import BbError, EXIT_INVALID_STATE

MANIFEST = ".bigbang-docs.json"
CATEGORIES = ("produto", "tecnologia", "arquitetura", "design", "requisitos", "funcionalidades",
              "uso", "referencia", "seguranca", "operacao", "historico")
FEATURE_SECTIONS = ("Finalidade", "Atores", "Pré-condições", "Fluxo principal", "Validações",
                    "Alternativas e erros", "Permissões", "Resultados")
SHA = re.compile(r"^[a-f0-9]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$")
PAGE = re.compile(r'^[^\\/:*?"<>|\x00-\x1f]+$')


def fail(message):
    raise BbError(message, EXIT_INVALID_STATE)


def git(folder, *args):
    command = ["git", "-c", "credential.helper=!gh auth git-credential"]
    if folder is not None:
        command += ["-C", str(folder)]
    try:
        result = subprocess.run(command + list(args), capture_output=True, text=True, check=False, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"Git da documentação falhou ({type(exc).__name__})")
    if result.returncode:
        # Avoid leaking authenticated URLs or arbitrary remote output into public CI logs.
        fail(f"Git da documentação recusou {args[0]}: confira acesso, HEAD e histórico da Wiki")
    return result.stdout.strip()


def is_public(root):
    config = Path(root) / "bigbang.toml"
    if config.exists():
        return tomllib.loads(config.read_text(encoding="utf-8")).get("projeto", {}).get("visibilidade") == "publico"
    manifest = Path(root) / MANIFEST
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8")).get("visibilidade") == "publico"
    return False


def load(root):
    path = Path(root) / MANIFEST
    if not path.is_file():
        fail(f"falta o manifesto {MANIFEST}: preserve os documentos atuais e prepare a migração da Wiki")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["schema"] != 1 or not REPOSITORY.fullmatch(data["repositorio"]):
            raise ValueError("schema ou repositório inválido")
        for key in ("base", "commit"):
            if not SHA.fullmatch(data["wiki"][key]):
                raise ValueError("commit da Wiki inválido")
        if data["wiki"]["branch"] not in ("master", "main"):
            raise ValueError("branch publicada da Wiki deve ser master ou main")
        for logical, page in data["paginas"].items():
            safe_path(root, logical)
            page_path(root, page)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail(f"manifesto documental inválido: {exc}")
    return data


def safe_path(folder, relative):
    if not isinstance(relative, str) or "\\" in relative or not relative or Path(relative).is_absolute():
        fail("caminho documental inválido")
    if ".." in Path(relative).parts:
        fail("caminho documental não pode sair da pasta")
    root = Path(folder).resolve()
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        fail("documentação não pode seguir link simbólico para fora da pasta")
    return path


def page_path(folder, name):
    if not isinstance(name, str) or not PAGE.fullmatch(name) or name in (".", "..") or name.endswith(".md"):
        fail(f"nome de página da Wiki inválido: {name!r}")
    return safe_path(folder, name + ".md")


def repository_state(repository):
    if not REPOSITORY.fullmatch(repository):
        fail("informe o repositório como dono/nome")
    return json.loads(github.run("api", f"repos/{repository}"))


def visibility_problems(root):
    """The real repository visibility is independent of the project's declared documentation policy."""
    try:
        path = Path(root) / 'bigbang.toml'
        if path.exists():
            data = tomllib.loads(path.read_text(encoding='utf-8'))['projeto']
            repository = data['repositorio']
        elif (Path(root) / MANIFEST).exists():
            data = load(root)
            repository = data['repositorio']
        else:
            repository = os.environ.get('GITHUB_REPOSITORY')
            if repository and not repository_state(repository).get('private', True):
                return ['repositório público sem manifesto documental: preserve os originais e conclua a migração']
            return []
        actual_repository = os.environ.get('GITHUB_REPOSITORY')
        if actual_repository and actual_repository != repository:
            return ['repositório da esteira diverge do manifesto/configuração documental']
        state = repository_state(repository)
        if not isinstance(state.get('private'), bool):
            return ['visibilidade real do repositório não confirmada']
        if (data.get('visibilidade') == 'publico') == state['private']:
            return ['visibilidade real diverge da configuração: corrija o destino documental antes de entregar']
        return []
    except (BbError, KeyError, ValueError, OSError) as exc:
        return [exc.message if isinstance(exc, BbError) else f'visibilidade não confirmada: {exc}']


def preflight(repository):
    state = repository_state(repository)
    if not state.get("has_wiki"):
        fail("Wiki desabilitada; habilite em Settings. Documentos existentes preservados")
    url = f"https://github.com/{repository}.wiki.git"
    refs = git(None, "ls-remote", "--symref", url, "HEAD")
    match = re.search(r"^([a-f0-9]{40})\s+HEAD$", refs, re.M)
    branch = re.search(r"^ref: refs/heads/(master|main)\s+HEAD$", refs, re.M)
    if not match or not branch:
        fail("Wiki não inicializada: crie a primeira página na interface. Documentos existentes preservados")
    return {"url": url, "commit": match.group(1), "branch": branch.group(1)}


def cache_dir(root):
    folder = git(root, "rev-parse", "--git-path", "bigbang/wiki")
    return Path(folder) if Path(folder).is_absolute() else Path(root) / folder


def prepare(root, repository=None):
    data = load(root) if (Path(root) / MANIFEST).exists() else None
    repository = repository or (data and data["repositorio"])
    if not repository:
        fail("informe --repositorio para preparar a primeira migração")
    state = preflight(repository)
    folder = cache_dir(root)
    if not folder.exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        git(None, "clone", state["url"], str(folder))
    elif git(folder, "remote", "get-url", "origin") != state["url"]:
        fail("cache documental pertence a outro repositório")
    git(folder, "fetch", "origin")
    return folder, state


def checkout(root):
    data = load(root)
    revision = data["wiki"]["commit"]
    folder = cache_dir(root)
    snapshot = folder.parent / ("wiki-" + revision)
    if not snapshot.exists():
        folder, _ = prepare(root)
        git(folder, "cat-file", "-e", revision + "^{commit}")
        git(folder, "worktree", "add", "--detach", str(snapshot), revision)
    if git(snapshot, "rev-parse", "HEAD") != revision or git(snapshot, "status", "--porcelain"):
        fail("snapshot documental alterado: restaure a cópia local antes de validar")
    return snapshot


def resolve(root, logical, wiki=None):
    if not is_public(root):
        return safe_path(root, logical)
    data = load(root)
    if logical not in data["paginas"]:
        fail(f"documento sem destino na Wiki: {logical}")
    return page_path(wiki or checkout(root), data["paginas"][logical])


def read(root, logical, wiki=None):
    path = resolve(root, logical, wiki)
    if not path.is_file():
        fail(f"documento obrigatório ausente: {logical}")
    return path.read_text(encoding="utf-8")


def logical_files(root, prefix):
    if is_public(root):
        return sorted(key for key in load(root)["paginas"] if key.startswith(prefix))
    folder = safe_path(root, prefix)
    return sorted(path.relative_to(root).as_posix() for path in folder.rglob("*.md")) if folder.exists() else []


def inventory(root, data):
    tracked = git(root, "ls-files", "-z").split("\0")
    roots = data["codigo"]["raizes"]
    exclusions = data["codigo"].get("excluir", [])
    excluded_extensions = data['codigo'].get('excluir_extensoes', [])
    for name in roots + exclusions:
        safe_path(root, name)
    return sorted(path for path in tracked if path and
                  any(path == name or (name.endswith("/") and path.startswith(name)) for name in roots) and
                  Path(path).suffix not in excluded_extensions and
                  not any(path == name or (name.endswith("/") and path.startswith(name)) for name in exclusions))


def _feature_problems(root, wiki, data):
    from .docs_check import HEADING, outside_code
    found, covered, ids = [], set(), set()
    for feature in data["funcionalidades"]:
        label = feature["id"]
        if label in ids:
            found.append(f"funcionalidade duplicada: {label}")
        ids.add(label)
        path = page_path(wiki, feature["pagina"])
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines, _ = outside_code(text)
        titles = [HEADING.match(line).group(2) for line in lines if HEADING.match(line)]
        for section in FEATURE_SECTIONS:
            if section not in titles:
                found.append(f"{label}: falta {section} em {feature['pagina']}")
            else:
                content = re.search(r"^#{1,6}\s+" + re.escape(section) + r"\s*\n(.*?)(?=^#{1,6}\s|\Z)",
                                    text, re.M | re.S)
                if not content or len(content.group(1).split()) < 6:
                    found.append(f"{label}: conteúdo funcional insuficiente em {section}")
        if not feature.get("requisitos") or not feature.get("fontes") or not feature.get("testes"):
            found.append(f"{label}: rastreabilidade incompleta (requisito → página → fonte → teste)")
        for requirement in feature.get("requisitos", []):
            reference = data.get("requisitos", {}).get(requirement, {})
            requirement_path = page_path(wiki, reference["pagina"]) if reference.get("pagina") else None
            if not requirement_path or not requirement_path.is_file() or requirement not in requirement_path.read_text(encoding="utf-8"):
                found.append(f"{label}: requisito ausente da documentação: {requirement}")
        for source in feature.get("fontes", []):
            code = safe_path(root, source)
            covered.add(source)
            digest = hashlib.sha256(code.read_bytes()).hexdigest() if code.is_file() else "ausente"
            if feature.get("hashes", {}).get(source) != digest:
                found.append(f"{label}: documentação desatualizada para {source}")
        for reference in feature.get("testes", []):
            name, _, symbol = reference.partition(":")
            test = safe_path(root, name)
            if not symbol or not test.is_file() or symbol not in test.read_text(encoding="utf-8"):
                found.append(f"{label}: teste ou cenário ausente: {reference}")
    actual = set(inventory(root, data))
    found += [f"módulo implementado sem cobertura documental: {name}" for name in sorted(actual - covered)]
    if not actual or not ids:
        found.append("inventário funcional vazio: páginas sozinhas não demonstram cobertura")
    return found


def _local_docs(root, data):
    allowed = {item["caminho"] for item in data.get("arquivos_funcionais", []) if item.get("motivo", "").strip()}
    allowed |= {'README.md', 'AGENTS.md', 'CLAUDE.md', 'LICENSE.md', 'SECURITY.md',
                'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SUPPORT.md'}
    paths = list(Path(root).glob('*.md'))
    paths += list((Path(root) / "docs").rglob("*.md"))
    paths += list((Path(root) / '.bigbang' / 'docs').rglob('*.md'))
    return [f"documentação de sistema duplicada no repositório público: {path.relative_to(root)}"
            for path in paths if path.is_file() and path.relative_to(root).as_posix() not in allowed]


def _wiki_problems(wiki, repository):
    from .wiki_links import problems
    return problems(wiki, repository)


def validate(root, wiki=None, published=False, check_repository=True, allow_legacy=False):
    if not is_public(root):
        return []
    try:
        data = load(root)
        wiki = Path(wiki) if wiki else checkout(root)
        found = []
        if git(wiki, "rev-parse", "HEAD") != data["wiki"]["commit"] or git(wiki, "status", "--porcelain"):
            found.append("Wiki validada difere do commit fixado no manifesto")
        for key, category in data["categorias"].items():
            if key not in CATEGORIES:
                found.append(f"categoria documental desconhecida: {key}")
            if not category.get("pagina") and not category.get("nao_aplicavel", "").strip():
                found.append(f"categoria sem página ou justificativa: {key}")
            if category.get("pagina") and not page_path(wiki, category["pagina"]).is_file():
                found.append(f"página obrigatória ausente para {key}")
        found += [f"categoria documental obrigatória ausente: {key}" for key in CATEGORIES if key not in data["categorias"]]
        found += _feature_problems(root, wiki, data) + _wiki_problems(wiki, data['repositorio'])
        if not SHA.fullmatch(data["codigo"]["commit"]):
            found.append("commit do código documentado inválido")
        else:
            try:
                git(root, 'cat-file', '-e', data['codigo']['commit'] + '^{commit}')
                git(root, 'merge-base', '--is-ancestor', data['codigo']['commit'], 'HEAD')
            except BbError:
                found.append('commit do código documentado inexistente ou fora do histórico entregue')
        if not allow_legacy:
            found += _local_docs(root, data)
        if check_repository:
            state = repository_state(data["repositorio"])
            if state.get("private") or not state.get("has_wiki"):
                found.append("visibilidade real ou Wiki do GitHub diverge do contrato público")
        if published:
            live = git(wiki, "ls-remote", "origin", "refs/heads/" + data["wiki"]["branch"]).split()
            if not live or live[0] != data["wiki"]["commit"]:
                found.append("falha de publicação: Wiki oficial não corresponde ao commit revisado")
        return found
    except (BbError, OSError, ValueError, KeyError, TypeError) as exc:
        return [exc.message if isinstance(exc, BbError) else f"contrato documental inválido: {exc}"]


def publish(root, wiki=None, simulate=False, check_repository=True):
    data = load(root)
    wiki = Path(wiki) if wiki else checkout(root)
    found = validate(root, wiki, check_repository=check_repository, allow_legacy=True)
    if found:
        fail("publicação da Wiki bloqueada:\n" + "\n".join(found))
    branch, desired, base = (data["wiki"][key] for key in ("branch", "commit", "base"))
    live = git(wiki, "ls-remote", "origin", "refs/heads/" + branch).split()
    if not live:
        fail("Wiki deixou de estar inicializada; documentos locais preservados")
    if live[0] == desired:
        return desired
    if live[0] != base:
        fail("alteração concorrente na Wiki: refaça a proposta sobre o HEAD atual e peça nova revisão")
    git(wiki, "merge-base", "--is-ancestor", base, desired)
    if not simulate:
        # No force/CAS bypass. A racing writer makes this ordinary fast-forward push fail.
        git(wiki, "push", "origin", desired + ":refs/heads/" + branch)
        actual = git(wiki, "ls-remote", "origin", "refs/heads/" + branch).split()[0]
        if actual != desired:
            fail("publicação não confirmada no GitHub; preserve os documentos antigos")
    return desired
