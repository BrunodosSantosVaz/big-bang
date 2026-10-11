"""Feature flags of the grouping workflow (ADR-0022): flags.toml in Portuguese (v2) or English (v3), the release
gate (every epic of a release is approved or ships dark behind its flag) and the pending-acceptance rule (a pending
acceptance test may only ship for an epic whose flag is off in production)."""
import datetime
import re
import tomllib

from .errors import EXIT_INVALID_STATE, BbError

FIELDS = {"name": "nome", "owner": "dono", "reason": "motivo", "epic": "epico", "created": "criada_em",
          "expires": "expira_em", "state": "estado"}
ENVIRONMENTS = {"staging": "staging", "production": "producao"}
EPIC = re.compile(r"^#?(\d+)$")


def _field(entry, key):
    return entry.get(key, entry.get(FIELDS.get(key, key)))


def parse(text, today):
    """List of flags: name, owner, reason, epic (int), created, expires, staging, production."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BbError(f"flags.toml inválido: {exc}", EXIT_INVALID_STATE) from exc
    entries = data.get("flag", [])
    if not isinstance(entries, list) or set(data) - {"flag"}:
        raise BbError("flags.toml: use somente tabelas [[flag]]", EXIT_INVALID_STATE)
    result, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BbError("flags.toml: cada flag precisa ser uma tabela [[flag]]", EXIT_INVALID_STATE)
        name = _field(entry, "name")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise BbError("flags.toml: nome ausente ou duplicado", EXIT_INVALID_STATE)
        seen.add(name)
        for key in ("owner", "reason"):
            if not isinstance(_field(entry, key), str) or not _field(entry, key).strip():
                raise BbError(f"flag {name}: falta {key}", EXIT_INVALID_STATE)
        epic = EPIC.match(str(_field(entry, "epic") or ""))
        if not epic:
            raise BbError(f"flag {name}: epic deve ser o número do épico (#n)", EXIT_INVALID_STATE)
        created, expires = _field(entry, "created"), _field(entry, "expires")
        if type(created) is not datetime.date or type(expires) is not datetime.date or expires < created \
                or created > today:
            raise BbError(f"flag {name}: datas inválidas (created/expires)", EXIT_INVALID_STATE)
        state = _field(entry, "state")
        if not isinstance(state, dict):
            raise BbError(f"flag {name}: falta a tabela de estado", EXIT_INVALID_STATE)
        values = {env: state.get(env, state.get(legacy)) for env, legacy in ENVIRONMENTS.items()}
        if any(type(value) is not bool for value in values.values()):
            raise BbError(f"flag {name}: estado de staging e production deve ser true/false", EXIT_INVALID_STATE)
        result.append({"name": name, "owner": _field(entry, "owner"), "reason": _field(entry, "reason"),
                       "epic": int(epic.group(1)), "created": created, "expires": expires, **values})
    return result


def switch(text, name, environment, value, today):
    """flags.toml with one flag switched on or off, in the file's own language and layout (bb flag on|off)."""
    flags = parse(text, today)
    if name not in {flag["name"] for flag in flags}:
        raise BbError(f"flag inexistente: {name}", EXIT_INVALID_STATE)
    if environment not in ENVIRONMENTS:
        raise BbError("ambiente deve ser staging ou production", EXIT_INVALID_STATE)
    lines, current = text.split("\n"), None
    keys = {environment, ENVIRONMENTS[environment]}
    for index, line in enumerate(lines):
        match = re.match(r'^\s*(name|nome)\s*=\s*"(.*)"', line)
        if match:
            current = match.group(2)
        key = re.match(r"^(\s*)(\w+)(\s*=\s*)(true|false)(.*)$", line)
        if current == name and key and key.group(2) in keys:
            lines[index] = f"{key.group(1)}{key.group(2)}{key.group(3)}{'true' if value else 'false'}{key.group(5)}"
    result = "\n".join(lines)
    if next(flag for flag in parse(result, today) if flag["name"] == name)[environment] != value:
        raise BbError(f"flag {name}: não foi possível alterar {environment}", EXIT_INVALID_STATE)
    return result


def _by_epic(flags):
    result = {}
    for flag in flags:
        result.setdefault(flag["epic"], []).append(flag)
    return result


def release_problems(epic_decisions, flags, today=None):
    """Why a release cannot ship: {epic: 'approved'|'pending'} → every epic is approved, or ships dark (every flag
    of the epic off in production); an expired flag is renewed with the owner or removed first."""
    found, by_epic = [], _by_epic(flags)
    if today is not None:
        found += [f"flag {flag['name']} vencida em {flag['expires']}: renove (com o dono) ou remova antes da release"
                  for flag in flags if flag["expires"] < today]
    for epic, decision in sorted(epic_decisions.items()):
        if decision in ("approved", "automatic"):
            continue
        own = by_epic.get(epic, [])
        if not own:
            found.append(f"épico #{epic} sem homologação e sem feature flag: não pode entrar na release")
        for flag in own:
            if flag["production"]:
                found.append(f"épico #{epic} sem homologação com a flag {flag['name']} ligada em produção")
    return found


def pending_problems(pending_issue_epics, flags):
    """{issue with pending acceptance marks: its epic (or None)} → only dark epics may ship pending tests."""
    found, by_epic = [], _by_epic(flags)
    for issue, epic in sorted(pending_issue_epics.items()):
        own = by_epic.get(epic, []) if epic else []
        if not own or any(flag["production"] for flag in own):
            found.append(f"teste de aceite pendente da #{issue} numa release sem a flag do épico desligada")
    return found
