"""Atomic locks in Git refs (ADR-0023): refs/bigbang/locks/<resource>. Creating a ref that already exists fails on
GitHub, and a non-fast-forward update fails too, so acquisition, expired takeover and renewal are compare-and-set
operations with one winner. Each lock commit message carries the record (owner, session, generation, expiry); the
generation is the fencing token: a session whose generation was replaced can no longer renew or release.

Only the controller writes these refs. They live outside refs/heads and refs/tags, so they are not branches."""
import datetime
import json
import re

from . import github
from .errors import EXIT_EXTERNAL_COMMAND, EXIT_INVALID_STATE, EXIT_USAGE, BbError

PREFIX = "refs/bigbang/locks/"
RESOURCE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
HEADER = "bb-lock"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class LockHeld(BbError):
    def __init__(self, record):
        holder = record.get("owner", "?") if record else "?"
        super().__init__(f"recurso em uso por {holder} (sessão {record.get('session', '?') if record else '?'}, "
                         f"até {record.get('expires', '?') if record else '?'})", EXIT_INVALID_STATE)
        self.record = record


class LockLost(BbError):
    def __init__(self, message):
        super().__init__(message, EXIT_INVALID_STATE)


def _iso(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def encode(record):
    return f"{HEADER}\n\n" + json.dumps(record, sort_keys=True, ensure_ascii=False)


def decode(message):
    """The record of a lock commit message, or None when the commit is not a Big Bang lock."""
    if not message or not message.startswith(HEADER + "\n\n"):
        return None
    try:
        record = json.loads(message[len(HEADER) + 2:])
    except json.JSONDecodeError:
        return None
    keys = {"resource", "owner", "session", "generation", "acquired", "expires", "state"}
    return record if isinstance(record, dict) and keys <= set(record) else None


def expired(record, now):
    return record.get("state") != "held" or _iso(now) >= record["expires"]


def gh_api(method, path, payload=None):
    """(status, body) of a GitHub REST call through gh; JSON bodies go through stdin."""
    import subprocess
    command = github.gh_command() + ["api", "-X", method, path, "-i"]
    data = None
    if payload is not None:
        command += ["--input", "-"]
        data = json.dumps(payload)
    try:
        completed = subprocess.run(command, input=data, capture_output=True, text=True, encoding="utf-8",
                                   check=False)
    except FileNotFoundError as exc:
        raise BbError("GitHub CLI (gh) não encontrado", EXIT_EXTERNAL_COMMAND) from exc
    head, _, body = completed.stdout.replace("\r\n", "\n").partition("\n\n")
    match = re.match(r"HTTP/\S+ (\d{3})", head)
    if not match:
        raise BbError(f"gh api {method} {path} falhou: {(completed.stderr or completed.stdout).strip()}",
                      EXIT_EXTERNAL_COMMAND)
    try:
        return int(match.group(1)), json.loads(body) if body.strip() else None
    except json.JSONDecodeError:
        return int(match.group(1)), None


class Locks:
    def __init__(self, repository, api=gh_api):
        self.repository, self.api = repository, api

    def _path(self, tail):
        return f"repos/{self.repository}/{tail}"

    def _call(self, method, tail, payload=None, accept=(200, 201, 204)):
        status, body = self.api(method, self._path(tail), payload)
        if status not in accept:
            raise BbError(f"GitHub respondeu {status} em {method} {tail}: {(body or {}).get('message', '')}",
                          EXIT_EXTERNAL_COMMAND)
        return status, body

    @staticmethod
    def _check(resource):
        if not isinstance(resource, str) or not RESOURCE.match(resource):
            raise BbError(f"nome de trava inválido: {resource!r} (minúsculas, números, . _ -)", EXIT_USAGE)

    def _commit(self, record, parent=None):
        _, commit = self._call("POST", "git/commits", {"message": encode(record), "tree": EMPTY_TREE,
                                                        "parents": [parent] if parent else []})
        return commit["sha"]

    def _head(self, resource):
        status, body = self._call("GET", f"git/ref/bigbang/locks/{resource}", accept=(200, 404))
        if status == 404:
            return None, None
        sha = body["object"]["sha"]
        _, commit = self._call("GET", f"git/commits/{sha}")
        record = decode(commit.get("message"))
        if record is None or record.get("resource") != resource:
            raise BbError(f"{PREFIX}{resource} não contém uma trava do Big Bang; confira a ref", EXIT_INVALID_STATE)
        return sha, record

    def current(self, resource):
        """The live record, or None when free (a released tombstone also counts as free)."""
        self._check(resource)
        _, record = self._head(resource)
        return record if record and record.get("state") == "held" else None

    def _record(self, resource, owner, session, generation, hours, now):
        return {"resource": resource, "owner": owner, "session": session, "generation": generation,
                "acquired": _iso(now), "expires": _iso(now + datetime.timedelta(hours=hours)), "state": "held"}

    def acquire(self, resource, owner, session, *, hours, now, take_expired=False):
        """Create the lock, or take a released one. An expired lock that was not released is taken only with
        take_expired (the owner's order); a live lock never is."""
        self._check(resource)
        record = self._record(resource, owner, session, 1, hours, now)
        status, body = self._call("POST", "git/refs", {"ref": PREFIX + resource, "sha": self._commit(record)},
                                  accept=(201, 422))
        if status == 201:
            return record
        head, current = self._head(resource)
        if current is None:
            raise BbError(f"a trava {resource} não pôde ser criada: {(body or {}).get('message', '')}",
                          EXIT_EXTERNAL_COMMAND)
        if current.get("state") == "held" and (not expired(current, now) or not take_expired):
            raise LockHeld(current)
        return self.take_over(resource, head, owner, session, hours=hours, now=now, take_expired=take_expired)

    def take_over(self, resource, expected_head, owner, session, *, hours, now, take_expired=False):
        """Replace a released lock (or an expired one, with take_expired) whose head is `expected_head`; fails if
        anyone moved it first and never replaces a live lock."""
        self._check(resource)
        head, current = self._head(resource)
        if current and current.get("state") == "held" and (not expired(current, now) or not take_expired):
            raise LockHeld(current)
        generation = (current or {}).get("generation", 0) + 1
        record = self._record(resource, owner, session, generation, hours, now)
        sha = self._commit(record, parent=expected_head)
        status, _ = self._call("PATCH", f"git/refs/bigbang/locks/{resource}", {"sha": sha, "force": False},
                               accept=(200, 422))
        if status == 422:
            raise LockHeld(self.current(resource) or current or {})
        return record

    def renew(self, resource, session, generation, *, hours, now):
        head, current = self._head(resource)
        if not current or current["session"] != session or current["generation"] != generation or \
                current.get("state") != "held":
            raise LockLost(f"a trava {resource} não pertence mais a esta sessão; reconcilie antes de continuar")
        if expired(current, now):
            raise LockLost(f"a posse de {resource} venceu: só o dono pode mandar retomá-la (--force-claim)")
        record = dict(current, expires=_iso(now + datetime.timedelta(hours=hours)))
        status, _ = self._call("PATCH", f"git/refs/bigbang/locks/{resource}",
                               {"sha": self._commit(record, parent=head), "force": False}, accept=(200, 422))
        if status == 422:
            raise LockLost(f"a trava {resource} mudou durante a renovação")
        return record

    def release(self, resource, session, generation, *, now):
        head, current = self._head(resource)
        if not current or current["session"] != session or current["generation"] != generation:
            raise LockLost(f"a trava {resource} não pertence a esta sessão; nada foi liberado")
        tombstone = dict(current, state="released", expires=_iso(now))
        status, _ = self._call("PATCH", f"git/refs/bigbang/locks/{resource}",
                               {"sha": self._commit(tombstone, parent=head), "force": False}, accept=(200, 422))
        if status == 422:
            raise LockLost(f"a trava {resource} mudou durante a liberação")
        # The tombstone stays for good: deleting it could remove a lock taken right after, and keeping it keeps the
        # generations monotonic. A released lock counts as free (current() returns None).

    def all(self, resources=None):
        """{resource: record} of the lock refs (held, expired or tombstone), all or only the given resources."""
        _, refs = self._call("GET", "git/matching-refs/bigbang/locks/")
        result = {}
        for ref in refs or []:
            resource = ref["ref"][len(PREFIX):]
            if resources is not None and resource not in resources:
                continue
            _, commit = self._call("GET", f"git/commits/{ref['object']['sha']}")
            record = decode(commit.get("message"))
            if record:
                result[resource] = record
        return result
