"""Flows of the grouping workflow (ADR-0022/0026): sprint start, branches from develop, merge rules and release
cut. Every board move goes through board.move; every GitHub call through the injectable client."""
import datetime
import os
import re

from . import acceptance, board, flags, names, pipeline, states
from . import config as config_module
from .errors import EXIT_INVALID_STATE, BbError

CONTROLLER = "controller"
MARKER = re.compile(r"<!-- bb:sprint epic=(\d+) role=([a-z]+(?:-\d+)?) -->")
INHERITED = ("review:", "tests-review:", "risk:", "area:", "no-release", "security", "owner:ai-review")
PREFIX = {"type:test": "test", "type:task": "feature", "type:docs": "docs"}


def _trusted(config):
    return {config_module.get(config, "project.owner")}


def _sprint_option(project, date):
    options = project.fields().get("Sprint", {}).get("options", [])
    today = [option for option in options if option.startswith("Sprint ") and option.endswith(f"· {date.isoformat()}")]
    if today:
        return today[0], options
    number = 1 + sum(1 for option in options if option.startswith("Sprint "))
    name = f"Sprint {number} · {date.isoformat()}"
    project.ensure_field("Sprint", "SINGLE_SELECT", options + [name])
    return name, options + [name]


def _children_by_role(client, epic):
    result = {}
    for child in client.sub_issues(epic):
        marker = MARKER.search(child["body"])
        if marker and int(marker.group(1)) == epic:
            result[marker.group(2)] = child
    return result


def _legacy_view(labels):
    return {names.label(label, "legacy") for label in labels} | set(labels)


def start_sprint(client, project, config, *, date, now=None, epics=None):
    """Start the sprint for every epic in Selected (or the listed ones): no epic branch; acceptance-test issue,
    one task per planned task and the docs issue as sub-issues with native dependencies; the test branch from
    develop; children in Todo with the Sprint; the epic in In Progress. Running again duplicates nothing."""
    trusted = _trusted(config)
    develop = client.branch_sha("develop")
    if develop is None:
        raise BbError("branch develop inexistente: a sprint nasce da develop", EXIT_INVALID_STATE)
    plan = []
    candidates = [issue for issue in client.issues("open") if states.kind(set(issue["labels"])) == "epic"]
    for epic in candidates:
        number = epic["number"]
        if epics is not None and number not in epics:
            continue
        if board.current_state(client, number, trusted, epic) != "Selected":
            continue
        problems = pipeline.readiness_problems(epic["body"], _legacy_view(epic["labels"]))
        if problems:
            message = "**Big Bang** · épico fora da sprint (Definition of Ready):\n" + "\n".join(
                f"- {p}" for p in problems)
            if message not in [c["body"] for c in client.comments(number)]:
                client.comment(number, message)
            continue
        sprint, _ = _sprint_option(project, date)
        inherited = sorted(label for label in epic["labels"] if label.startswith(INHERITED))
        existing = _children_by_role(client, number)
        tasks = pipeline.planned_tasks(epic["body"])

        def child(role, title, kind, body_extra=""):
            if role in existing:
                return existing[role]["number"]
            body = (f"Parte do épico #{number}.{body_extra}\n\n<!-- bb:sprint epic={number} role={role} -->")
            created = client.create_issue(title, body, [kind, *inherited])
            client.add_sub_issue(number, created)
            existing[role] = client.issue(created)
            return created

        test = child("test", f"Testes de aceite: {epic['title']}", "type:test",
                     " Um teste por critério de aceite, escrito antes das tarefas.")
        task_numbers = []
        for index, (title, _) in enumerate(tasks, start=1):
            task_numbers.append(child(f"task-{index}", title, "type:task"))
        docs = child("docs", f"Documentação: {epic['title']}", "type:docs", " Última tarefa do épico.")
        for index, (_, deps) in enumerate(tasks, start=1):
            blockers = [test] + [task_numbers[dep - 1] for dep in deps]
            _block(client, task_numbers[index - 1], blockers)
        _block(client, docs, task_numbers)
        for issue_number in [test, *task_numbers, docs]:
            project.add(issue_number)
            if project.get(issue_number, "Status") is None:
                project.set(issue_number, "Status", "Todo")
            project.set(issue_number, "Sprint", sprint)
        project.add(number)
        project.set(number, "Sprint", sprint)
        test_issue = client.issue(test)
        if not client.branches(f"test/{test}-"):
            client.create_branch(pipeline.branch_name("test", test, test_issue["title"]), develop)
        board.move(client, project, config, number, "In Progress", CONTROLLER, now=now,
                   event_id=f"sprint-{number}-{sprint}")
        plan.append({"epic": number, "sprint": sprint, "test": test, "tasks": task_numbers, "docs": docs})
    return plan


