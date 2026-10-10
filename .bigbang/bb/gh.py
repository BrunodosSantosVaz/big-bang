"""GitHub client of the v3 flows (ADR-0026): every REST call goes through one injectable `api(method, path,
payload) -> (status, body)`, so the flows are tested against an in-memory GitHub with the same semantics. The real
transport is `gh api -i` (locks.gh_api), authenticated by the gh CLI."""
from urllib.parse import quote

from . import locks
from .errors import EXIT_EXTERNAL_COMMAND, BbError


def _labels(raw):
    return sorted(label["name"] if isinstance(label, dict) else label for label in raw.get("labels", []))


def normalize_issue(raw):
    return {"number": raw["number"], "id": raw.get("id"), "title": raw.get("title", ""), "body": raw.get("body") or "",
            "state": raw.get("state", "open").lower(), "state_reason": raw.get("state_reason"),
            "labels": _labels(raw), "pull_request": "pull_request" in raw, "comments": raw.get("comments", 0),
            "milestone": (raw.get("milestone") or {}).get("title")}


class GitHub:
    def __init__(self, repository, api=None):
        self.repository = repository
        self.api = api or locks.gh_api

    def call(self, method, tail, payload=None, accept=(200, 201, 204)):
        status, body = self.api(method, f"repos/{self.repository}/{tail}", payload)
        if status not in accept:
            message = (body or {}).get("message", "") if isinstance(body, dict) else ""
            raise BbError(f"GitHub respondeu {status} em {method} {tail}: {message}", EXIT_EXTERNAL_COMMAND)
        return status, body

    def paginate(self, tail):
        separator = "&" if "?" in tail else "?"
        result, page = [], 1
        while True:
            _, body = self.call("GET", f"{tail}{separator}per_page=100&page={page}")
            items = body if isinstance(body, list) else body.get("items", [])
            result.extend(items)
            if len(items) < 100:
                return result
            page += 1

    # --- issues -----------------------------------------------------------------------------------------------------

    def issue(self, number):
        status, body = self.call("GET", f"issues/{number}", accept=(200, 404))
        return normalize_issue(body) if status == 200 else None

    def issues(self, state="open", labels=None):
        tail = f"issues?state={state}" + (f"&labels={quote(','.join(labels))}" if labels else "")
        return [normalize_issue(raw) for raw in self.paginate(tail) if "pull_request" not in raw]

    def create_issue(self, title, body, labels=()):
        _, raw = self.call("POST", "issues", {"title": title, "body": body, "labels": list(labels)})
        return raw["number"]

    def update_issue(self, number, **fields):
        self.call("PATCH", f"issues/{number}", fields)

    def add_labels(self, number, labels):
        if labels:
            self.call("POST", f"issues/{number}/labels", {"labels": list(labels)})

    def remove_label(self, number, label):
        self.call("DELETE", f"issues/{number}/labels/{quote(label, safe='')}", accept=(200, 204, 404))

    def ensure_label(self, name, color, description):
        status, _ = self.call("POST", "labels", {"name": name, "color": color, "description": description},
                              accept=(201, 422))
        return status == 201

    def comments(self, number):
        return self.paginate(f"issues/{number}/comments")

    def comment(self, number, body):
        _, raw = self.call("POST", f"issues/{number}/comments", {"body": body})
        return raw["id"]

    # --- hierarchy and dependencies (native) ----------------------------------------------------------------------

    def sub_issues(self, number):
        return [normalize_issue(raw) for raw in self.paginate(f"issues/{number}/sub_issues")]

    def parent(self, number):
        status, body = self.call("GET", f"issues/{number}/parent", accept=(200, 404))
        return normalize_issue(body) if status == 200 and body else None

    def add_sub_issue(self, parent, child):
        child_id = self.issue(child)["id"]
        self.call("POST", f"issues/{parent}/sub_issues", {"sub_issue_id": child_id}, accept=(201, 422))

    def blocked_by(self, number):
        return [normalize_issue(raw) for raw in self.paginate(f"issues/{number}/dependencies/blocked_by")]

    def add_blocked_by(self, number, blocker):
        blocker_id = self.issue(blocker)["id"]
        self.call("POST", f"issues/{number}/dependencies/blocked_by", {"issue_id": blocker_id}, accept=(201, 422))

    # --- refs -----------------------------------------------------------------------------------------------------------

    def branches(self, prefix):
        _, refs = self.call("GET", f"git/matching-refs/heads/{prefix}")
        return [ref["ref"][len("refs/heads/"):] for ref in refs or []]

    def branch_sha(self, name):
        status, body = self.call("GET", f"git/ref/heads/{name}", accept=(200, 404))
        return body["object"]["sha"] if status == 200 else None

    def create_branch(self, name, sha):
        status, _ = self.call("POST", "git/refs", {"ref": f"refs/heads/{name}", "sha": sha}, accept=(201, 422))
        return status == 201

    def locks(self):
        return locks.Locks(self.repository, api=self.api)
