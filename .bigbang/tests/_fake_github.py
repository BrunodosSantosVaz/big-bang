"""In-memory GitHub for the v3 flows (ADR-0026): the REST endpoints they use, with GitHub's semantics (422 on an
existing ref or a non-fast-forward update, 404 on missing objects, labels created on demand)."""
import hashlib
import json
import re


class FakeGitHub:
    def __init__(self, repository="dono/repo"):
        self.repository = repository
        self.issues, self.comments, self.labels = {}, {}, {}
        self.refs, self.commits = {}, {}
        self.parents, self.blockers = {}, {}
        self.pulls, self.checks, self.milestones, self.compares = {}, {}, {}, {}
        self.failures = set()  # (method, tail) answered with HTTP 500, to test partial failures
        self.author = "dona"  # login that authors new comments
        self.merges, self.contained, self.conflicts = [], set(), set()
        self.calls = []
        self.next_comment = 1000

    # --- helpers for tests ----------------------------------------------------------------------------------------

    def add_issue(self, number, title="x", labels=(), state="open", body="", parent=None, blocked_by=()):
        self.issues[number] = {"number": number, "id": 10_000 + number, "title": title, "body": body,
                               "state": state, "state_reason": None, "labels": [{"name": n} for n in labels],
                               "comments": 0, "milestone": None}
        for label in labels:
            self.labels.setdefault(label, {"name": label})
        if parent is not None:
            self.parents[number] = parent
        self.blockers[number] = list(blocked_by)
        return number

    def add_pull(self, number, head, base, title="feat: x", labels=(), sha=None, state="open", merged=False,
                 draft=False, body=""):
        self.pulls[number] = {"number": number, "title": title, "body": body, "state": state, "merged": merged,
                              "draft": draft, "labels": [{"name": n} for n in labels], "mergeable": True,
                              "head": {"ref": head, "sha": sha or f"{number:040d}"}, "base": {"ref": base}}
        return number

    def label_names(self, number):
        return sorted(label["name"] for label in self.issues[number]["labels"])

    def comment_bodies(self, number):
        return [comment["body"] for comment in self.comments.get(number, [])]

    # --- the API ------------------------------------------------------------------------------------------------------

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path))
        if path == "user":
            return 200, getattr(self, "user", None) or {"login": "dona"}
        if path.startswith("orgs/"):
            org = getattr(self, "orgs", {}).get(path[len("orgs/"):])
            return (200, org) if org else (404, {"message": "Not Found"})
        if path == f"repos/{self.repository}":
            repo = getattr(self, "repo", None)
            return (200, repo) if repo else (404, {"message": "Not Found"})
        prefix = f"repos/{self.repository}/"
        assert path.startswith(prefix), path
        tail, _, query = path[len(prefix):].partition("?")
        if (method, tail) in self.failures:
            return 500, {"message": "Server Error"}
        params = dict(item.split("=", 1) for item in query.split("&") if item)
        for pattern, handler in self.ROUTES:
            match = re.fullmatch(pattern, tail)
            if match and handler[0] == method:
                return getattr(self, handler[1])(params, payload, *match.groups())
        raise AssertionError(f"rota não simulada: {method} {tail}")

    ROUTES = [
        (r"issues", ("GET", "_list_issues")), (r"issues", ("POST", "_create_issue")),
        (r"issues/(\d+)", ("GET", "_get_issue")), (r"issues/(\d+)", ("PATCH", "_patch_issue")),
        (r"issues/(\d+)/labels", ("POST", "_add_labels")),
        (r"issues/(\d+)/labels/(.+)", ("DELETE", "_remove_label")),
        (r"labels", ("POST", "_create_label")),
        (r"issues/(\d+)/comments", ("GET", "_list_comments")), (r"issues/(\d+)/comments", ("POST", "_add_comment")),
        (r"issues/(\d+)/sub_issues", ("GET", "_list_sub")), (r"issues/(\d+)/sub_issues", ("POST", "_add_sub")),
        (r"issues/(\d+)/parent", ("GET", "_get_parent")),
        (r"issues/(\d+)/dependencies/blocked_by", ("GET", "_list_blockers")),
        (r"issues/(\d+)/dependencies/blocked_by", ("POST", "_add_blocker")),
        (r"git/matching-refs/(.*)", ("GET", "_matching_refs")),
        (r"git/ref/(.+)", ("GET", "_get_ref")),
        (r"git/refs", ("POST", "_create_ref")), (r"git/refs/(.+)", ("PATCH", "_patch_ref")),
        (r"git/refs/(.+)", ("DELETE", "_delete_ref")),
        (r"git/trees", ("POST", "_create_tree")), (r"git/commits", ("POST", "_create_commit")),
        (r"git/commits/([0-9a-f]+)", ("GET", "_get_commit")),
        (r"pulls/(\d+)", ("GET", "_get_pull")), (r"pulls", ("GET", "_list_pulls")),
        (r"pulls/(\d+)/files", ("GET", "_pull_files")),
         (r"pulls/(\d+)/merge", ("PUT", "_merge_pull")),
        (r"commits/([0-9a-z]+)/check-runs", ("GET", "_check_runs")),
        (r"compare/(.+)\.\.\.(.+)", ("GET", "_compare")),
        (r"milestones", ("GET", "_list_milestones")), (r"milestones", ("POST", "_create_milestone")),
        (r"milestones/(\d+)", ("PATCH", "_patch_milestone")),
         (r"pulls", ("POST", "_create_pull")),
        (r"merges", ("POST", "_merge_branches")),
        (r"rules/branches/(.+)", ("GET", "_branch_rules")),
        (r"rulesets/(\d+)", ("GET", "_get_ruleset")),
        (r"environments/([^/]+)", ("GET", "_get_environment")),
        (r"environments/([^/]+)/deployment-branch-policies", ("GET", "_environment_branches")),
    ]

    def _page(self, items, params):
        size, page = int(params.get("per_page", 30)), int(params.get("page", 1))
        return items[(page - 1) * size:page * size]

    def _list_issues(self, params, payload):
        state = params.get("state", "open")
        if "milestone" in params:
            items = [issue for _, issue in sorted(self.issues.items())
                     if issue.get("milestone") == int(params["milestone"]) and
                     (state == "all" or issue["state"] == state)]
            return 200, self._page(items, params)
        from urllib.parse import unquote
        wanted = set(filter(None, unquote(params.get("labels", "")).split(",")))
        items = [issue for _, issue in sorted(self.issues.items())
                 if (state == "all" or issue["state"] == state) and
                 wanted <= {label["name"] for label in issue["labels"]}]
        return 200, self._page(items, params)

    def _create_issue(self, params, payload):
        number = max(self.issues, default=0) + 1
        self.add_issue(number, payload["title"], payload.get("labels", []), body=payload.get("body", ""))
        return 201, self.issues[number]

    def _get_issue(self, params, payload, number):
        issue = self.issues.get(int(number))
        return (200, issue) if issue else (404, {"message": "Not Found"})

    def _patch_issue(self, params, payload, number):
        if int(number) not in self.issues:
            return 404, {"message": "Not Found"}
        self.issues[int(number)].update(payload)
        return 200, self.issues[int(number)]

    def _add_labels(self, params, payload, number):
        issue = self.issues.get(int(number)) or self.pulls[int(number)]  # a PR is an issue for labels
        for name in payload["labels"]:
            self.labels.setdefault(name, {"name": name})
            if name not in {label["name"] for label in issue["labels"]}:
                issue["labels"].append({"name": name})
        return 200, issue["labels"]

    def _remove_label(self, params, payload, number, name):
        from urllib.parse import unquote
        issue, name = self.issues[int(number)], unquote(name)
        before = len(issue["labels"])
        issue["labels"] = [label for label in issue["labels"] if label["name"] != name]
        return (200, issue["labels"]) if len(issue["labels"]) < before else (404, {"message": "Label does not exist"})

    def _create_label(self, params, payload):
        if payload["name"] in self.labels:
            return 422, {"message": "already_exists"}
        self.labels[payload["name"]] = payload
        return 201, payload

    def _list_comments(self, params, payload, number):
        return 200, self._page(self.comments.get(int(number), []), params)

    def _add_comment(self, params, payload, number):
        self.next_comment += 1
        comment = {"id": self.next_comment, "body": payload["body"], "user": {"login": self.author},
                   "created_at": "2026-10-10T12:00:00Z"}
        self.comments.setdefault(int(number), []).append(comment)
        self.issues[int(number)]["comments"] += 1
        return 201, comment

    def _list_sub(self, params, payload, number):
        children = [self.issues[child] for child, parent in sorted(self.parents.items()) if parent == int(number)]
        return 200, self._page(children, params)

    def _add_sub(self, params, payload, number):
        child = next(n for n, issue in self.issues.items() if issue["id"] == payload["sub_issue_id"])
        if child in self.parents:
            return 422, {"message": "already has a parent"}
        self.parents[child] = int(number)
        return 201, self.issues[child]

    def _get_parent(self, params, payload, number):
        parent = self.parents.get(int(number))
        return (200, self.issues[parent]) if parent else (404, {"message": "Not Found"})

    def _list_blockers(self, params, payload, number):
        return 200, self._page([self.issues[n] for n in self.blockers.get(int(number), [])], params)

    def _add_blocker(self, params, payload, number):
        blocker = next(n for n, issue in self.issues.items() if issue["id"] == payload["issue_id"])
        current = self.blockers.setdefault(int(number), [])
        if blocker in current:
            return 422, {"message": "already blocked"}
        current.append(blocker)
        return 201, self.issues[blocker]

    def _matching_refs(self, params, payload, prefix):
        prefix_ref = "refs/" + prefix
        return 200, [{"ref": ref, "object": {"sha": sha}} for ref, sha in sorted(self.refs.items())
                     if ref.startswith(prefix_ref)]

    def _get_ref(self, params, payload, name):
        ref = "refs/" + name
        return (200, {"ref": ref, "object": {"sha": self.refs[ref]}}) if ref in self.refs else (404, {})

    def _create_ref(self, params, payload):
        if payload["ref"] in self.refs:
            return 422, {"message": "Reference already exists"}
        self.refs[payload["ref"]] = payload["sha"]
        return 201, {"ref": payload["ref"], "object": {"sha": payload["sha"]}}

    def _patch_ref(self, params, payload, name):
        ref = "refs/" + name
        if ref not in self.refs:
            return 422, {"message": "Reference does not exist"}
        commit = self.commits.get(payload["sha"])
        if not payload.get("force") and (commit is None or self.refs[ref] not in commit["parents"]):
            return 422, {"message": "Update is not a fast forward"}
        self.refs[ref] = payload["sha"]
        return 200, {"ref": ref, "object": {"sha": payload["sha"]}}

    def _delete_ref(self, params, payload, name):
        self.deleted = getattr(self, "deleted", []) + ["refs/" + name]
        self.refs.pop("refs/" + name, None)
        return 204, None

    def _branch_rules(self, params, payload, branch):
        return 200, self._page(getattr(self, "branch_rules", {}).get(branch, []), params)

    def _get_ruleset(self, params, payload, number):
        ruleset = getattr(self, "rulesets", {}).get(int(number))
        return (200, ruleset) if ruleset else (404, {"message": "Not Found"})

    def _get_environment(self, params, payload, name):
        environment = getattr(self, "environments", {}).get(name)
        return (200, environment) if environment else (404, {"message": "Not Found"})

    def _environment_branches(self, params, payload, name):
        policies = getattr(self, "environment_branches", {}).get(name, [])
        return 200, {"total_count": len(policies), "branch_policies": policies}

    def _list_pulls(self, params, payload):
        items = [pull for _, pull in sorted(self.pulls.items())
                 if (params.get("state", "open") == "all" or pull["state"] == params.get("state", "open")) and
                 (not params.get("head") or params["head"].split(":", 1)[-1] == pull["head"]["ref"]) and
                 (not params.get("base") or params["base"] == pull["base"]["ref"])]
        if params.get("sort") == "updated":
            items.sort(key=lambda pull: pull.get("updated_at", "9999"), reverse=params.get("direction") != "asc")
        return 200, self._page(items, params)

    def _pull_files(self, params, payload, number):
        return 200, self._page(self.pulls[int(number)].get("files", []), params)

    def _get_pull(self, params, payload, number):
        pull = self.pulls.get(int(number))
        return (200, pull) if pull else (404, {"message": "Not Found"})

    def _merge_pull(self, params, payload, number):
        pull = self.pulls[int(number)]
        if pull["state"] != "open":
            return 405, {"message": "Pull Request is not mergeable"}
        if payload.get("sha") and payload["sha"] != pull["head"]["sha"]:
            return 409, {"message": "Head branch was modified"}
        pull.update(state="closed", merged=True, merge_method=payload.get("merge_method"))
        return 200, {"merged": True, "sha": "f" * 40}

    def _check_runs(self, params, payload, sha):
        runs = self.checks.get(sha, [])
        return 200, {"total_count": len(runs), "check_runs": runs}

    def _compare(self, params, payload, base, head):
        commits = self.compares.get((base, head), [])
        return 200, {"commits": [{"sha": f"{i:040x}", "commit": {"message": message}} for i, message in
                                 enumerate(commits, start=1)], "total_commits": len(commits),
                     "ahead_by": len(commits), "status": "ahead" if commits else "identical"}

    def _list_milestones(self, params, payload):
        return 200, self._page(list(self.milestones.values()), params)

    def _create_milestone(self, params, payload):
        if any(m["title"] == payload["title"] for m in self.milestones.values()):
            return 422, {"message": "already_exists"}
        number = len(self.milestones) + 1
        self.milestones[number] = {"number": number, "title": payload["title"], "state": "open"}
        return 201, self.milestones[number]

    def _patch_milestone(self, params, payload, number):
        self.milestones[int(number)].update(payload)
        return 200, self.milestones[int(number)]

    def _create_pull(self, params, payload):
        if any(p["head"]["ref"] == payload["head"] and p["base"]["ref"] == payload["base"] and p["state"] == "open"
               for p in self.pulls.values()):
            return 422, {"message": "A pull request already exists"}
        number = max(list(self.pulls) + list(self.issues), default=0) + 1
        self.add_pull(number, payload["head"], payload["base"], title=payload["title"], body=payload.get("body", ""))
        return 201, self.pulls[number]

    def _merge_branches(self, params, payload):
        key = (payload["base"], payload["head"])
        if key in self.conflicts:
            return 409, {"message": "Merge conflict"}
        if key in self.contained:
            return 204, None
        self.merges.append(key)
        self.contained.add(key)  # merging again finds nothing to merge (HTTP 204), as on GitHub
        return 201, {"sha": "c" * 40}

    def _create_tree(self, params, payload):
        return 201, {"sha": "4b825dc642cb6eb9a060e54bf8d69288fbee4904"}

    def _create_commit(self, params, payload):
        sha = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        self.commits[sha] = payload
        return 201, {"sha": sha}

    def _get_commit(self, params, payload, sha):
        commit = self.commits[sha]
        return 200, {"sha": sha, "message": commit["message"],
                     "parents": [{"sha": parent} for parent in commit["parents"]]}