def _block(client, number, blockers):
    current = {blocker["number"] for blocker in client.blocked_by(number)}
    for blocker in blockers:
        if blocker not in current:
            client.add_blocked_by(number, blocker)


def create_branches(client, config, epic=None):
    """Branches from develop for every open child of an epic in progress whose blockers are all closed."""
    trusted = _trusted(config)
    develop = client.branch_sha("develop")
    created = []
    for parent in client.issues("open"):
        if states.kind(set(parent["labels"])) != "epic" or (epic and parent["number"] != epic):
            continue
        if board.current_state(client, parent["number"], trusted, parent) != "In Progress":
            continue
        for child in client.sub_issues(parent["number"]):
            prefix = next((PREFIX[label] for label in child["labels"] if label in PREFIX), None)
            if child["state"] != "open" or prefix is None or client.branches(f"{prefix}/{child['number']}-"):
                continue
            if any(blocker["state"] == "open" for blocker in client.blocked_by(child["number"])):
                continue
            name = pipeline.branch_name(prefix, child["number"], child["title"])
            if client.create_branch(name, develop):
                client.comment(child["number"], f"**Big Bang** · branch `{name}` criada a partir da `develop`.")
                created.append(name)
    return created


# --- merge ------------------------------------------------------------------------------------------------------------

REQUIRED_CHECKS = names.REQUIRED_CHECKS["v3"]


def _has(labels, v3_label):
    return v3_label in labels or names.label(v3_label, "legacy") in labels


def merge_pr(client, config, number):
    """Merge one PR into develop or a release branch when its rules, approval and gate are satisfied. Never main:
    main only receives a release (or maintenance) through the publish flows."""
    pull = client.pull(number)
    if not pull or pull["state"] != "open" or pull["draft"]:
        raise BbError(f"PR #{number} não está aberto e pronto", EXIT_INVALID_STATE)
    if pull["base"] == "main":
        raise BbError("a main só recebe release ou manutenção pelos botões de publicação", EXIT_INVALID_STATE)
    problem = pipeline.v3_branch_problem(pull["head"], pull["base"])
    if problem:
        raise BbError(problem, EXIT_INVALID_STATE)
    kind, issue_number = pipeline.branch_issue(pull["head"])
    labels = set(pull["labels"])
    issue = client.issue(issue_number) if issue_number else None
    if kind == "test" and issue and _has(set(issue["labels"]), "tests-review:human"):
        if not _has(labels, "approved:tests"):
            raise BbError("os testes de aceite são revisados pelo dono: falta approved:tests", EXIT_INVALID_STATE)
    elif not _has(labels, "pr:approved"):
        raise BbError("PR ainda não aprovado (pr:approved)", EXIT_INVALID_STATE)
    runs = {run["name"]: run for run in client.check_runs(pull["sha"])}
    missing = [name for name in REQUIRED_CHECKS
               if runs.get(name, {}).get("status") != "completed" or runs[name].get("conclusion") != "success"]
    if missing:
        raise BbError(f"check obrigatório não verde no SHA {pull['sha'][:10]}: {', '.join(missing)}",
                      EXIT_INVALID_STATE)
    client.merge_pull(number, pull["sha"])
    return create_branches(client, config) if pull["base"] == "develop" else []


