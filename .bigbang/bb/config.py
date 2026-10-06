"""Reading and schema validation of bigbang.toml (spec 5.4; ADR-0002).

The schema is strict: unknown sections and keys are refused, so a typo never silently disables a rule.
"""
import os
import re
import tomllib

from .errors import EXIT_INVALID_CONFIG, EXIT_UNKNOWN_KEY, BbError
from .paths import config_path, framework_version

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DELIVERY_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\Z")
REPOSITORY = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
SPDX = re.compile(r"^[A-Za-z0-9.+-]+$")
URL = re.compile(r"^https://\S+$")
SERVICE = re.compile(r"^[a-z][a-z0-9_-]*$")
SERVICE_BUILD = re.compile(r"^[a-z][a-z0-9_-]*=\S+$")
HEALTH_PATH = re.compile(r"^/\S*$")

DEPENDABOT_ECOSYSTEMS = ("npm", "pip", "uv", "gomod", "cargo", "maven", "gradle", "composer", "nuget", "bundler",
                        "docker", "pub", "mix", "swift", "terraform")
BUILD_SYSTEMS = ("windows-x64", "windows-arm64", "linux-x64", "linux-arm64", "macos-x64", "macos-arm64", "android")
DEPLOY_PLATFORMS = ("linux/amd64", "linux/arm64")
COMMAND_KEYS = ("instalar", "lint", "tipos", "testes", "testes_aceite", "arquitetura", "cobertura", "build")


# --- value checkers: each returns an error message (Portuguese) or None ---------------------------------------------

def _string(pattern=None, allowed=None, required=True):
    def check(value):
        if not isinstance(value, str):
            return "deve ser texto"
        if required and not value:
            return "não pode ser vazio"
        if allowed is not None and value not in allowed:
            return f"deve ser um de: {', '.join(allowed)}"
        if pattern is not None and value and not pattern.match(value):
            return f"formato inválido ({value!r})"
        return None
    return check


def _integer(minimum=None, maximum=None):
    def check(value):
        if isinstance(value, bool) or not isinstance(value, int):
            return "deve ser número inteiro"
        if minimum is not None and value < minimum:
            return f"deve ser no mínimo {minimum}"
        if maximum is not None and value > maximum:
            return f"deve ser no máximo {maximum}"
        return None
    return check


def _boolean(value):
    return None if isinstance(value, bool) else "deve ser true ou false"


def _string_list(pattern=None, allowed=None, non_empty=True, unique=False):
    def check(value):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            return "deve ser uma lista de textos não vazios"
        if non_empty and not value:
            return "não pode ser uma lista vazia"
        if unique and len(set(value)) != len(value):
            return "não pode ter itens repetidos"
        for item in value:
            if allowed is not None and item not in allowed:
                return f"item {item!r} inválido; use: {', '.join(allowed)}"
            if pattern is not None and not pattern.match(item):
                return f"item {item!r} com formato inválido"
        return None
    return check


def _regex(value):
    error = _string()(value)
    if error:
        return error
    try:
        re.compile(value)
    except re.error as exc:
        return f"expressão regular inválida: {exc}"
    return None


SCHEMA = {
    "bigbang": {"versao": _string(SEMVER), "origem": _string(REPOSITORY)},
    "projeto": {
        "nome": _string(), "slug": _string(SLUG), "dono": _string(GITHUB_LOGIN),
        "repositorio": _string(REPOSITORY), "visibilidade": _string(allowed=("privado", "publico")),
        "licenca": _string(SPDX, required=False),
    },
    "entrega": {
        "perfil": _string(allowed=("deploy", "compilado")), "alvo": _string(DELIVERY_NAME, required=False),
        "caminhos_artefato": _string_list(), "arquivo_versao": _string(required=False),
        "ecossistemas": _string_list(allowed=DEPENDABOT_ECOSYSTEMS, non_empty=False, unique=True),
    },
    "compilado": {"sistemas": _string_list(allowed=BUILD_SYSTEMS, unique=True)},  # plus build_<system>
    "deploy": {
        "artefato": _string(DELIVERY_NAME),
        "imagem": _string(), "url_staging": _string(URL), "url_producao": _string(URL), "smoke": _string(),
        "servicos": _string_list(SERVICE_BUILD), "plataformas": _string_list(allowed=DEPLOY_PLATFORMS, unique=True),
        "caminho_saude": _string(HEALTH_PATH), "servico_migrar": _string(SERVICE),
        "servico_checar": _string(SERVICE, required=False),
    },
    "comandos": {key: _string(required=False) for key in COMMAND_KEYS},
    "testes": {"cobertura_minima": _integer(0, 100), "marca_pendente": _string(), "padrao_teste": _regex},
    "seguranca": {
        "nivel_asvs": _string(allowed=("L1", "L2", "L3")), "banco_no_navegador": _boolean,
        "zonas_sensiveis": _string_list(non_empty=False),
    },
    "paineis": {
        "owner": _string(GITHUB_LOGIN), "planejamento": _integer(0), "execucao": _integer(0), "bugs": _integer(0),
    },
    "ias": {
        "nomes": _string_list(SLUG, unique=True), "tarefas_por_ia": _integer(1), "trava_expira_horas": _integer(1),
        "espera_confirmacao_segundos": _integer(1),
    },
    "flags": {"validade_maxima_dias": _integer(1)},
}

