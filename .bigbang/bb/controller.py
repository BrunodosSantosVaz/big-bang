"""The v3 controller (ADR-0023/0026): turns GitHub events into validated board moves. It never decides anything
the rules do not allow: every move goes through board.move (states + policy + receipt), so a replayed or out-of-order
event is either a no-op or refused with its reason. Dragging a card on a user Project emits no event; the schedule
reconciles the board with the receipts instead."""
import datetime
import re

from . import board, claims, config as config_module, names
from .errors import BbError
from .locks import expired

TASK_BRANCH = re.compile(r"^(test|feature|docs|fix|hotfix)/(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*$")
CONTROLLER = "controller"
AUTO_ADVANCE = {"Refinement": ("Prototyping", "Ready"), "Prototyping": ("Ready",), "QA": ("Releasing",)}


def _now(now):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _try(client, project, config, number, target, *, actor=CONTROLLER, **kwargs):
    """Move if the rules allow it now; returns the receipt, or None when refused (refusal is not an error here)."""
    try:
        return board.move(client, project, config, number, target, actor, **kwargs)
    except BbError:
        return None


def _state(client, config, number):
    return board.current_state(client, number, {config_module.get(config, "project.owner")})


def _issue_of(branch):
    match = TASK_BRANCH.match(branch or "")
    return int(match.group(2)) if match else None


def release_on_merge(client, number, *, now=None):
    """The merge concludes the claim: release the lock with its own record and drop the projection labels."""
    now = _now(now)
    lock_api = client.locks()
    current = lock_api.current(f"issue-{number}")
    if current:
        lock_api.release(f"issue-{number}", current["session"], current["generation"], now=now)
    for label in client.issue(number)["labels"]:
        if label.startswith(("agent:", "person:")) or label == "stale":
            client.remove_label(number, label)


def handle(client, project, config, event, payload, *, now=None):
    """Apply one event; returns the list of (issue, target) moves made."""
    now = _now(now)
    action = payload.get("action")
    done = []

    def advance(number, target, **kwargs):
        receipt = _try(client, project, config, number, target, now=now, **kwargs)
        if receipt:
            done.append((number, target))
        return receipt

    if event == "issues":
        number = payload["issue"]["number"]
        if action in ("opened", "reopened", "edited"):
            issue = client.issue(number)
            state = _state(client, config, number)
            if issue and board.states.kind(set(issue["labels"])) and project.get(number, "Status") != state:
                project.add(number)
                project.set(number, "Status", state)
                done.append((number, state))
        elif action == "labeled" and names.label((payload.get("label") or {}).get("name", ""), "v3") in \
                set(names.DECISIONS) | {"prototype:required", "prototype:waived", "flag:required", "flag:waived"}:
            for target in AUTO_ADVANCE.get(_state(client, config, number), ()):
                if advance(number, target):
                    break
    elif event == "push":
        number = _issue_of((payload.get("ref") or "").removeprefix("refs/heads/"))
        if number and _state(client, config, number) == "Todo":
            advance(number, "Coding")
    elif event == "pull_request":
        pull = payload.get("pull_request") or {}
        number = _issue_of((pull.get("head") or {}).get("ref"))
        if number is None:
            return done
        state = _state(client, config, number)
        if action in ("opened", "reopened", "ready_for_review") and not pull.get("draft"):
            if state in ("Todo", "Selected"):
                advance(number, "Coding")
            advance(number, "In Review", facts={"pr_open": True})
        elif action == "closed" and pull.get("merged"):
            if state == "Coding":
                advance(number, "In Review", facts={"pr_open": True})
            for target in ("Done", "QA"):
                if advance(number, target, facts={"pr_merged": True}):
                    break
            release_on_merge(client, number, now=now)
        elif action == "closed":
            advance(number, "Coding", facts={"pr_open": False})
    elif event == "schedule":
        for number, _, expected in board.reconcile(client, project, config, now=now):
            done.append((number, expected))
        stale_issues = {item["issue"] for item in claims.stale(client, now=now)}
        for issue in client.issues("open"):
            labeled = "stale" in issue["labels"]
            if issue["number"] in stale_issues and not labeled:
                client.add_labels(issue["number"], ["stale"])
            elif labeled and issue["number"] not in stale_issues:
                live = client.locks().current(f"issue-{issue['number']}")
                if live and not expired(live, now):
                    client.remove_label(issue["number"], "stale")
    return done