# --- release cut --------------------------------------------------------------------------------------------------

STABLE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
MERGE_MESSAGE = re.compile(r"^Merge pull request #(\d+)")


def current_version(client):
    versions = [tuple(int(part) for part in match.groups()) for match in map(STABLE.match, client.tags()) if match]
    return ".".join(str(part) for part in max(versions)) if versions else "0.0.0"


def release_items(client, base="main", head="develop"):
    """(number, title, labels) of the PRs merged into `head` and not yet in `base` (CHANGELOG input)."""
    numbers = []
    for message in client.compare_messages(base, head):
        match = MERGE_MESSAGE.match(message)
        if match and int(match.group(1)) not in numbers:
            numbers.append(int(match.group(1)))
    return [(pull["number"], pull["title"], pull["labels"]) for pull in map(client.pull, numbers)
            if pull and pull["merged"]]


def cut_release(client, config, *, version=None, now=None):
    """Cut release/x.y.z from develop with everything merged since main: version from the PR titles, version lock,
    milestone on the epics and tasks. Returns the release manifest, or None when there is nothing to release."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    numbers = []
    for message in client.compare_messages("main", "develop"):
        match = MERGE_MESSAGE.match(message)
        if match and int(match.group(1)) not in numbers:
            numbers.append(int(match.group(1)))
    pulls = [pull for pull in (client.pull(number) for number in numbers) if pull and pull["merged"]]
    if not pulls:
        return None
    current = current_version(client)
    target = version or pipeline.next_version(current, [pull["title"] for pull in pulls],
                                              [pull["body"] for pull in pulls])
    if not pipeline.SEMVER.match(target):
        raise BbError(f"versão inválida: {target}", EXIT_INVALID_STATE)
    branch = f"release/{target}"
    if client.branch_sha(branch) or f"v{target}" in client.tags():
        raise BbError(f"a versão {target} já foi cortada ou publicada", EXIT_INVALID_STATE)
    client.locks().acquire(f"version-{target}", CONTROLLER, f"release-{target}", hours=24 * 30, now=now)
    develop = client.branch_sha("develop")
    client.create_branch(branch, develop)
    milestone = client.ensure_milestone(f"v{target}")
    issues, epics = set(), set()
    for pull in pulls:
        _, issue = pipeline.branch_issue(pull["head"])
        if issue and client.issue(issue):  # a branch may cite an issue that no longer exists
            issues.add(issue)
            parent = client.parent(issue)
            if parent:
                epics.add(parent["number"])
    for number in sorted(issues | epics):
        client.update_issue(number, milestone=milestone)
    return {"version": target, "previous": current, "branch": branch, "sha": develop, "milestone": milestone,
            "epics": sorted(epics), "issues": sorted(issues), "pulls": [pull["number"] for pull in pulls]}


def release_gate(client, config, root, epics, *, today, pending=None):
    """Why the release cannot ship: every epic approved or dark behind its flag; pending acceptance tests only
    for dark epics. `pending` maps issue -> marks (acceptance.pending_marks when None)."""
    path = os.path.join(root, "flags.toml")
    registered = flags.parse(open(path, encoding="utf-8").read(), today) if os.path.exists(path) else []
    decisions = {}
    for epic in epics:
        labels = set(client.issue(epic)["labels"])
        decisions[epic] = "approved" if _has(labels, "qa:approved") else "pending"
    if pending is None:
        marker = config_module.get(config, "tests.pending_marker")
        pending = {}
        for issue, location in acceptance.pending_marks(root, marker):
            pending.setdefault(issue, []).append(location)
    owners = {}
    for issue in pending:
        parent = client.parent(issue)
        owners[issue] = parent["number"] if parent else None
    return flags.release_problems(decisions, registered) + flags.pending_problems(owners, registered)
