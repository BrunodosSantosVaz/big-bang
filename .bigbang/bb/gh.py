"""GitHub client of the v3 flows (ADR-0026): every REST call goes through one injectable `api(method, path,
payload) -> (status, body)`, so the flows are tested against an in-memory GitHub with the same semantics. The real
transport is `gh api -i` (locks.gh_api), authenticated by the gh CLI."""
import json
import subprocess
from urllib.parse import quote

from . import github

from . import locks
from .errors import EXIT_EXTERNAL_COMMAND, BbError


def _labels(raw):
    return sorted(label["name"] if isinstance(label, dict) else label for label in raw.get("labels", []))


def normalize_issue(raw):
    return {"number": raw["number"], "id": raw.get("id"), "title": raw.get("title", ""), "body": raw.get("body") or "",
            "state": raw.get("state", "open").lower(), "state_reason": raw.get("state_reason"),
            "labels": _labels(raw), "pull_request": "pull_request" in raw, "comments": raw.get("comments", 0),
            "created_at": raw.get("created_at"),
            "milestone": _milestone(raw.get("milestone"))}


def _milestone(value):
    if isinstance(value, dict):
        return value.get("title")
    return value


def _normalize_pull(raw):
    return {"number": raw["number"], "title": raw.get("title", ""), "body": raw.get("body") or "",
            "state": raw.get("state"), "merged": bool(raw.get("merged")), "draft": bool(raw.get("draft")),
            "labels": _labels(raw), "head": raw["head"]["ref"], "sha": raw["head"]["sha"],
            "base": raw["base"]["ref"]}


def graphql(query, variables=None):
    """data of a GitHub GraphQL call through `gh api graphql`; GraphQL errors become BbError."""
    command = github.gh_command() + ["api", "graphql", "--input", "-"]
    try:
        completed = subprocess.run(command, input=json.dumps({"query": query, "variables": variables or {}}),
                                   capture_output=True, text=True, encoding="utf-8", check=False)
    except FileNotFoundError as exc:
        raise BbError("GitHub CLI (gh) não encontrado", EXIT_EXTERNAL_COMMAND) from exc
    try:
        body = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        body = {}
    if completed.returncode or body.get("errors"):
        message = "; ".join(error.get("message", "") for error in body.get("errors", [])) or completed.stderr.strip()
        raise BbError(f"GitHub GraphQL falhou: {message}", EXIT_EXTERNAL_COMMAND)
    return body.get("data") or {}


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

    # --- repository controls ----------------------------------------------------------------------------------------

    def repository_info(self):
        status, body = self.api("GET", f"repos/{self.repository}", None)
        return body if status == 200 else None

    def user(self):
        status, body = self.api("GET", "user", None)
        return body if status == 200 else None

    def branch_rules(self, branch):
        return self.paginate(f"rules/branches/{branch}")

    def ruleset(self, number):
        status, body = self.call("GET", f"rulesets/{number}", accept=(200, 404))
        return body if status == 200 else None

    def environment(self, name):
        status, body = self.call("GET", f"environments/{name}", accept=(200, 404))
        return body if status == 200 else None

    def environment_branch_policies(self, name):
        _, body = self.call("GET", f"environments/{name}/deployment-branch-policies?per_page=100")
        return (body or {}).get("branch_policies", [])

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

    # --- pull requests, checks, comparisons ------------------------------------------------------------------------

    def pull(self, number):
        status, raw = self.call("GET", f"pulls/{number}", accept=(200, 404))
        if status == 404:
            return None
        return _normalize_pull(raw)

    def merge_pull(self, number, sha):
        """Merge commit, guarded by the exact head SHA (a newer push makes GitHub refuse)."""
        status, body = self.call("PUT", f"pulls/{number}/merge", {"merge_method": "merge", "sha": sha},
                                 accept=(200, 405, 409))
        if status != 200:
            raise BbError(f"merge do PR #{number} recusado pelo GitHub: {(body or {}).get('message', '')}",
                          EXIT_EXTERNAL_COMMAND)
        return body.get("sha")

    def pull_files(self, number):
        return self.paginate(f"pulls/{number}/files")

    def add_pr_labels(self, number, labels):
        self.add_labels(number, labels)  # a PR is an issue for labels

    def check_runs(self, sha):
        _, body = self.call("GET", f"commits/{sha}/check-runs?per_page=100")
        return body.get("check_runs", [])

    def compare_messages(self, base, head):
        _, body = self.call("GET", f"compare/{base}...{head}")
        return [commit["commit"]["message"] for commit in body.get("commits", [])]

    def tags(self):
        _, refs = self.call("GET", "git/matching-refs/tags/")
        return [ref["ref"][len("refs/tags/"):] for ref in refs or []]

    def ensure_milestone(self, title):
        for milestone in self.paginate("milestones?state=all"):
            if milestone["title"] == title:
                return milestone["number"]
        _, body = self.call("POST", "milestones", {"title": title})
        return body["number"]

    def milestone_number(self, title):
        for milestone in self.paginate("milestones?state=all"):
            if milestone["title"] == title:
                return milestone["number"]
        return None

    def close_milestone(self, number):
        self.call("PATCH", f"milestones/{number}", {"state": "closed"})

    def milestone_issues(self, number):
        return [normalize_issue(raw) for raw in self.paginate(f"issues?milestone={number}&state=all")
                if "pull_request" not in raw]

    def pulls(self, head=None, base=None, state="open"):
        owner = self.repository.split("/")[0]
        tail = f"pulls?state={state}" + (f"&head={owner}:{head}" if head else "") + (f"&base={base}" if base else "")
        return [_normalize_pull(raw) for raw in self.paginate(tail)]

    def create_pull(self, head, base, title, body):
        status, raw = self.call("POST", "pulls", {"head": head, "base": base, "title": title, "body": body},
                                accept=(201, 422))
        if status == 201:
            return raw["number"]
        existing = self.pulls(head=head, base=base)
        if existing:
            return existing[0]["number"]
        raise BbError(f"PR {head} → {base} não pôde ser aberto", EXIT_EXTERNAL_COMMAND)

    def merge_branches(self, base, head, message):
        """'merged', 'noop' (already contained) or 'conflict' (GitHub merges API)."""
        status, _ = self.call("POST", "merges", {"base": base, "head": head, "commit_message": message},
                              accept=(201, 204, 409))
        return {201: "merged", 204: "noop", 409: "conflict"}[status]

    def ahead_by(self, base, head):
        _, body = self.call("GET", f"compare/{base}...{head}")
        return body.get("ahead_by", len(body.get("commits", [])))

    def delete_ref(self, ref):
        self.call("DELETE", f"git/{ref}", accept=(204, 422))

    def all_branches(self):
        _, refs = self.call("GET", "git/matching-refs/heads/")
        return [ref["ref"][len("refs/heads/"):] for ref in refs or []]

    def locks(self):
        return locks.Locks(self.repository, api=self.api)