class FakeProject:
    """In-memory GitHub Project (v2) with the same interface as board.ProjectGraphQL."""

    def __init__(self):
        self.field_specs, self.values = {}, {}

    def fields(self):
        return {name: {"type": spec["type"], "options": list(spec.get("options", []))}
                for name, spec in self.field_specs.items()}

    def ensure_field(self, name, field_type, options=None):
        spec = self.field_specs.setdefault(name, {"type": field_type, "options": []})
        if options is not None:
            spec["options"] = list(options)

    def add(self, number):
        self.values.setdefault(number, {})

    def set(self, number, field, value):
        if field not in self.field_specs:
            raise AssertionError(f"campo inexistente: {field}")
        spec = self.field_specs[field]
        if value is not None and spec["type"] == "SINGLE_SELECT" and value not in spec["options"]:
            raise AssertionError(f"opção inexistente em {field}: {value}")
        self.add(number)
        if value is None:
            self.values[number].pop(field, None)
        else:
            self.values[number][field] = value

    def get(self, number, field):
        return self.values.get(number, {}).get(field)

    def items(self):
        return {number: dict(values) for number, values in self.values.items()}

    # shortcuts for the tests
    def status(self, number):
        return self.get(number, "Status")

    def value(self, number, field):
        return self.get(number, field)

    def set_status(self, number, state):
        self.set(number, "Status", state)
