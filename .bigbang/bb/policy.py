"""Work policy of the v3 modes (ADR-0025): who approves each gate, the risk floor of a change, the limits and the
autonomy contract. Pure: the configuration and the contract are passed in, nothing is read from disk here."""
import datetime
import fnmatch
import hashlib
import json
import re

MODES = ("normal", "flash", "autonomous")
GATES = ("backlog", "refinement", "prototype", "selection", "tests", "pr", "qa", "publish", "flag", "cancel")
RISKS = ("low", "medium", "high", "critical")
# Changes whose risk floor is critical or high, whatever the label says (the AI never lowers a risk floor).
CRITICAL_PATHS = (".github/**", ".bigbang/**", "migrations/**", "**/migrations/**", "**/auth/**", "**/payments/**",
                  "infra/**", "infrastructure/**", "deploy/**", "autonomy.toml", "bigbang.toml",
                  ".bigbang-framework.toml", "**/secrets/**")
HIGH_PATHS = ("AGENTS.md", "CLAUDE.md", "STACK.md", "PRODUTO.md", "DESIGN.md", "flags.toml", "tests/aceite/**", "tests/acceptance/**",
              "*lock*", "package.json", "pyproject.toml", "requirements*.txt", "go.mod", "go.sum", "Cargo.toml",
              "pom.xml", "*gradle*", "Gemfile", "composer.json", "*Dockerfile*", "compose.y*ml",
              "docker-compose*")
LOW_PATHS = ("docs/**", "*.md", "**/*.md", "LICENSE", ".gitignore")
# Flash: the agent approves common work; these gates always go to the owner, and so does anything at or above the
# listed risk.
FLASH_OWNER_GATES = ("selection", "cancel")
FLASH_OWNER_FROM = {"refinement": "critical", "prototype": "critical", "qa": "high", "publish": "high",
                    "flag": "high", "tests": "critical", "pr": "critical", "backlog": "high"}
DEFAULT_LIMITS = {"attempts": 3, "expedite": 1, "epics_in_progress": 2, "tasks_per_session": 1, "lease_hours": 24}
CONTRACT_KEYS = {"version", "targets", "risk", "gates", "flags", "wip", "attempts", "max_cost_usd",
                 "publish_window", "expires"}
WINDOW = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")


def mode(config):
    """Effective mode from a v3 or legacy configuration mapping."""
    project = config.get("project") if isinstance(config.get("project"), dict) else None
    if project and project.get("mode") in MODES:
        return project["mode"]
    legacy = (config.get("projeto") or {}).get("modo", "padrao")
    return {"padrao": "normal", "flash": "flash"}.get(legacy, "normal")


def _rank(risk):
    return RISKS.index(risk) if risk in RISKS else len(RISKS) - 1  # unknown counts as critical


def approver(current_mode, gate, risk, contract=None):
    """'owner', 'agent' or 'blocked' for one gate. Unknown mode, gate or risk is treated as the strictest case."""
    if gate not in GATES or current_mode not in MODES:
        return "owner"
    if current_mode == "normal":
        return "owner"
    if current_mode == "flash":
        if gate in FLASH_OWNER_GATES or _rank(risk) >= _rank(FLASH_OWNER_FROM.get(gate, "low")):
            return "owner"
        return "agent"
    if not contract or gate not in contract.get("gates", []) or risk not in contract.get("risk", []):
        return "blocked"  # autonomy never widens itself beyond the contract
    if gate == "flag" and contract.get("flags") != "agent":
        return "owner"
    return "agent"


def _matches(path, patterns):
    parts = path.split("/")
    return any(fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase("/".join(parts[i:]), pattern)
               for pattern in patterns for i in range(len(parts)))


def risk_floor(paths, sensitive_paths=()):
    """The lowest risk a change can have, from the files it touches."""
    floor = "low"
    for path in paths:
        if _matches(path, CRITICAL_PATHS) or _matches(path, tuple(sensitive_paths)):
            return "critical"
        if _matches(path, HIGH_PATHS):
            floor = "high"
        elif not _matches(path, LOW_PATHS) and _rank(floor) < _rank("medium"):
            floor = "medium"
    return floor