# Keys that may be left out: the default is used (`bb config get` returns it). Added after 1.0, so a project made
# before them keeps validating.
OPTIONAL_KEYS = {
    "deploy": {
        "artefato": "imagem",                # installed format; capabilities checked before generation
        "servicos": ["app=Dockerfile"],      # service=Dockerfile, one image per service (built from the root)
        "plataformas": ["linux/amd64"],      # docker buildx --platform
        "caminho_saude": "/api/health",      # health check path (OBS-04)
        "servico_migrar": "migrar",          # compose service that runs the migration
        "servico_checar": "",                # compose service that checks the server before migrating ("" = none)
    },
}

# Sections that only exist for one delivery profile; the other one may be present (as in the example) but is ignored.
PROFILE_SECTIONS = {"deploy": "deploy", "compilado": "compilado"}


def validate(config, expected_version=None):
    """Return the list of schema errors (empty when valid)."""
    errors = []
    for section in config:
        if section not in SCHEMA:
            errors.append(f"seção desconhecida [{section}]")
    perfil = config.get("entrega", {}).get("perfil") if isinstance(config.get("entrega"), dict) else None
    for section, keys in SCHEMA.items():
        optional = section in PROFILE_SECTIONS and PROFILE_SECTIONS[section] != perfil
        if section not in config:
            if not optional:
                errors.append(f"seção obrigatória ausente: [{section}]")
            continue
        table = config[section]
        if not isinstance(table, dict):
            errors.append(f"[{section}] deve ser uma seção")
            continue
        errors.extend(_validate_section(section, table, keys))
    if not errors:
        errors.extend(_cross_checks(config, expected_version))
    return errors


def _validate_section(section, table, keys):
    errors = []
    extra_keys = set()
    if section == "compilado":
        systems = table.get("sistemas") if isinstance(table.get("sistemas"), list) else []
        extra_keys = {f"build_{system}" for system in systems}
        for key in sorted(extra_keys):
            if key not in table:
                errors.append(f"[compilado] falta {key} (comando de build de cada sistema)")
            elif _string()(table[key]):
                errors.append(f"[compilado] {key}: {_string()(table[key])}")
    for key in table:
        if key not in keys and key not in extra_keys:
            errors.append(f"chave desconhecida: {section}.{key}")
    for key, check in keys.items():
        if key not in table:
            if key not in OPTIONAL_KEYS.get(section, {}):
                errors.append(f"chave obrigatória ausente: {section}.{key}")
            continue
        error = check(table[key])
        if error:
            errors.append(f"{section}.{key}: {error}")
    return errors


def _cross_checks(config, expected_version):
    errors = []
    entrega, projeto = config["entrega"], config["projeto"]
    if entrega["perfil"] == "deploy" and not entrega["alvo"]:
        errors.append("entrega.alvo: no perfil deploy deve indicar um alvo (consulte bb alvos)")
    if entrega["perfil"] == "compilado" and entrega["alvo"]:
        errors.append('entrega.alvo: no perfil compilado deve ser ""')
    if projeto["visibilidade"] == "publico" and not projeto["licenca"]:
        errors.append("projeto.licenca: obrigatória quando o repositório é público (identificador SPDX, ex.: MIT)")
    if not projeto["repositorio"].lower().startswith(projeto["dono"].lower() + "/"):
        errors.append("projeto.repositorio: deve pertencer ao projeto.dono")
    deploy = config.get("deploy")
    if entrega["perfil"] == "deploy" and isinstance(deploy, dict):
        names = [item.split("=", 1)[0] for item in deploy.get("servicos", [])]
        if len(set(names)) != len(names):
            errors.append("deploy.servicos: nome de serviço repetido")
        if deploy.get("servico_migrar", "migrar") in names or deploy.get("servico_checar") in names:
            errors.append("deploy.servico_migrar/servico_checar: não pode ser um dos serviços publicados")
    if expected_version is not None and config["bigbang"]["versao"] != expected_version:
        errors.append(f"bigbang.versao ({config['bigbang']['versao']}) diferente de .bigbang/VERSION "
                      f"({expected_version}); rode bb atualizar ou corrija a versão")
    return errors


def parse(text, source="bigbang.toml"):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BbError(f"{source} não é um TOML válido: {exc}", EXIT_INVALID_CONFIG) from exc


def load(root, required=True):
    """Load and validate bigbang.toml. Returns None when the file does not exist and is not required."""
    path = config_path(root)
    if not os.path.exists(path):
        if required:
            raise BbError("bigbang.toml não encontrado: o projeto ainda não foi fundado (rode bb init)",
                          EXIT_INVALID_CONFIG)
        return None
    with open(path, "rb") as handle:
        try:
            config = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise BbError(f"bigbang.toml não é um TOML válido: {exc}", EXIT_INVALID_CONFIG) from exc
    errors = validate(config, framework_version(root))
    if errors:
        raise BbError("bigbang.toml inválido:\n" + "\n".join(f"  - {e}" for e in errors), EXIT_INVALID_CONFIG)
    return config


def get(config, dotted_key):
    """Return the value at `secao.chave` (only scalar values and lists of scalars)."""
    node = config
    parts = dotted_key.split(".")
    if len(parts) == 2 and parts[1] in OPTIONAL_KEYS.get(parts[0], {}) and isinstance(config.get(parts[0]), dict):
        return config[parts[0]].get(parts[1], OPTIONAL_KEYS[parts[0]][parts[1]])
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise BbError(f"chave inexistente no bigbang.toml: {dotted_key}", EXIT_UNKNOWN_KEY)
        node = node[part]
    if isinstance(node, dict):
        raise BbError(f"{dotted_key} é uma seção; peça uma chave dela", EXIT_UNKNOWN_KEY)
    return node


def format_value(value):
    """Plain-text form used by `bb config get` (lists: one item per line; booleans: true/false)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "\n".join(format_value(item) for item in value)
    return str(value)
