"""Reading and schema validation of bigbang.toml (spec 5.4; ADR-0002; ADR-0024).

The schema is strict: unknown sections and keys are refused, so a typo never silently disables a rule.
A file is written either in the legacy Portuguese names (v2) or in the v3 English names, never mixed. Once loaded,
the configuration answers in both: `config["projeto"]["modo"]` and `config["project"]["mode"]` are views of the same
value, so legacy code and scripts keep working on a v3 file and v3 code reads a legacy file.
"""
import os
import re
import tomllib

from . import names
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
BUILD_SYSTEMS = ("windows-x64", "windows-arm64", "linux-x64", "linux-arm64", "macos-x64", "macos-arm64", "android", "universal")
DEPLOY_PLATFORMS = ("linux/amd64", "linux/arm64")
COMMAND_KEYS = ("instalar", "lint", "tipos", "testes", "testes_aceite", "arquitetura", "cobertura", "build",
                "testes_alterados")


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
        "modo": _string(allowed=("padrao", "flash")),
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
        "runner": _string_list(re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z"), unique=True),
        "preparar_rede": _string(required=False),
    },
    "comandos": {key: _string(required=False) for key in COMMAND_KEYS},
    "testes": {"cobertura_minima": _integer(0, 100), "marca_pendente": _string(), "padrao_teste": _regex,
               "caminhos_estruturais": _string_list(non_empty=False)},
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
    "projeto": {"modo": "padrao"},
    "comandos": {"testes_alterados": ""},
    "testes": {"caminhos_estruturais": []},
    "deploy": {
        "artefato": "imagem",                # installed format; capabilities checked before generation
        "runner": ["ubuntu-24.04"],
        "preparar_rede": "",
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
    """Return the list of schema errors (empty when valid), for a legacy or a v3 file."""
    kind = dialect(config)
    if kind == "mixed":
        return ["bigbang.toml mistura nomes em português (v2) e em inglês (v3); escreva o arquivo em um só idioma "
                "(ADR-0024)"]
    if kind == "v3":
        legacy, _, errors = _v3_to_legacy(config)
        structural = [_message_to_v3(error) for error in _validate_legacy(legacy, expected_version)]
        return errors + [error for error in structural if error not in errors]
    return _validate_legacy(config, expected_version)


def _validate_legacy(config, expected_version=None):
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


# --- v3 (English) files -----------------------------------------------------------------------------------------------

SHARED_SECTIONS = {"bigbang", "deploy", "flags"}  # same spelling in both dialects; their keys tell them apart
LEGACY_ONLY_SECTIONS = set(names.SECTIONS) - SHARED_SECTIONS
V3_ONLY_SECTIONS = (set(names.SECTIONS_V3) - SHARED_SECTIONS) | {"workflow"}
MODES = ("normal", "flash", "autonomous")
BOARD_MODELS = ("single", "three-boards")
WORKFLOW_MODELS = ("grouping", "epic-branch")
LABEL_DIALECTS = ("v3", "legacy")
V3_DEFAULTS = {"board": {"model": "single", "labels": "v3"}, "workflow": {"model": "grouping"}}
LEGACY_DEFAULTS = {"board": {"model": "three-boards", "number": 0, "labels": "legacy"},
                   "workflow": {"model": "epic-branch"}}


def dialect(raw):
    """'legacy', 'v3' or 'mixed' for a parsed bigbang.toml."""
    sections = set(raw) if isinstance(raw, dict) else set()
    legacy, v3 = sections & LEGACY_ONLY_SECTIONS, sections & V3_ONLY_SECTIONS
    if not (legacy or v3):
        shared_keys = {key for section in SHARED_SECTIONS & sections if isinstance(raw[section], dict)
                       for key in raw[section]}
        v3 = {key for key in shared_keys if key in names.KEYS_V3.get("bigbang", {}) or
              key in names.KEYS_V3.get("deploy", {}) or key in names.KEYS_V3.get("flags", {})} - set(
                  names.KEYS["deploy"]) - set(names.KEYS["bigbang"]) - set(names.KEYS["flags"])
    if legacy and v3:
        return "mixed"
    return "v3" if v3 else "legacy"


def _message_to_v3(message):
    """Rename legacy sections and keys inside an error message for a v3 file."""
    message = re.sub(r"\[([a-z_]+)\]", lambda m: f"[{names.SECTIONS.get(m.group(1), m.group(1))}]", message)
    return re.sub(r"\b([a-z]+)\.([a-z][a-z0-9_-]*)\b",
                  lambda m: names.key_to_v3(m.group(0)) if m.group(1) in names.SECTIONS else m.group(0), message)


def _v3_to_legacy(raw):
    """Translate a v3 file into the legacy shape. Returns (legacy, v3_extras, errors)."""
    legacy, errors = {}, []
    extras = {"board": dict(V3_DEFAULTS["board"]), "workflow": dict(V3_DEFAULTS["workflow"]), "mode": None}
    for section, table in raw.items():
        if section == "workflow":
            if not isinstance(table, dict):
                errors.append("[workflow] deve ser uma seção")
                continue
            for key, value in table.items():
                if key != "model":
                    errors.append(f"chave desconhecida: workflow.{key}")
                elif value not in WORKFLOW_MODELS:
                    errors.append(f"workflow.model: deve ser um de: {', '.join(WORKFLOW_MODELS)}")
                else:
                    extras["workflow"]["model"] = value
            continue
        legacy_section = names.SECTIONS_V3.get(section)
        if legacy_section is None:
            errors.append(f"seção desconhecida [{section}]")
            continue
        if not isinstance(table, dict):
            errors.append(f"[{section}] deve ser uma seção")
            continue
        target = legacy.setdefault(legacy_section, {})
        for key, value in table.items():
            if section == "board" and key in ("model", "number", "labels"):
                extras["board"][key] = value
                continue
            if section == "compiled" and names.is_build_key(key):
                target[key] = value
                continue
            legacy_key = names.KEYS_V3.get(section, {}).get(key)
            if legacy_key is None:
                errors.append(f"chave desconhecida: {section}.{key}")
                continue
            dotted = f"{legacy_section}.{legacy_key}"
            mapping = names.VALUES.get(dotted, {})
            if isinstance(value, str) and value in mapping and mapping[value] != value:
                errors.append(f"{section}.{key}: use o valor em inglês {mapping[value]!r} (não {value!r})")
                target[legacy_key] = value  # present: the structural check must not call it missing
                continue
            if dotted == "projeto.modo" and value not in MODES:
                errors.append(f"project.mode: deve ser um de: {', '.join(MODES)}")
                continue
            if dotted == "projeto.modo":
                extras["mode"] = value
            target[legacy_key] = names.value_to_legacy(dotted, value)
    board = extras["board"]
    if board["labels"] not in LABEL_DIALECTS:
        errors.append(f"board.labels: deve ser um de: {', '.join(LABEL_DIALECTS)}")
    elif extras["workflow"]["model"] == "epic-branch" and board["labels"] != "legacy":
        errors.append('board.labels: o modelo epic-branch (esteira legada) só entende as labels em português; '
                      'use labels = "legacy"')
    if board["model"] not in BOARD_MODELS:
        errors.append(f"board.model: deve ser um de: {', '.join(BOARD_MODELS)}")
    elif board["model"] == "single":
        number = board.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            errors.append("board.number: número do Project único (inteiro, 0 antes de F4)")
        elif isinstance(legacy.get("paineis"), dict):
            for key in ("planejamento", "execucao", "bugs"):
                if key in legacy["paineis"]:
                    errors.append(f"board.{names.KEYS['paineis'][key]}: só existe no modelo three-boards")
                legacy["paineis"][key] = number  # the legacy view sees the single board in every role
    elif "number" in board and board["number"]:
        errors.append("board.number: só existe no modelo single")
    return legacy, extras, errors


def _legacy_to_v3(legacy):
    """Translate a (validated) legacy configuration into the v3 shape, values included."""
    result = {}
    for section, table in legacy.items():
        if not isinstance(table, dict) or section not in names.SECTIONS:
            continue
        target = result.setdefault(names.SECTIONS[section], {})
        for key, value in table.items():
            if section == "compilado" and names.is_build_key(key):
                target[key] = value
            elif key in names.KEYS.get(section, {}):
                target[names.KEYS[section][key]] = names.value_to_v3(f"{section}.{key}", value)
    return result


def _with_optional(legacy):
    """Copy of the legacy view with the documented defaults of optional keys filled in."""
    result = {section: dict(table) if isinstance(table, dict) else table for section, table in legacy.items()}
    for section, defaults in OPTIONAL_KEYS.items():
        if isinstance(result.get(section), dict):
            for key, value in defaults.items():
                result[section].setdefault(key, list(value) if isinstance(value, list) else value)
    return result


def views(raw):
    """Both views of a valid parsed file merged in one mapping (see the module docstring)."""
    kind = dialect(raw)
    if kind == "v3":
        legacy, extras, _ = _v3_to_legacy(raw)
        legacy = _with_optional(legacy)
        v3 = _legacy_to_v3(legacy)
        for section, table in raw.items():
            if isinstance(table, dict):
                v3.setdefault(section, {}).update(table)
        if extras["mode"]:
            v3["project"]["mode"] = extras["mode"]
        for section, defaults in V3_DEFAULTS.items():
            for key, value in defaults.items():
                v3.setdefault(section, {}).setdefault(key, value)
        v3["board"].setdefault("number", extras["board"].get("number", 0))
    else:
        legacy = _with_optional(raw)
        v3 = _legacy_to_v3(legacy)
        for section, defaults in LEGACY_DEFAULTS.items():
            for key, value in defaults.items():
                v3.setdefault(section, {}).setdefault(key, value)
    merged = {section: dict(table) if isinstance(table, dict) else table for section, table in legacy.items()}
    for section, table in v3.items():
        merged.setdefault(section, {}).update(table)
    merged["_dialect"] = kind
    return merged


HEADER = re.compile(r"^(\s*)\[([a-z_]+)\](.*)$")
ASSIGNMENT = re.compile(r'^(\s*)([A-Za-z0-9_-]+)(\s*=\s*)("(?:[^"\\]|\\.)*"|[^#\n]*?)([ \t]*(?:#.*)?)$')


def text_to_v3(text):
    """Rewrite a legacy bigbang.toml text with the v3 names, keeping layout and comments (migration, ADR-0024).

    [paineis] becomes [board] with model = "three-boards" (the boards migrate in a later step); [workflow] with
    model = "epic-branch" is appended, so the project keeps its current behavior until it migrates its workflow."""
    if dialect(parse(text)) != "legacy":
        raise BbError("bigbang.toml já está em inglês (v3) ou mistura os dois", EXIT_INVALID_CONFIG)
    lines, section = [], None
    for line in text.split("\n"):
        header = HEADER.match(line)
        if header:
            section = header.group(2)
            lines.append(f"{header.group(1)}[{names.SECTIONS.get(section, section)}]{header.group(3)}")
            if section == "paineis":
                lines.append('model = "three-boards"                 # single depois da migração do quadro')
                lines.append('labels = "legacy"                      # v3 depois da migração das labels')
            continue
        assignment = ASSIGNMENT.match(line)
        if assignment and section in names.KEYS:
            indent, key, equals, value, comment = assignment.groups()
            new_key = key if names.is_build_key(key) else names.KEYS[section].get(key, key)
            dotted = f"{section}.{key}"
            if value.startswith('"') and dotted in names.VALUES:
                literal = tomllib.loads(f"v = {value}")["v"]
                value = '"' + names.value_to_v3(dotted, literal) + '"'
            lines.append(f"{indent}{new_key}{equals}{value}{comment}")
            continue
        lines.append(line)
    result = "\n".join(lines).rstrip("\n") + "\n\n[workflow]\nmodel = \"epic-branch\"\n"
    if validate(parse(result)) and not validate(parse(text)):
        raise BbError("a tradução para v3 não validou; nada foi alterado", EXIT_INVALID_CONFIG)
    return result


def parse(text, source="bigbang.toml"):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BbError(f"{source} não é um TOML válido: {exc}", EXIT_INVALID_CONFIG) from exc


def load(root, required=True):
    """Load and validate bigbang.toml. Returns None when the file does not exist and is not required."""
    path = config_path(root)
    if not os.path.exists(path):
        from . import framework
        own = framework.load(root, bootstrap=required)
        if own is not None:
            return own
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
    return views(config)


def _consistent(dotted_key):
    """'legacy', 'v3' or None: a key must be spelled wholly in one language (section and key)."""
    section, _, key = dotted_key.partition(".")
    if section.startswith("_") or key.startswith("_"):
        return None
    legacy_keys, v3_keys = names.KEYS.get(section), names.KEYS_V3.get(section)
    legacy = legacy_keys is not None and (not key or key in legacy_keys or
                                          (section == "compilado" and names.is_build_key(key)))
    v3 = v3_keys is not None and (not key or key in v3_keys or (section == "compiled" and names.is_build_key(key)))
    if (section, key) in names.V3_ONLY or section == "workflow":
        return "v3"
    if legacy and v3:
        return "shared"
    return "legacy" if legacy else "v3" if v3 else "unknown"


def get(config, dotted_key):
    """Return the value at `secao.chave` (only scalar values and lists of scalars), in either language.

    The key must be spelled wholly in one language (`projeto.modo` or `project.mode`, never `projeto.mode`), and
    internal keys are never exposed. A loaded configuration holds both views; a plain mapping (as tests build) is
    translated on the fly. A missing key reports the key that was asked."""
    spelling = _consistent(dotted_key)
    if spelling is None or (spelling == "unknown" and "." in dotted_key and config.get("_dialect")):
        raise BbError(f"chave inexistente no bigbang.toml: {dotted_key}", EXIT_UNKNOWN_KEY)
    try:
        return _get(config, dotted_key)
    except BbError as original:
        if spelling in ("unknown", "shared") or config.get("_dialect"):
            raise original
        try:
            if spelling == "v3":
                legacy_key = names.key_to_legacy(dotted_key)
                if legacy_key and legacy_key != dotted_key:
                    return names.value_to_v3(legacy_key, _get(config, legacy_key))
                section, _, key = dotted_key.partition(".")
                if (section, key) in names.V3_ONLY:
                    return names.V3_ONLY[(section, key)]
            else:
                v3_key = names.key_to_v3(dotted_key)
                if v3_key != dotted_key:
                    return names.value_to_legacy(dotted_key, _get(config, v3_key))
        except BbError:
            pass
        raise original


def _get(config, dotted_key):
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
