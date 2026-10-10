"""v3 claims (ADR-0023): one protocol for people and agents, at any stage (refinement, prototype, code).

The lock refs/bigbang/locks/issue-<n> is the claim; the label agent:<name> or person:<login> is only its
projection, and a receipt records each claim and release. A claim has a lease (agents.lease_hours) renewed by
`bb renew`; a session whose lock was taken over after expiry loses its generation and can no longer renew, release
or conclude. Legacy projects keep the optimistic protocol of ownership.py."""
import datetime
import re
import uuid

from . import config as config_module
from . import names, policy, receipts
from .errors import EXIT_INVALID_STATE, EXIT_USAGE, BbError
from .locks import LockHeld, LockLost, expired

LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
LABEL_COLORS = {"agent": ("5319E7", "Posse de tarefa por IA (projeção da trava)"),
                "person": ("0E8A16", "Posse de tarefa por pessoa (projeção da trava)")}


def is_v3(config):
    """v3 claims once the project runs the grouping workflow or its labels were migrated to English."""
    try:
        return (config_module.get(config, "workflow.model") == "grouping" or
                names.label_dialect(config) == "v3")
    except BbError:
        return False


def _now(now):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _iso(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _label(name, person):
    return f"{'person' if person else 'agent'}:{name}"


def _owner(name, person):
    """The lock owner: people and agents never share a key, even with the same spelling."""
    return f"person:{name}" if person else name


def _check_name(config, name, person):
    if person:
        if not LOGIN.match(name or ""):
            raise BbError(f"login do GitHub inválido: {name!r}", EXIT_USAGE)
        return
    allowed = config_module.get(config, "agents.names")
    if name not in allowed:
        raise BbError(f"{name!r} não está em agents.names ({', '.join(allowed)})", EXIT_USAGE)


def _open_issue(client, number):
    issue = client.issue(number)
    if not issue or issue["pull_request"] or issue["state"] != "open":
        raise BbError(f"#{number} não é uma issue aberta", EXIT_INVALID_STATE)
    return issue


def _blockers(client, number):
    open_blockers = [blocker["number"] for blocker in client.blocked_by(number) if blocker["state"] == "open"]
    if open_blockers:
        raise BbError(f"#{number} depende de " + ", ".join(f"#{n}" for n in open_blockers) + " ainda aberta(s)",
                      EXIT_INVALID_STATE)


def _held_by(client, owner, now):
    return sorted(int(resource.split("-", 1)[1]) for resource, record in client.locks().all().items()
                  if resource.startswith("issue-") and record.get("owner") == owner and not expired(record, now))


def _record(client, number, receipt):
    client.comment(number, receipts.render(receipt))


def claim(client, config, number, name, *, person=False, now=None):
    """Acquire the lock of an issue and project it; returns the local receipt of the session."""
    now = _now(now)
    _check_name(config, name, person)
    _open_issue(client, number)
    _blockers(client, number)
    limit = policy.limits(config)["tasks_per_session"]
    held = [n for n in _held_by(client, _owner(name, person), now) if n != number]
    if len(held) >= limit:
        raise BbError(f"{name} atingiu o limite de {limit} posse(s): " + ", ".join(f"#{n}" for n in held),
                      EXIT_INVALID_STATE)
    session = str(uuid.uuid4())
    try:
        record = client.locks().acquire(f"issue-{number}", _owner(name, person), session,
                                        hours=policy.limits(config)["lease_hours"], now=now)
    except LockHeld as held:
        if held.record and expired(held.record, now):
            raise BbError(f"#{number}: a posse de {held.record.get('owner')} venceu em {held.record.get('expires')}; "
                          f"só o dono pode mandar retomá-la (bb claim {number} {name} --force-claim --quote "
                          f"\"<frase do dono>\")", EXIT_INVALID_STATE) from held
        raise
    return _project(client, number, name, person, session, record, now)


def _project(client, number, name, person, session, record, now):
    kind = "person" if person else "agent"
    client.ensure_label(_label(name, person), *LABEL_COLORS[kind])
    client.add_labels(number, [_label(name, person)])
    _record(client, number, {"kind": "claim", "event_id": f"claim-{session}", "issue": number, "actor": name,
                             "at": _iso(now), "resource": f"issue-{number}", "session": session,
                             "generation": record["generation"], "expires": record["expires"]})
    return {"issue": number, "name": name, "person": person, "session": session,
            "generation": record["generation"], "expires": record["expires"]}


def renew(client, config, receipt, *, now=None):
    now = _now(now)
    record = client.locks().renew(f"issue-{receipt['issue']}", receipt["session"], receipt["generation"],
                                  hours=policy.limits(config)["lease_hours"], now=now)
    return dict(receipt, expires=record["expires"])


def unclaim(client, config, receipt, *, now=None, reason="liberada pela sessão dona"):
    now = _now(now)
    number = receipt["issue"]
    client.locks().release(f"issue-{number}", receipt["session"], receipt["generation"], now=now)
    client.remove_label(number, _label(receipt["name"], receipt.get("person", False)))
    _record(client, number, {"kind": "release", "event_id": f"release-{receipt['session']}", "issue": number,
                             "actor": receipt["name"], "at": _iso(now), "resource": f"issue-{number}",
                             "session": receipt["session"], "generation": receipt["generation"], "reason": reason})


def force(client, config, number, name, quote, *, person=False, now=None):
    """Take over an EXPIRED claim by the owner's order (recorded verbatim); a live claim is never forced."""
    now = _now(now)
    if not quote or not quote.strip():
        raise BbError("retomar uma posse exige a frase do dono (--quote)", EXIT_USAGE)
    _check_name(config, name, person)
    _open_issue(client, number)
    lock_api = client.locks()
    current = lock_api.current(f"issue-{number}")
    if current and not expired(current, now):
        raise BbError(f"#{number}: posse de {current['owner']} ainda válida até {current['expires']}; nada foi "
                      f"retomado", EXIT_INVALID_STATE)
    session = str(uuid.uuid4())
    record = lock_api.acquire(f"issue-{number}", _owner(name, person), session,
                              hours=policy.limits(config)["lease_hours"], now=now, take_expired=True)
    client.comment(number, f"**Ordem do dono para retomar a posse** (`{name}`):\n\n" +
                   "\n".join("> " + line for line in quote.strip().splitlines()))
    if current:
        for label in client.issue(number)["labels"]:
            previous = current["owner"].removeprefix("person:")
            if label in (_label(previous, False), _label(previous, True)):
                client.remove_label(number, label)
    return _project(client, number, name, person, session, record, now)


def stale(client, *, now=None):
    """Held claims whose lease expired: the controller projects them as `stale`; nobody's work is touched."""
    now = _now(now)
    return [{"issue": int(resource.split("-", 1)[1]), "owner": record["owner"].removeprefix("person:"),
             "expires": record["expires"],
             "generation": record["generation"]}
            for resource, record in sorted(client.locks().all().items())
            if resource.startswith("issue-") and record.get("state") == "held" and expired(record, now)]


__all__ = ["LockLost", "claim", "force", "is_v3", "renew", "stale", "unclaim"]
