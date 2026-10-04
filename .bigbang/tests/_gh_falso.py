#!/usr/bin/env python3
"""Fake `gh` with state, for the pipeline script tests. State: JSON file in FAKE_GH_STATE; every call is appended to
FAKE_GH_LOG. `--jq` filters are applied with the real jq (a test-only dependency), exactly as gh would.

State shape:
  boards: {"<n>": {"fields": {"Status": {"id": "F", "options": [{"id": "O", "name": "A fazer"}]}, "Épico": {"id": ...}},
                   "items": {"<issue>": {"Status": "A fazer", "Sprint": "...", "Épico": "#7"}}}}
  issues: {"<n>": {"title", "body", "labels": [...], "state": "open"|"closed", "parent": n, "sub": [n], "blocked_by": [n]}}
  refs: {"heads/develop": "sha"}, pulls: [...], checks: {"sha": [{"name", "status", "conclusion"}]}
"""
import json
import datetime
import os
import re
import subprocess
import sys

REPO = os.environ.get("GITHUB_REPOSITORY", "dono/repo")


def load():
    with open(os.environ["FAKE_GH_STATE"], encoding="utf-8") as handle:
        return json.load(handle)


def save(state):
    with open(os.environ["FAKE_GH_STATE"], "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=1)


def options(argv):
    """Collect -f/-F/--raw-field/--field values, --jq, --paginate, -X and positional args."""
    fields, jq, method, positional, flags = {}, None, "GET", [], {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-f", "-F", "--raw-field", "--field"):
            key, _, value = argv[i + 1].partition("=")
            fields[key] = value
            i += 2
        elif arg in ("--jq", "-q"):
            jq, i = argv[i + 1], i + 2
        elif arg == "-X":
            method, i = argv[i + 1], i + 2
        elif arg.startswith("--") and i + 1 < len(argv) and not argv[i + 1].startswith("-") and arg not in (
                "--paginate", "--silent", "--force", "--draft"):
            flags.setdefault(arg, []).append(argv[i + 1])
            i += 2
        elif arg.startswith("-") and arg not in ("-R",) and len(arg) > 1:
            flags.setdefault(arg, []).append(True)
            i += 1
        elif arg == "-R":
            i += 2
        else:
            positional.append(arg)
            i += 1
    return fields, jq, method, positional, flags


def emit(data, jq):
    if "--slurp" in sys.argv and jq is None:
        data = [data]
    text = json.dumps(data, ensure_ascii=False)
    if jq is None:
        print(text)
        return
    result = subprocess.run(["jq", "-r", jq], input=text, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    sys.stdout.write(result.stdout)


def board(state, number):
    return state["boards"][str(number)]


def board_by_pid(state, pid):
    return board(state, pid[1:])


def field_value(item, name):
    value = item.get(name)
    return None if value is None else {"name": value}


# --- graphql ---------------------------------------------------------------------------------------------------------

def graphql(state, fields, jq):
    query = fields.get("query", "")
    if "addProjectV2ItemById" in query:
        b = board_by_pid(state, fields["p"])
        issue = fields["c"][1:]
        b["items"].setdefault(issue, {})
        save(state)
        return emit({"data": {"addProjectV2ItemById": {"item": {"id": f"I{fields['p'][1:]}-{issue}"}}}}, jq)
    if "updateProjectV2ItemFieldValue" in query:
        b = board_by_pid(state, fields["p"])
        issue = fields["i"].split("-", 1)[1]
        name = next(n for n, f in b["fields"].items() if f["id"] == fields["f"])
        if "o" in fields:
            value = next(o["name"] for o in b["fields"][name]["options"] if o["id"] == fields["o"])
        else:
            value = fields["t"]
        b["items"].setdefault(issue, {})[name] = value
        save(state)
        return emit({"data": {}}, jq)
    if "deleteProjectV2Item" in query:
        b = board_by_pid(state, fields["p"])
        b["items"].pop(fields["i"].split("-", 1)[1], None)
        save(state)
        return emit({"data": {}}, jq)
    if "updateProjectV2Field" in query:
        field_id = re.search(r'fieldId:\s*"([^"]+)"', query).group(1)
        for b in state["boards"].values():
            for name, field in b["fields"].items():
                if field["id"] == field_id:
                    new = []
                    for match in re.finditer(r'\{\s*(?:id:\s*"([^"]*)",\s*)?name:\s*"((?:[^"\\]|\\.)*)"', query):
                        option_id = match.group(1) or f"{field_id}-{len(new)}-{match.group(2)}"
                        new.append({"id": option_id, "name": match.group(2).replace('\\"', '"')})
                    kept = {o["id"]: o["name"] for o in new}
                    lost = {o["name"] for o in field["options"] if o["id"] not in kept}
                    renamed = {o["name"]: kept[o["id"]] for o in field["options"] if o["id"] in kept}
                    for item in b["items"].values():  # GitHub wipes values of options sent without their id
                        if item.get(name) in lost:
                            item.pop(name)
                        elif item.get(name) in renamed:  # and a kept id carries the new name
                            item[name] = renamed[item[name]]
                    field["options"] = new
        save(state)
        return emit({"data": {}}, jq)
    if "projectV2(number:$n){ id" in query.replace("\n", " ") or re.search(r"projectV2\(number:\$n\)\{\s*id", query):
        return emit({"data": {"repositoryOwner": {"projectV2": {"id": f"P{fields['n']}"}}}}, jq)
    if "ProjectV2SingleSelectField { id options" in query:
        field = board(state, fields["n"])["fields"].get(fields["c"])
        data = {"id": field["id"], "options": field["options"]} if field and "options" in field else None
        return emit({"data": {"repositoryOwner": {"projectV2": {"field": data}}}}, jq)
    if "ProjectV2FieldCommon { id" in query:
        field = board(state, fields["n"])["fields"].get(fields["c"])
        return emit({"data": {"repositoryOwner": {"projectV2": {"field": {"id": field["id"]} if field else None}}}},
                    jq)
    if "node(id:$i)" in query and "fieldValueByName" in query:
        b = board(state, fields["i"][1:].split("-", 1)[0])
        item = b["items"].get(fields["i"].split("-", 1)[1], {})
        return emit({"data": {"node": {"fieldValueByName": field_value(item, fields["c"])}}}, jq)
    if "items(first:100" in query:
        b = board_by_pid(state, fields["id"])
        nodes = []
        for issue, item in b["items"].items():
            data = state["issues"].get(issue, {})
            content = {"number": int(issue), "title": data.get("title", ""),
                       "state": "OPEN" if data.get("state", "open") == "open" else "CLOSED",
                       "repository": {"nameWithOwner": item.get("_repo", REPO)}}
            nodes.append({"fieldValueByName": field_value(item, "Status"), "status": field_value(item, "Status"),
                          "sprint": field_value(item, "Sprint"), "content": content})
        return emit({"data": {"node": {"items": {"pageInfo": {"hasNextPage": False}, "nodes": nodes}}}}, jq)
    if "parent{ number }" in query or "parent { number }" in query:
        issue = state["issues"].get(str(fields["n"]), {})
        parent = issue.get("parent")
        return emit({"data": {"repository": {"issue": {"parent": {"number": parent} if parent else None}}}}, jq)
    if "subIssuesSummary" in query:
        issue = state["issues"][str(fields["n"])]
        subs = issue.get("sub", [])
        done = sum(1 for n in subs if state["issues"][str(n)].get("state") == "closed")
        return emit({"data": {"repository": {"issue": {"state": issue.get("state", "open").upper(),
                                                         "subIssuesSummary": {"total": len(subs),
                                                                              "completed": done}}}}}, jq)
    if "subIssues(first" in query:
        issue = state["issues"][str(fields["n"])]
        nodes = [{"number": n, "title": state["issues"][str(n)]["title"],
                  "labels": {"nodes": [{"name": label} for label in state["issues"][str(n)].get("labels", [])]},
                  "state": state["issues"][str(n)].get("state", "open").upper()} for n in issue.get("sub", [])]
        return emit({"data": {"repository": {"issue": {"subIssues": {"nodes": nodes}}}}}, jq)
    if "addSubIssue" in query:
        parent, child = fields["e"][1:], fields["t"][1:]
        state["issues"][parent].setdefault("sub", []).append(int(child))
        state["issues"][child]["parent"] = int(parent)
        save(state)
        return emit({"data": {}}, jq)
    sys.stderr.write(f"gh falso: consulta graphql não suportada:\n{query}\n")
    sys.exit(1)


# --- REST and subcommands --------------------------------------------------------------------------------------------

def issue_json(state, number):
    issue = state["issues"][str(number)]
    return {"number": int(number), "node_id": f"N{number}", "id": 1000 + int(number), "title": issue.get("title", ""),
            "body": issue.get("body", ""), "state": issue.get("state", "open"),
            "labels": [{"name": label} for label in issue.get("labels", [])],
            "comments": len(state.get("comment_records", {}).get(str(number), [])),
            "milestone": {"title": issue["milestone"]} if issue.get("milestone") else None}


def new_issue(state, title, body, labels, milestone=None):
    number = max([int(n) for n in state["issues"]] + [int(state.get("next_issue", 100))]) + 1
    state["issues"][str(number)] = {"title": title, "body": body, "labels": list(labels), "state": "open"}
    if milestone:
        state["issues"][str(number)]["milestone"] = milestone
    save(state)
    return number


def api(state, positional, fields, jq, method):
    from urllib.parse import unquote
    path = unquote(positional[0])
    if "per_page=100" in path and "/issues?" not in path:
        path = path.split("?", 1)[0]
    match = re.match(rf"^repos/{re.escape(REPO)}/issues/(\d+)$", path)
    if match:
        return emit(issue_json(state, match.group(1)), jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/issues/(\d+)/comments$", path)
    if match:
        number = match.group(1)
        records = state.setdefault("comment_records", {}).setdefault(number, [])
        if method == "POST":
            state.setdefault("comments", {}).setdefault(number, []).append(fields["body"])
            ident = state.get("next_comment", 0) + 1
            state["next_comment"] = ident
            record = {"id": ident, "body": fields["body"], "user": {"login": "dono"},
                      "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
            record["updated_at"] = record["created_at"]
            records.append(record)
            save(state)
            return emit(record, jq)
        return emit(records, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/issues/comments/(\d+)$", path)
    if match:
        for number, records in state.get("comment_records", {}).items():
            for index, record in enumerate(records):
                if record["id"] != int(match.group(1)):
                    continue
                if method == "DELETE":
                    records.pop(index)
                    state["comments"][number].pop(index)
                elif method == "PATCH":
                    record["body"] = fields["body"]
                    record["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    state["comments"][number][index] = fields["body"]
                save(state)
                return emit(record, jq)
        sys.stderr.write("HTTP 404: comment not found\n")
        sys.exit(1)
    match = re.match(rf"^repos/{re.escape(REPO)}/issues/(\d+)/labels(?:/(.+))?$", path)
    if match and method in ("POST", "DELETE"):
        number = match.group(1)
        target = state.get("prs", {}).get(number) or state["issues"][number]
        target.setdefault("labels", [])
        if method == "POST" and fields["labels[]"] not in target["labels"]:
            target["labels"].append(fields["labels[]"])
        if method == "DELETE":
            if match.group(2) not in target["labels"]:
                sys.stderr.write("HTTP 404: Label does not exist\n")
                sys.exit(1)
            target["labels"].remove(match.group(2))
        save(state)
        return emit({}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/issues/(\d+)/dependencies/blocked_by$", path)
    if match:
        issue = state["issues"][match.group(1)]
        if method == "POST":
            blocker = int(fields["issue_id"]) - 1000
            if blocker not in issue.setdefault("blocked_by", []):
                issue["blocked_by"].append(blocker)
            save(state)
            return emit({}, jq)
        return emit([issue_json(state, n) for n in issue.get("blocked_by", [])], jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/issues/(\d+)/parent$", path)
    if match:
        parent = state["issues"][match.group(1)].get("parent")
        if not parent:
            sys.stderr.write("HTTP 404: parent not found\n")
            sys.exit(1)
        return emit(issue_json(state, parent), jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/git/ref/tags/(.+)$", path)
    if match:
        if f"tags/{match.group(1)}" not in state.get("refs", {}):
            sys.stderr.write("HTTP 404: Not Found\n")
            sys.exit(1)
        return emit({"object": {"sha": state["refs"][f"tags/{match.group(1)}"]}}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/git/refs/heads/(.+)$", path)
    if match and method == "DELETE":
        state.get("refs", {}).pop(f"heads/{match.group(1)}", None)
        state.setdefault("apagadas", []).append(match.group(1))
        save(state)
        return emit({}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/compare/(.+)$", path)
    if match:
        return emit({"ahead_by": state.get("compare", {}).get(match.group(1), 0)}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/milestones/(\d+)$", path)
    if match and method == "PATCH":
        for milestone in state.get("milestones", []):
            if milestone["number"] == int(match.group(1)):
                milestone["state"] = fields.get("state", milestone["state"])
        save(state)
        return emit({}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/issues\?milestone=(\d+)", path)
    if match:
        title = next(m["title"] for m in state.get("milestones", []) if m["number"] == int(match.group(1)))
        return emit([issue_json(state, n) for n, i in state["issues"].items() if i.get("milestone") == title], jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/git/matching-refs/heads/(.*)$", path)
    if match:
        refs = [{"ref": f"refs/{name}", "object": {"sha": state["refs"][name]}} for name in sorted(state.get("refs", {}))
                if name.startswith(f"heads/{match.group(1)}")]
        return emit(refs, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/git/refs?/heads/(.+)$", path)
    if match and method == "GET":
        sha = state.get("refs", {}).get(f"heads/{match.group(1)}")
        if not sha:
            sys.stderr.write("HTTP 404: Not Found\n")
            sys.exit(1)
        return emit({"object": {"sha": sha}}, jq)
    if path == f"repos/{REPO}/git/refs" and method == "POST":
        state.setdefault("refs", {})[fields["ref"][len("refs/"):]] = fields["sha"]
        save(state)
        return emit({}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/commits/([^/]+)/check-runs", path)
    if match:
        return emit({"check_runs": state.get("checks", {}).get(match.group(1), [])}, jq)
    match = re.match(rf"^repos/{re.escape(REPO)}/pulls/(\d+)/files", path)
    if match:
        return emit(state.get("pr_files", {}).get(match.group(1), []), jq)
    if path.startswith(f"repos/{REPO}/pulls"):
        return emit(state.get("pulls", []), jq)
    if path.startswith(f"repos/{REPO}/milestones"):
        if method == "POST":
            state.setdefault("milestones", []).append({"number": len(state.get("milestones", [])) + 1,
                                                       "title": fields["title"], "state": "open"})
            save(state)
            return emit(state["milestones"][-1], jq)
        return emit(state.get("milestones", []), jq)
    if path.startswith(f"repos/{REPO}/issues?") or path == f"repos/{REPO}/issues":
        from urllib.parse import parse_qs, urlsplit
        query = parse_qs(urlsplit(path).query)
        wanted = set(query.get("labels", [""])[0].split(",")) - {""}
        status = query.get("state", ["open"])[0]
        return emit([issue_json(state, n) for n, i in state["issues"].items()
                     if wanted <= set(i.get("labels", [])) and status in ("all", i.get("state", "open"))], jq)
    return emit(state.get("api", {}).get(path, {}), jq)


def main():
    argv = sys.argv[1:]
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps(argv, ensure_ascii=False) + "\n")
    state = load()
    fields, jq, method, positional, flags = options(argv)
    if argv[0] == "api" and flags.get("--input"):  # the request body (e.g. a ruleset), kept for the assertions
        with open(flags["--input"][0], encoding="utf-8") as body:
            state.setdefault("corpos", []).append({"rota": positional[1], "corpo": json.loads(body.read())})
        save(state)
    if argv[:2] == ["api", "graphql"]:
        return graphql(state, fields, jq)
    if argv[0] == "api":
        if fields and method == "GET" and positional[0].endswith("/refs"):
            method = "POST"
        return api(state, positional[1:], fields, jq, method)
    if argv[:2] == ["issue", "create"]:
        number = new_issue(state, flags["--title"][0], flags.get("--body", [""])[0], flags.get("--label", []),
                           (flags.get("--milestone") or [None])[0])
        print(f"https://github.com/{REPO}/issues/{number}")
        return None
    if argv[:2] == ["issue", "edit"]:
        issue = state["issues"][positional[2]]
        for label in flags.get("--add-label", []):
            for item in label.split(","):
                if item not in issue["labels"]:
                    issue["labels"].append(item)
        for label in flags.get("--remove-label", []):
            for item in label.split(","):
                if item in issue["labels"]:
                    issue["labels"].remove(item)
        if flags.get("--milestone"):
            issue["milestone"] = flags["--milestone"][0]
        save(state)
        return None
    if argv[:2] == ["release", "create"]:
        tag = positional[2]
        state.setdefault("releases", []).append(tag)
        state.setdefault("refs", {})[f"tags/{tag}"] = (flags.get("--target") or ["sha"])[0]
        state.setdefault("release_assets", {})[tag] = [os.path.basename(f) for f in positional[3:]]
        import shutil
        import tempfile
        folder = tempfile.mkdtemp(prefix="release-", dir=os.path.dirname(os.environ["FAKE_GH_STATE"]))
        for f in positional[3:]:
            shutil.copy(f, folder)
        state.setdefault("release_dirs", {})[tag] = folder
        state.setdefault("release_info", {})[tag] = {"prerelease": "--prerelease" in argv,
                                                     "latest": "--latest" in argv,
                                                     "target": (flags.get("--target") or [""])[0]}
        save(state)
        return None
    if argv[:2] == ["pr", "create"]:
        number = str(max([int(n) for n in state.get("prs", {})] + [400]) + 1)
        state.setdefault("prs", {})[number] = {"head": flags["--head"][0], "base": flags["--base"][0],
                                               "title": flags["--title"][0], "state": "OPEN",
                                               "labels": flags.get("--label", []), "body": (flags.get("--body") or [""])[0]}
        save(state)
        print(f"https://github.com/{REPO}/pull/{number}")
        return None
    if argv[:2] == ["attestation", "verify"]:
        if state.get("atestacao_falha"):
            sys.stderr.write("verification failed\n")
            sys.exit(1)
        return None
    if argv[:2] == ["release", "download"]:
        import shutil
        source = state["release_dirs"][positional[2]]
        for name in os.listdir(source):
            shutil.copy(os.path.join(source, name), os.path.join(flags["--dir"][0], name))
        return None
    if argv[:2] == ["release", "view"]:
        if len(positional) < 3:  # no tag: the latest release
            return emit({"tagName": state["releases"][-1]}, jq)
        if positional[2] not in state.get("releases", []):
            sys.stderr.write("release not found\n")
            sys.exit(1)
        return None
    if argv[:2] == ["pr", "view"]:
        pr = state["prs"][positional[2]]
        return emit({"number": int(positional[2]), "state": pr.get("state", "OPEN"), "isDraft": pr.get("draft", False),
                     "baseRefName": pr["base"], "headRefName": pr["head"], "headRefOid": pr.get("sha", "sha0"),
                     "labels": [{"name": label} for label in pr.get("labels", [])],
                     "title": pr.get("title", ""), "body": pr.get("body", "")}, jq)
    if argv[:2] == ["pr", "diff"]:
        sys.stdout.write(state.get("prs", {}).get(positional[2], {}).get("diff", ""))
        return None
    if argv[:2] == ["pr", "merge"]:
        pr = state["prs"][positional[2]]
        expected = (flags.get("--match-head-commit") or [None])[0]
        if expected and expected != pr.get("sha", "sha0"):
            sys.stderr.write("head commit mudou\n")
            sys.exit(1)
        pr["state"] = "MERGED"
        save(state)
        hook = state.get("hooks", {}).get("pr_merge")
        if hook:  # tests: perform the real git merge the PR would do
            subprocess.run(hook, shell=True, check=True, capture_output=True)
        return None
    if argv[:2] == ["pr", "list"]:
        wanted_state = (flags.get("--state") or ["open"])[0].upper()
        base = (flags.get("--base") or [None])[0]
        head = (flags.get("--head") or [None])[0]
        result = [{"number": int(n), "headRefName": pr["head"], "baseRefName": pr["base"], "title": pr.get("title", ""),
                   "mergeable": pr.get("mergeable", "MERGEABLE"), "headRefOid": pr.get("sha", "sha0"),
                   "body": pr.get("body", ""), "state": pr.get("state", "OPEN"),
                   "labels": [{"name": label} for label in pr.get("labels", [])]}
                  for n, pr in state.get("prs", {}).items()
                  if "head" in pr and (wanted_state == "ALL" or pr.get("state", "OPEN") == wanted_state)
                  and (base is None or pr["base"] == base) and (head is None or pr["head"] == head)]
        return emit(result, jq)
    if argv[:2] == ["workflow", "run"]:
        return None
    if argv[:2] == ["pr", "edit"]:
        pr = state.setdefault("prs", {}).setdefault(positional[2], {"labels": []})
        for label in flags.get("--add-label", []):
            if label not in pr["labels"]:
                pr["labels"].append(label)
        for label in flags.get("--remove-label", []):
            if label in pr["labels"]:
                pr["labels"].remove(label)
        save(state)
        return None
    if argv[:2] == ["issue", "close"]:
        state["issues"][positional[2]]["state"] = "closed"
        save(state)
        return None
    if argv[:2] in (["issue", "comment"], ["pr", "comment"], ["label", "create"]):
        return None
    canned = state.get("comandos", {}).get(" ".join(argv[:2]))
    if canned is not None:
        sys.stdout.write(canned)
        return None
    sys.stderr.write(f"gh falso: comando não suportado: {argv}\n")
    sys.exit(1)


if __name__ == "__main__":
    if os.name == "nt":
        main()
    else:
        # Serialize fake API transactions, not clients: concurrent tests must not lose JSON writes.
        import contextlib
        import fcntl
        import io
        import time
        output = io.StringIO()
        with open(os.environ["FAKE_GH_STATE"] + ".lock", "w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with contextlib.redirect_stdout(output):
                main()
        result = output.getvalue()
        gate = os.environ.get("FAKE_GH_INITIAL_GATE")
        if gate and "/comments?" in " ".join(sys.argv) and "-X" not in sys.argv and result.strip() == "[[]]":
            from pathlib import Path
            Path(gate, os.environ["FAKE_GH_ACTOR"]).touch()
            deadline = time.monotonic() + 10
            while len(list(Path(gate).iterdir())) < 2:
                if time.monotonic() > deadline:
                    raise RuntimeError("concurrent clients did not reach the initial barrier")
                time.sleep(0.01)
        sys.stdout.write(result)
