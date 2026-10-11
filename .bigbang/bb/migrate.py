"""Guided migration to the v3 (plan section 8, ADR-0024): four parts run in order, each by its own reviewed PR, each
with a dry run, a snapshot and a way back. Nothing is deleted: old labels stay until the end of the migration and the
old boards are only archived by the owner after a cycle without divergence. `bb update` alone never migrates."""
import datetime
import json
import os
import re

from . import board, names, policy, receipts, states
from . import config as config_module
from .errors import EXIT_INVALID_STATE, EXIT_USAGE, BbError
from .paths import config_path, read_text, write_text

PARTS = ("config", "labels", "board", "workflow")
MIGRATION_ACTOR = "migration"
# Inherited by systems founded before #236: the framework's own project section, without markers.
FRAMEWORK_QUOTE = re.compile(r"(?ms)^> \*\*Se este é o repositório `BrunodosSantosVaz/big-bang`\*\*.*?(?=^\S|\Z)")
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
        with open(snapshot, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def _load_snapshot(snapshot):
    if not snapshot or not os.path.exists(snapshot):
        raise BbError("a volta precisa do snapshot gravado na migração (--snapshot)", EXIT_USAGE)
    with open(snapshot, encoding="utf-8") as handle:
        return json.load(handle)


# --- config ----------------------------------------------------------------------------------------------------------

def clean_agents(text):
    """AGENTS.md without the framework's own project section inherited by old systems (no markers)."""
    return FRAMEWORK_MODE.sub("", FRAMEWORK_QUOTE.sub("", text)).replace("\n\n\n", "\n\n")


def config_part(root, *, dry_run=False):
    """bigbang.toml with the English names, same behavior (epic-branch, three boards, legacy labels)."""
    text = _config_text(root)
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
        if migrated != text:
            _write_config(root, migrated)
        if agents is not None and cleaned != agents:
            write_text(agents_path, cleaned)
    return {"part": "config", "changes": changes, "next": "rode bb generate, abra o PR e, depois do merge, "
                                                           "bb migrate labels"}


# --- labels ----------------------------------------------------------------------------------------------------------

def _labels_of(client):
    return {label["name"] for label in client.paginate("labels")}


def labels_part(client, root, *, snapshot=None, dry_run=False, rollback=False):
    """Legacy labels renamed to the v3 names (the issues keep them), copied when both exist, the v3 catalog
    completed; replaced labels (tem-dependencia, prioridade:*) are reported, never removed here."""
    text = _config_text(root)
    config = config_module.load(root)
    if rollback:
        data = _load_snapshot(snapshot)
        if not dry_run:
            for legacy, v3 in data["renamed"].items():
                client.call("PATCH", f"labels/{v3.replace(':', '%3A')}", {"new_name": legacy})
            for v3, numbers in data["copied"].items():
                for number in numbers:
                    client.remove_label(number, v3)
            _write_config(root, set_key(text, "board", "labels", "legacy"))
        return {"part": "labels", "rollback": True, "renamed": data["renamed"], "copied": data["copied"]}
    _require(config, [(config_module.dialect(config_module.parse(text)) == "v3",
                       "rode antes bb migrate config (bigbang.toml em inglês)")])
    existing = _labels_of(client)
    renamed, copied = [], {}
    for legacy, v3 in sorted(names.LABELS.items()):
        if legacy == v3 or legacy not in existing:
            continue
        if v3 not in existing:
            renamed.append((legacy, v3))
        else:
            numbers = [issue["number"] for issue in client.issues("all", labels=[legacy])
                       if v3 not in issue["labels"]]
            if numbers:
                copied[v3] = numbers
    replaced = {}
    for legacy in sorted(names.LABELS_REPLACED):
        if legacy in existing:
            replaced[legacy] = [issue["number"] for issue in client.issues("open", labels=[legacy])]
    report = {"part": "labels", "renamed": renamed, "copied": copied, "replaced": replaced,
              "next": "abra o PR com o bigbang.toml e, depois do merge, bb migrate board"}
    if dry_run:
        return report
    _save(snapshot, {"part": "labels", "renamed": dict(renamed), "copied": copied, "replaced": replaced,
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


def _claimed(labels):
    return any(label.startswith(("ia:", "agent:", "person:")) for label in labels)


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
            return "Done" if facts["closed"] else "Releasing"
    if role == EXECUTION:
        if column in ("A fazer", "Feature"):
            return "Todo"
        if column == "Code":
            return "Coding" if _claimed(labels) else "Todo"
        if column in ("CI/PR", "Validar PR"):
            return "In Review" if facts["open_pr"] else ("Coding" if _claimed(labels) else "Todo")
        if column in ("Pronto", "Concluído"):
            return "Done" if facts["closed"] else "In Review"
    if role == BUGS:
        if column == "Novo":
            return "Brainstorm"
        if column == "Em correção":
            return "Coding" if _claimed(labels) else "Selected"
        if column in ("CI/PR", "Validar PR"):
            return "In Review" if facts["open_pr"] else ("Coding" if _claimed(labels) else "Selected")
        if column == "Homologação":
            return "QA"
        if column == "Corrigido":
            return "Done" if facts["closed"] else "Releasing"
    return states.INITIAL.get(card_kind, "Brainstorm") if hasattr(states, "INITIAL") else "Brainstorm"


def _facts(client, issue, candidate_tags):
    number = issue["number"]
    children = client.sub_issues(number)
    pulls = client.pulls(state="open")
    milestone = issue.get("milestone")
    version = milestone[1:] if isinstance(milestone, str) and milestone.startswith("v") else None
    return {"labels": set(issue["labels"]), "closed": issue["state"] == "closed",
            "open_children": any(child["state"] == "open" for child in children),
            "epic_branch": bool(client.branches(f"epico/{number}-")),
            "candidate": bool(version and any(tag.startswith(f"v{version}-rc.") for tag in candidate_tags)),
            "open_pr": any(re.match(rf"^[a-z]+/{number}-", pull["head"]) for pull in pulls)}


def board_part(client, root, *, open_project, create_project, snapshot=None, dry_run=False, rollback=False,
               now=None):
    """Snapshot of the three boards, single Project, every card mapped by evidence with a migration receipt, then
    the switch in bigbang.toml. The old boards are left untouched."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    text = _config_text(root)
    config = config_module.load(root)
    if rollback:
        data = _load_snapshot(snapshot)
        if not dry_run:
            restored = set_key(drop_key(text, "board", "number"), "board", "model", "three-boards")
            for role in (PLANNING, EXECUTION, BUGS):
                restored = set_key(restored, "board", role, data["boards"][role])
            _write_config(root, restored)
        return {"part": "board", "rollback": True, "boards": data["boards"]}
    _require(config, [(config_module.dialect(config_module.parse(text)) == "v3", "rode antes bb migrate config"),
                      (config_module.get(config, "board.labels") == "v3", "rode antes bb migrate labels")])
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
            mapped[card] = map_card(role, values.get("Status"), card_kind, _facts(client, issue, tags))
    report = {"part": "board", "mapped": mapped, "boards": boards,
              "next": "abra o PR com o bigbang.toml; arquive os painéis antigos depois de um ciclo sem divergência"}
    if dry_run:
        return report
    _save(snapshot, {"part": "board", "boards": boards, "items": items, "mapped": {str(k): v for k, v in mapped.items()},
                     "at": _iso(now)})
    number, project = create_project()
    board.ensure_fields(project)
    _, policy_hash = policy.snapshot({"mode": policy.mode(config), "limits": policy.limits(config)})
    for card, state in sorted(mapped.items()):
        history = receipts.parse(client.comments(card), {owner})
        if not any(r["kind"] in ("transition", "rejection") for r in history):
            card_kind = states.kind(set(client.issue(card)["labels"]))
            initial = board.INITIAL.get(card_kind, "Brainstorm")
            if state != initial:
                client.comment(card, receipts.render({
                    "kind": "transition", "event_id": f"migrate-{card}", "issue": card, "actor": MIGRATION_ACTOR,
                    "at": _iso(now), "from": initial, "to": state, "policy": policy_hash}))
        project.add(card)
        project.set(card, "Status", board.current_state(client, card, {owner}))
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
        f"à branch main (gh api -X PUT repos/{repository}/environments/production); o producao antigo fica até a "
        "primeira publicação conferida.",
        f"Segredo e variáveis: gh secret set PROJECT_TOKEN --repo {repository} (o mesmo token de PROJETO_TOKEN); "
        f"gh variable set PROJECT_OWNER --repo {repository} --body <dono>; gh variable set PROJECT_NUMBER --repo "
        f"{repository} --body {config_module.get(config, 'board.number')}.",
    ]


def workflow_part(client, root, *, dry_run=False, rollback=False):
    """Epic-branch → grouping, only between sprints: no epico/* branch may carry work not merged into develop."""
    text = _config_text(root)
    config = config_module.load(root)
    if rollback:
        if not dry_run:
            _write_config(root, set_key(text, "workflow", "model", "epic-branch"))
        return {"part": "workflow", "rollback": True}
    _require(config, [(config_module.dialect(config_module.parse(text)) == "v3", "rode antes bb migrate config"),
                      (config_module.get(config, "board.labels") == "v3", "rode antes bb migrate labels"),
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
    if not dry_run:
        _write_config(root, set_key(text, "workflow", "model", "grouping"))
    return report
