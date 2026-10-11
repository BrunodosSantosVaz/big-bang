"""Guided migration to the v3 (plan section 8, ADR-0024): four parts run in order, each by its own reviewed PR, each
with a dry run, a snapshot and a way back. Nothing is deleted: old labels stay until the end of the migration and the
old boards are only archived by the owner after a cycle without divergence. `bb update` alone never migrates."""
import datetime
import json
import os
import re
import uuid
from urllib.parse import quote

from . import board, names, policy, receipts, states, ownership
from .locks import expired
from . import config as config_module
from .errors import EXIT_INVALID_STATE, EXIT_USAGE, BbError
from .paths import config_path, read_text, write_text

PARTS = ("config", "board", "workflow", "labels")
MIGRATION_ACTOR = "migration"
# Inherited by systems founded before #236: the framework's own project section, without markers.
FRAMEWORK_QUOTE = re.compile(
    r"(?m)^> \*\*Se este é o repositório `BrunodosSantosVaz/big-bang`\*\*[^\n]*(?:\n>[^\n]*)*(?:\n|$)")
FRAMEWORK_MODE = re.compile(r"(?ms)^### Modo do próprio framework\n.*?(?=^#{1,3} |\Z)")


def _iso(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _config_text(root):
    return read_text(config_path(root))


def _write_config(root, text):
    errors = config_module.validate(config_module.parse(text))
    if errors:
        raise BbError("bigbang.toml migrado ficou inválido:\n" + "\n".join(f"  - {e}" for e in errors),
                      EXIT_INVALID_STATE)
    write_text(config_path(root), text)


def _section_bounds(text, section):
    header = re.search(rf"^\[{re.escape(section)}\][^\n]*$", text, re.M)
    if not header:
        raise BbError(f"bigbang.toml sem a seção [{section}]", EXIT_INVALID_STATE)
    following = re.search(r"^\[", text[header.end():], re.M)
    return header.end(), header.end() + following.start() if following else len(text)


def set_key(text, section, key, value):
    """`key = value` inside [section]: replaced keeping its comment, or added right after the header."""
    start, end = _section_bounds(text, section)
    body = text[start:end]
    literal = json.dumps(value, ensure_ascii=False)
    pattern = re.compile(rf'^({re.escape(key)}\s*=\s*)("(?:[^"\\]|\\.)*"|[^#\n]*?)([ \t]*(?:#.*)?)$', re.M)
    if pattern.search(body):
        body = pattern.sub(lambda m: m.group(1) + literal + m.group(3), body, count=1)
    else:
        body = f"\n{key} = {literal}" + body
    return text[:start] + body + text[end:]


def drop_key(text, section, key):
    start, end = _section_bounds(text, section)
    body = re.sub(rf"(?m)^{re.escape(key)}\s*=[^\n]*\n?", "", text[start:end], count=1)
    return text[:start] + body + text[end:]


def _require(config, checks):
    found = [message for ok, message in checks if not ok]
    if found:
        raise BbError("migração fora de ordem:\n" + "\n".join(f"  - {m}" for m in found), EXIT_INVALID_STATE)


def _save(snapshot, data):
    if snapshot:
        try:
            with open(snapshot, "x", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        except OSError as exc:
            raise BbError("não foi possível criar o snapshot (não sobrescrevemos backups): " + str(exc), EXIT_USAGE)


def _load_snapshot(snapshot, part=None, repository=None):
    if not snapshot or not os.path.exists(snapshot):
        raise BbError("a volta precisa do snapshot gravado na migração (--snapshot)", EXIT_USAGE)
    try:
        with open(snapshot, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise BbError("snapshot ilegível: " + str(exc), EXIT_USAGE)
    if not isinstance(data, dict) or (part and (data.get("part") != part or data.get("repository") != repository)):
        raise BbError("snapshot de outra parte ou repositório; não é seguro restaurar", EXIT_USAGE)
    return data


def _save_project_number(snapshot, number, repository):
    """Record the created Project so an owner can disable its workflows and safely resume."""
    if not snapshot:
        return
    data = _load_snapshot(snapshot, "board", repository)
    data["project_number"] = number
    try:
        with open(snapshot, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as exc:
        raise BbError("não foi possível atualizar o snapshot do quadro: " + str(exc), EXIT_USAGE)


# --- config ----------------------------------------------------------------------------------------------------------

def clean_agents(text):
    """AGENTS.md without the framework's own project section inherited by old systems (no markers)."""
    return FRAMEWORK_MODE.sub("", FRAMEWORK_QUOTE.sub("", text)).replace("\n\n\n", "\n\n")


def _rollback_order(config, part):
    """Parts are undone in reverse order: an earlier part cannot go back while a later one is still applied."""
    applied = {"labels": config_module.get(config, "board.labels") == "v3",
               "workflow": config_module.get(config, "workflow.model") == "grouping",
               "board": config_module.get(config, "board.model") == "single"}
    order = ("config", "board", "workflow", "labels")
    later = [name for name in order[order.index(part) + 1:] if applied.get(name)]
    if later:
        raise BbError(f"volta fora de ordem: desfaça antes {', '.join(reversed(later))} (as partes voltam na ordem "
                      "inversa: labels, workflow, board, config)", EXIT_INVALID_STATE)


def config_part(root, *, snapshot=None, dry_run=False, rollback=False):
    """bigbang.toml with the English names, same behavior (epic-branch, three boards, legacy labels)."""
    text = _config_text(root)
    repository = config_module.get(config_module.load(root), "project.repository")
    if rollback:
        _rollback_order(config_module.load(root), "config")
        data = _load_snapshot(snapshot, "config", repository)
        if not dry_run:
            _write_config(root, data["config_before"])
            if data["agents_before"] is not None:
                write_text(os.path.join(root, "AGENTS.md"), data["agents_before"])
        return {"part": "config", "rollback": True}
    changes = []
    migrated = text
    if config_module.dialect(config_module.parse(text)) == "legacy":
        migrated = config_module.text_to_v3(text)
        changes.append("bigbang.toml com os nomes em inglês (comportamento igual: epic-branch e três painéis)")
    agents_path = os.path.join(root, "AGENTS.md")
    agents = read_text(agents_path) if os.path.exists(agents_path) else None
    cleaned = clean_agents(agents) if agents is not None else None
    if agents is not None and cleaned != agents:
        changes.append("AGENTS.md sem o trecho do próprio framework herdado na Fundação")
    if not dry_run:
        if changes:
            _save(snapshot, {"part": "config", "repository": repository, "config_before": text,
                             "agents_before": agents})
        if migrated != text:
            _write_config(root, migrated)
        if agents is not None and cleaned != agents:
            write_text(agents_path, cleaned)
    return {"part": "config", "changes": changes, "next": "rode bb generate, abra o PR e, depois do merge, "
                                                           "bb migrate board"}


# --- labels ----------------------------------------------------------------------------------------------------------

def _labels_of(client):
    return {label["name"] for label in client.paginate("labels")}


def labels_part(client, root, *, snapshot=None, dry_run=False, rollback=False):
    """Legacy labels renamed to the v3 names (the issues keep them), copied when both exist, the v3 catalog
    completed; replaced labels (tem-dependencia, prioridade:*) are reported, never removed here."""
    text = _config_text(root)
    config = config_module.load(root)
    if rollback:
        data = _load_snapshot(snapshot, "labels", config_module.get(config, "project.repository"))
        if not dry_run:
            existing = _labels_of(client)
            for legacy, v3 in data["renamed"].items():
                if v3 in existing and legacy not in existing:
                    client.call("PATCH", f"labels/{quote(v3, safe='')}", {"new_name": legacy})
            for v3, numbers in data["copied"].items():
                for number in numbers:
                    client.remove_label(number, v3)
            _write_config(root, set_key(text, "board", "labels", "legacy"))
        return {"part": "labels", "rollback": True, "renamed": data["renamed"], "copied": data["copied"]}
    _require(config, [(config_module.dialect(config_module.parse(text)) == "v3",
                       "rode antes bb migrate config (bigbang.toml em inglês)"),
                      (config_module.get(config, "workflow.model") == "grouping", "rode antes bb migrate workflow"),
                      (config_module.get(config, "board.model") == "single", "rode antes bb migrate board")])
    if config_module.get(config, "board.labels") == "v3":
        return {"part": "labels", "changes": [], "next": "labels já migradas"}
    existing = _labels_of(client)
    renamed, copied = [], {}
    for legacy, v3 in sorted(names.LABELS.items()):
        if legacy == v3 or legacy not in existing:
            continue
        if v3 not in existing:
            renamed.append((legacy, v3))
        else:
            numbers = [issue["number"] for issue in client.paginate("issues?state=all&labels=" + quote(legacy, safe=""))
                       if v3 not in {label["name"] for label in issue["labels"]}]
            if numbers:
                copied[v3] = numbers
    replaced = {}
    for legacy in sorted(names.LABELS_REPLACED):
        if legacy in existing:
            replaced[legacy] = [issue["number"] for issue in client.issues("open", labels=[legacy])]
    report = {"part": "labels", "renamed": renamed, "copied": copied, "replaced": replaced,
              "next": "abra o PR com o bigbang.toml; depois confira um ciclo completo antes de arquivar painéis antigos"}
    if dry_run:
        return report
    _save(snapshot, {"part": "labels", "repository": config_module.get(config, "project.repository"), "renamed": dict(renamed), "copied": copied, "replaced": replaced,
                     "labels_before": sorted(existing)})
    for legacy, v3 in renamed:
        client.call("PATCH", f"labels/{legacy.replace(':', '%3A')}", {"new_name": v3})
    for v3, numbers in copied.items():
        for number in numbers:
            client.add_labels(number, [v3])
    board.ensure_labels(client)
    _write_config(root, set_key(text, "board", "labels", "v3"))
    return report


# --- board -----------------------------------------------------------------------------------------------------------

PLANNING = "planning"
EXECUTION = "execution"
BUGS = "bugs"


def _has(labels, v3_label):
    return v3_label in labels or names.label(v3_label, "legacy") in labels


def _claimed(client, issue, config, now):
    labels = set(issue["labels"])
    if labels & {"stale", "parada"}:
        return False
    current = client.locks().current(f"issue-{issue['number']}")
    if current is not None:
        return current.get("state") == "held" and not expired(current, now)
    owner = config_module.get(config, "project.owner").casefold()
    comments = [c for c in client.comments(issue["number"])
                if (c.get("user") or {}).get("login", "").casefold() == owner]
    for comment in comments:
        match = ownership.CLAIM.search(comment.get("body") or "")
        if not match or f"ia:{match[1]}" not in labels:
            continue
        stamps = [comment.get("created_at")]
        for heartbeat in comments:
            push = ownership.PUSH.search(heartbeat.get("body") or "")
            if push and push[1] == match[2]:
                stamps.append(heartbeat.get("created_at"))
        try:
            last = max(ownership.timestamp(stamp) for stamp in stamps)
        except (TypeError, ValueError):
            continue
        if last <= now and now - last <= datetime.timedelta(hours=config_module.get(config, "agents.lease_hours")):
            return True
    return False


def map_card(role, column, card_kind, facts):
    """The v3 state of a card of an old board (plan 8.4): only with the evidence the state needs."""
    labels = facts["labels"]
    if role == PLANNING:
        if column in ("Brainstorm", "Backlog"):
            return column
        if column == "Backlog Refinement":
            return "Refinement"
        if column == "Validar protótipo":
            return "Prototyping" if _has(labels, "prototype:required") else "Refinement"
        if column == "Próxima sprint":
            prototype_ok = not _has(labels, "prototype:required") or _has(labels, "approved:prototype")
            return "Selected" if _has(labels, "approved:refinement") and prototype_ok else "Refinement"
        if column == "Em desenvolvimento":
            return "In Progress" if facts["open_children"] or facts["epic_branch"] else "Selected"
        if column == "Homologação":
            return "QA" if facts["candidate"] else "In Progress"
        if column == "Concluída":
            return "Done" if facts["closed"] and facts["published"] else "Releasing"
    if role == EXECUTION:
        if column in ("A fazer", "Feature"):
            return "Todo"
        if column == "Code":
            return "Coding" if facts["claimed"] else "Todo"
        if column in ("CI/PR", "Validar PR"):
            return "In Review" if facts["open_pr"] else ("Coding" if facts["claimed"] else "Todo")
        if column in ("Pronto", "Concluído"):
            return "Done" if facts["merged_pr"] and facts["grouping"] else "In Review"
    if role == BUGS:
        if column == "Novo":
            return "Brainstorm"
        if column == "Em correção":
            return "Coding" if facts["claimed"] else "Selected"
        if column in ("CI/PR", "Validar PR"):
            return "In Review" if facts["open_pr"] else ("Coding" if facts["claimed"] else "Selected")
        if column == "Homologação":
            return "QA" if facts["candidate"] else "In Review"
        if column == "Corrigido":
            return "Done" if facts["closed"] and facts["published"] else "Releasing"
    return states.INITIAL.get(card_kind, "Brainstorm") if hasattr(states, "INITIAL") else "Brainstorm"


def _facts(client, issue, candidate_tags, config, now):
    number = issue["number"]
    children = client.sub_issues(number)
    pulls = client.pulls(state="open")
    milestone = issue.get("milestone")
    matched = re.fullmatch(r"v?(\d+\.\d+\.\d+)", milestone) if isinstance(milestone, str) else None
    version = matched[1] if matched else None
    all_pulls = client.pulls(state="all")
    recorded = receipts.parse(client.comments(number), {config_module.get(config, "project.owner")})
    published = bool(version and f"v{version}" in candidate_tags) or any(
        r["kind"] == "publication" and r["result"] == "success"
        and r["environment"] in ("production", "producao")
        and (r["version"] in (version, f"v{version}") or str(r["version"]).startswith("maintenance-"))
        for r in recorded)
    return {"claimed": _claimed(client, issue, config, now), "published": published,
            "grouping": config_module.get(config, "workflow.model") == "grouping",
            "merged_pr": any(pull["merged"] and re.match(rf"^[a-z]+/{number}-", pull["head"]) for pull in all_pulls),
            "labels": set(issue["labels"]), "closed": issue["state"] == "closed",
            "open_children": any(child["state"] == "open" for child in children),
            "epic_branch": bool(client.branches(f"epico/{number}-")),
            "candidate": bool(version and any(tag.startswith(f"v{version}-rc.") for tag in candidate_tags)),
            "open_pr": any(re.match(rf"^[a-z]+/{number}-", pull["head"]) for pull in pulls)}


def board_part(client, root, *, open_project, create_project, snapshot=None, dry_run=False, rollback=False,
               project_number=None, now=None):
    """Snapshot of the three boards, single Project, every card mapped by evidence with a migration receipt, then
    the switch in bigbang.toml. The old boards are left untouched."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    text = _config_text(root)
    config = config_module.load(root)
    if rollback:
        _rollback_order(config, "board")
        data = _load_snapshot(snapshot, "board", config_module.get(config, "project.repository"))
        if not dry_run:
            restored = set_key(drop_key(text, "board", "number"), "board", "model", "three-boards")
            for role in (PLANNING, EXECUTION, BUGS):
                restored = set_key(restored, "board", role, data["boards"][role])
            _write_config(root, restored)
        return {"part": "board", "rollback": True, "boards": data["boards"]}
    _require(config, [(config_module.dialect(config_module.parse(text)) == "v3", "rode antes bb migrate config"),
                      (config_module.get(config, "board.labels") == "legacy", "as labels mudam por último")])
    owner = config_module.get(config, "project.owner")
    if config_module.get(config, "board.model") == "single":
        return {"part": "board", "mapped": {}, "changes": [], "next": "quadro já migrado"}
    boards = {role: config_module.get(config, f"board.{role}") for role in (PLANNING, EXECUTION, BUGS)}
    items, mapped = {}, {}
    tags = client.tags()
    for role, number in boards.items():
        if not number:
            continue
        cards = open_project(number).items()
        items[str(number)] = {str(card): values for card, values in cards.items()}
        for card, values in sorted(cards.items()):
            issue = client.issue(card)
            if not issue or issue["pull_request"]:
                continue
            card_kind = states.kind(set(issue["labels"]))
            if card_kind is None:
                continue
            mapped[card] = map_card(role, values.get("Status"), card_kind, _facts(client, issue, tags, config, now))
    report = {"part": "board", "mapped": mapped, "boards": boards,
              "next": "abra o PR com o bigbang.toml; arquive os painéis antigos depois de um ciclo sem divergência"}
    if dry_run:
        return report
    repository = config_module.get(config, "project.repository")
    if project_number is not None:
        data = _load_snapshot(snapshot, "board", repository)
        if data.get("boards") != boards or data.get("mapped") != {str(k): v for k, v in mapped.items()}:
            raise BbError("o mapa ou os quadros mudaram desde o snapshot; não é seguro retomar", EXIT_INVALID_STATE)
        if data.get("project_number") not in (None, project_number):
            raise BbError("o Project informado não corresponde ao snapshot", EXIT_INVALID_STATE)
        attempt = data["attempt"]
        number, project = project_number, open_project(project_number)
    else:
        attempt = uuid.uuid4().hex
        _save(snapshot, {"attempt": attempt, "part": "board", "repository": repository, "boards": boards,
                         "items": items, "mapped": {str(k): v for k, v in mapped.items()}, "at": _iso(now)})
        number, project = create_project()
        _save_project_number(snapshot, number, repository)
    active = [workflow for workflow in project.workflows() if workflow.get("enabled")]
    if active:
        workflow_names = ", ".join(workflow.get("name", "(sem nome)") for workflow in active)
        raise BbError(f"Project #{number} tem workflows embutidas ativas ({workflow_names}). Desative-as na interface "
                      f"do Project, em Workflows, e retome com `bb migrate board --project {number} --snapshot "
                      f"{snapshot} --yes`.", EXIT_INVALID_STATE)
    board.ensure_fields(project)
    _, policy_hash = policy.snapshot({"mode": policy.mode(config), "limits": policy.limits(config)})
    for card, state in sorted(mapped.items()):
        initial = board.current_state(client, card, {owner})
        client.comment(card, receipts.render({
            "kind": "transition", "event_id": f"migrate-{attempt}-{card}", "issue": card,
            "actor": MIGRATION_ACTOR, "at": _iso(now), "from": initial, "to": state, "policy": policy_hash}))
        project.add(card)
        project.set(card, "Status", state)
    observed = project.items(refresh=True)
    for card, state in sorted(mapped.items()):
        if observed.get(card, {}).get("Status") != state:
            project.set(card, "Status", state)
    confirmed = project.items(refresh=True)
    mismatches = {card: {"esperado": state, "observado": confirmed.get(card, {}).get("Status")}
                  for card, state in mapped.items() if confirmed.get(card, {}).get("Status") != state}
    if mismatches:
        raise BbError("confirmação final de Status divergiu; bigbang.toml permanece nos três quadros: "
                      + json.dumps(mismatches, ensure_ascii=False, sort_keys=True), EXIT_INVALID_STATE)
    migrated = set_key(text, "board", "model", "single")
    for role in (PLANNING, EXECUTION, BUGS):
        migrated = drop_key(migrated, "board", role)
    _write_config(root, set_key(migrated, "board", "number", number))
    return report


# --- workflow --------------------------------------------------------------------------------------------------------

def owner_steps(config):
    repository = config_module.get(config, "project.repository")
    return [
        f"Rulesets de main e develop em {repository}: troque os checks obrigatórios (check, regras, seguranca) pelo "
        "check único gate (Settings → Rules → Rulesets, ou gh api repos/" + repository + "/rulesets).",
        "Ambiente production: crie-o com os mesmos revisores obrigatórios e segredos do ambiente producao e restrito "
        f"à branch main. Leia gh api repos/{repository}/environments/producao, prepare e revise production.json "
        f"preservando reviewers, prevent_self_review e deployment_branch_policy; só então o dono executa "
        f"gh api -X PUT repos/{repository}/environments/production --input production.json. O producao antigo fica até a "
        "primeira publicação conferida.",
        f"Segredo e variáveis: gh secret set PROJECT_TOKEN --repo {repository} (o mesmo token de PROJETO_TOKEN); "
        f"gh variable set PROJECT_OWNER --repo {repository} --body <dono>; gh variable set PROJECT_NUMBER --repo "
        f"{repository} --body {config_module.get(config, 'board.number')}.",
    ]


def workflow_part(client, root, *, snapshot=None, dry_run=False, rollback=False):
    """Epic-branch → grouping, only between sprints: no epico/* branch may carry work not merged into develop."""
    text = _config_text(root)
    config = config_module.load(root)
    if rollback:
        _rollback_order(config, "workflow")
        data = _load_snapshot(snapshot, "workflow", config_module.get(config, "project.repository")) if snapshot else None
        if not dry_run:
            _write_config(root, data["config_before"] if data else set_key(text, "workflow", "model", "epic-branch"))
        return {"part": "workflow", "rollback": True}
    _require(config, [(config_module.dialect(config_module.parse(text)) == "v3", "rode antes bb migrate config"),
                      (config_module.get(config, "board.labels") == "legacy", "as labels mudam por último"),
                      (config_module.get(config, "board.model") == "single", "rode antes bb migrate board")])
    pending = []
    for branch in client.branches("epico/"):
        if client.ahead_by("develop", branch) > 0:
            pending.append(branch)
    if pending:
        raise BbError("épicos ainda trabalhando no modelo anterior: " + ", ".join(sorted(pending)) + ". Termine-os "
                      "no fluxo atual ou mescle a branch na develop com a feature flag desligada (se mudam o "
                      "artefato) e rode de novo", EXIT_INVALID_STATE)
    report = {"part": "workflow", "owner_steps": owner_steps(config),
              "next": "rode bb generate, abra o PR e, depois do merge, faça os passos do dono no GitHub"}
    if not dry_run and config_module.get(config, "workflow.model") != "grouping":
        _save(snapshot, {"part": "workflow", "repository": config_module.get(config, "project.repository"),
                         "config_before": text})
        _write_config(root, set_key(text, "workflow", "model", "grouping"))
    return report