AREA_RISK = {"area:auth": "critical", "area:data": "high", "area:infra": "high", "area:ci": "high"}


def _area_risk(labels, default):
    areas = [AREA_RISK.get(label, "medium") for label in labels if label.startswith("area:")]
    return max(areas, key=_rank) if areas else default


def planning_risk(labels):
    """Risk of a planning gate (no code yet): from the declared areas and risk:* labels; medium by default."""
    return effective_risk(labels, _area_risk(labels, "medium"))


def delivery_risk(labels, paths=(), sensitive_paths=()):
    """Risk of a QA or publication gate: the changed paths when known; without them, the areas, and high when
    nothing is declared (fail closed)."""
    floor = risk_floor(paths, sensitive_paths) if paths else _area_risk(labels, "high")
    return effective_risk(labels, floor)


def effective_risk(labels, floor):
    """The declared risk:* label may raise the floor, never lower it."""
    declared = [label.split(":", 1)[1] for label in labels if label.startswith("risk:")]
    return max([floor, *[risk for risk in declared if risk in RISKS]], key=_rank)


def limits(config):
    result = dict(DEFAULT_LIMITS)
    agents = config.get("agents") if isinstance(config.get("agents"), dict) else {}
    if isinstance(agents.get("tasks_per_agent"), int):
        result["tasks_per_session"] = agents["tasks_per_agent"]
    if isinstance(agents.get("lease_hours"), int):
        result["lease_hours"] = agents["lease_hours"]
    return result


def snapshot(policy_data):
    """(canonical JSON, short hash): the policy revision every receipt points to."""
    canonical = json.dumps(policy_data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def suite_on_promotion(current_mode, evidence_valid):
    """Promoting the same artifact repeats the suite only when the evidence is no longer valid (never in
    autonomous mode, which checks integrity and health instead)."""
    if current_mode == "autonomous":
        return False
    return not evidence_valid


def in_window(window, now):
    match = WINDOW.match(window or "")
    if not match:
        return False
    start = int(match.group(1)) * 60 + int(match.group(2))
    end = int(match.group(3)) * 60 + int(match.group(4))
    minute = now.astimezone(datetime.timezone.utc).hour * 60 + now.astimezone(datetime.timezone.utc).minute
    return start <= minute < end if start <= end else (minute >= start or minute < end)


def contract_problems(contract, today):
    """Validation of autonomy.toml (already parsed). Empty list = usable contract."""
    found = [f"autonomy.toml: chave desconhecida {key}" for key in sorted(set(contract) - CONTRACT_KEYS)]
    if contract.get("version") != 1:
        found.append("autonomy.toml: version deve ser 1")
    if not isinstance(contract.get("targets"), list) or not contract.get("targets"):
        found.append("autonomy.toml: targets deve listar os ambientes permitidos")
    bad_risk = [risk for risk in contract.get("risk", []) if risk not in RISKS]
    if not contract.get("risk") or bad_risk:
        found.append(f"autonomy.toml: risk deve listar classes de {', '.join(RISKS)}")
    bad_gates = [gate for gate in contract.get("gates", []) if gate not in GATES]
    if not contract.get("gates") or bad_gates:
        found.append(f"autonomy.toml: gates deve listar portões de {', '.join(GATES)}")
    if contract.get("flags") not in ("agent", "owner"):
        found.append("autonomy.toml: flags deve ser agent ou owner")
    for key in ("wip", "attempts", "max_cost_usd"):
        value = contract.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            found.append(f"autonomy.toml: {key} deve ser inteiro não negativo")
    if not WINDOW.match(str(contract.get("publish_window", ""))):
        found.append("autonomy.toml: publish_window no formato HH:MM-HH:MM (UTC)")
    try:
        expires = datetime.date.fromisoformat(str(contract.get("expires", "")))
        if expires < today:
            found.append("autonomy.toml: contrato vencido; o dono precisa renová-lo")
    except ValueError:
        found.append("autonomy.toml: expires deve ser uma data AAAA-MM-DD")
    return found
