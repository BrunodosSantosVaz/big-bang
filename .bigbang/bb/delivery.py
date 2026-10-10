"""Delivery of the grouping workflow (ADR-0022/0023): candidate ready, publish behind the release gate, maintenance
publish, correction task after a QA rejection and cleanup. Promotion of the artifact itself stays in the profile
scripts (the same bytes of the candidate); these flows decide and record."""
import datetime
import re

from . import autonomy, board, flows, names, pipeline, states
from . import config as config_module
from .errors import EXIT_INVALID_STATE, BbError
from .locks import expired

CONTROLLER = "controller"
ISSUE_PREFIXES = ("test", "feature", "docs", "fix", "hotfix", "maintenance", "foundation",
                  "teste", "bugfix", "fundacao", "epico")
PROTECTED = re.compile(r"^(main|develop|release/.+|dependabot/.+|framework/.+)$")
LOCK_GRACE = datetime.timedelta(days=7)


def _now(now):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _trusted(config):
    return {config_module.get(config, "project.owner")}


def _milestone(client, version):
    number = client.milestone_number(f"v{version}")
    if number is None:
        raise BbError(f"milestone v{version} inexistente: corte a release primeiro", EXIT_INVALID_STATE)
    return number


def _epics(client, milestone):
    return [issue for issue in client.milestone_issues(milestone) if states.kind(set(issue["labels"])) == "epic"]


def _has(labels, v3_label):
    return v3_label in labels or names.label(v3_label, "legacy") in labels


def candidate_ready(client, project, config, branch, rc_tag, *, now=None):
    """After a candidate is published: its epics go to QA (or straight to Releasing when QA does not apply), the
    candidate is recorded on each card and the PR release → main is opened once."""
    now = _now(now)
    version = branch.removeprefix("release/")
    milestone = _milestone(client, version)
    trusted = _trusted(config)
    epics = _epics(client, milestone)
    for epic in epics:
        number = epic["number"]
        target = "Releasing" if _has(set(epic["labels"]), "qa:not-applicable") else "QA"
        if board.current_state(client, number, trusted, epic) == "In Progress":
            try:
                board.move(client, project, config, number, target, CONTROLLER, now=now,
                           facts={"candidate": True}, event_id=f"candidate-{number}-{version}")
            except BbError as error:
                client.comment(number, f"**Big Bang** · candidata {rc_tag} pronta, mas o épico não avançou:\n\n"
                                       f"{error.message}")
                continue
        project.set(number, "Candidate", rc_tag)
        message = (f"**Big Bang** · candidata `{rc_tag}` pronta para homologação. Confira os critérios de aceite "
                   f"deste épico na candidata e registre `qa:approved` ou a reprovação com o motivo (QA delegado: "
                   f"um agente sem posse no épico registra `bb qa verdict` para esta candidata).")
        if message not in [comment["body"] for comment in client.comments(number)]:
            client.comment(number, message)
    pull = client.create_pull(branch, "main", f"chore(release): {version}",
                              f"Release {version}: épicos " + ", ".join(f"#{e['number']}" for e in epics) +
                              ".\n\nPublicada pelo botão Publish depois da homologação; não mescle à mão.")
    return {"version": version, "epics": [epic["number"] for epic in epics], "pr": pull}


def _flags(root, today):
    from . import flags
    text = flows.read_content(root, "flags.toml")
    by_epic = {}
    for flag in (flags.parse(text, today) if text is not None else []):
        by_epic.setdefault(flag["epic"], []).append(flag)
    return by_epic


def _green(client, sha):
    runs = {run["name"]: run for run in client.check_runs(sha)}
    return all(runs.get(name, {}).get("status") == "completed" and runs[name].get("conclusion") == "success"
               for name in flows.REQUIRED_CHECKS)


def _return_main(client, version):
    """main back into develop; a conflict opens a sync PR instead of forcing anything."""
    result = client.merge_branches("develop", "main", f"chore(sync): return main {version} to develop")
    if result == "conflict":
        branch = f"sync/main-{version.replace('.', '-')}-to-develop"
        client.create_branch(branch, client.branch_sha("main"))
        number = client.create_pull(branch, "develop", f"chore(sync): main {version} into develop",
                                    "A devolução automática da main para a develop teve conflito: resolva neste PR.")
        client.add_labels(number, ["conflict"])
    return result


def _latest_candidate(client, version):
    candidates = []
    for tag in client.tags():
        match = re.fullmatch(rf"v{re.escape(version)}-rc\.(\d+)", tag)
        if match:
            candidates.append((int(match.group(1)), tag))
    return max(candidates)[1] if candidates else None


def publish(client, project, config, version, root, *, today, now=None, pending=None, promote=None, dry_run=False):
    """Publish a release behind its gate: every epic approved or dark behind its flag, pending acceptance only for
    dark epics, a candidate exists and the PR release → main is green on its exact head. Then merge, conclude the
    epics that are delivered, close the milestone and return main to develop. Running again is harmless."""
    now = _now(now)
    milestone = _milestone(client, version)
    epics = _epics(client, milestone)
    trusted = _trusted(config)
    branch = f"release/{version}"
    problems = flows.release_gate(client, config, root, [epic["number"] for epic in epics], today=today,
                                  pending=pending, project=project)
    problems += autonomy.publish_problems(config, "production", now)
    published = f"v{version}" in client.tags()
    rc_tag = _latest_candidate(client, version)
    rc_sha = None
    if rc_tag is None and not published:
        problems.append(f"nenhuma candidata v{version}-rc.N publicada")
    elif rc_tag and not published:
        rc_sha = client.call("GET", f"git/ref/tags/{rc_tag}")[1]["object"]["sha"]
        if client.branch_sha(branch) not in (None, rc_sha):
            problems.append(f"a {branch} mudou depois da candidata {rc_tag}: gere uma candidata nova")
    blocking = [issue["number"] for issue in client.issues("open")
                if "blocks-production" in issue["labels"] or "bloqueia-producao" in issue["labels"]]
    if blocking:
        problems.append("issues que bloqueiam produção abertas: " + ", ".join(f"#{n}" for n in blocking))
    pulls = client.pulls(head=branch, base="main", state="all")
    pull = next((p for p in pulls if p["state"] == "open" or p["merged"]), None)
    if pull is None:
        problems.append(f"PR {branch} → main inexistente")
    elif not pull["merged"] and not _green(client, pull["sha"]):
        problems.append(f"PR #{pull['number']} sem o check gate verde no SHA {pull['sha'][:10]}")
    elif not pull["merged"] and rc_sha and pull["sha"] != rc_sha:
        problems.append(f"o PR #{pull['number']} não está na candidata {rc_tag}: gere uma candidata nova")
    if problems:
        raise BbError("publicação recusada:\n" + "\n".join(f"  - {p}" for p in problems), EXIT_INVALID_STATE)
    if dry_run:
        return {"version": version, "pr": pull["number"], "done": [], "dark": [], "dry_run": True}
    if not pull["merged"]:
        client.merge_pull(pull["number"], pull["sha"])
    if promote and not published:
        promote(rc_tag, f"v{version}", client.branch_sha("main"))  # the candidate's bytes, never a rebuild
    flags_by_epic = _flags(root, today)
    done, dark, pending = [], [], []
    for epic in epics:
        number = epic["number"]
        labels = set(client.issue(number)["labels"])
        state = board.current_state(client, number, trusted)
        if state == "QA":
            try:  # QA passed by the owner's decision or an independent agent's verdict: the rules decide
                board.move(client, project, config, number, "Releasing", CONTROLLER, now=now,
                           event_id=f"publish-{number}-{version}-releasing")
                state = "Releasing"
            except BbError as error:
                if error.code != EXIT_INVALID_STATE:
                    raise
        flag_on = any(flag["production"] for flag in flags_by_epic.get(number, []))
        if state == "Releasing":
            try:
                board.move(client, project, config, number, "Done", CONTROLLER, now=now,
                           facts={"delivered": True, "flag_on": flag_on}, event_id=f"publish-{number}-{version}-done")
                done.append(number)
            except BbError:
                (pending if flag_on else dark).append(number)
        elif state == "Done":
            done.append(number)
        elif flag_on:
            pending.append(number)  # lost its QA after the gate (decision withdrawn): never reported as dark
        else:
            dark.append(number)  # the gate let it through only with every flag off: shipped dark
    client.close_milestone(milestone)
    _return_main(client, version)
    current = client.locks().current(f"version-{version}")
    if current:
        client.locks().release(f"version-{version}", current["session"], current["generation"], now=now)
    for number in pending:
        client.comment(number, f"**Big Bang** · a release {version} foi publicada com a flag deste épico ligada, mas "
                               "ele não pôde ser concluído (a homologação mudou depois do portão). Confira a decisão "
                               "e a flag com o dono.")
    return {"version": version, "pr": pull["number"], "done": done, "dark": dark, "pending": pending}


def publish_maintenance(client, config, number, *, changed_paths, dry_run=False):
    """maintenance/* → main when nothing of the artifact changed, then main back to develop."""
    pull = client.pull(number)
    if not pull or pull["state"] != "open" or not pull["head"].startswith("maintenance/") or pull["base"] != "main":
        raise BbError(f"PR #{number} não é uma manutenção aberta para a main", EXIT_INVALID_STATE)
    if not _has(set(pull["labels"]), "pr:approved"):
        raise BbError("manutenção ainda não aprovada (pr:approved)", EXIT_INVALID_STATE)
    artifact = pipeline.artifact_paths(changed_paths, config_module.get(config, "delivery.artifact_paths"))
    if artifact:
        raise BbError("a manutenção muda o artefato (" + ", ".join(artifact[:3]) + "): isso exige uma release",
                      EXIT_INVALID_STATE)
    if not _green(client, pull["sha"]):
        raise BbError(f"PR #{number} sem o check gate verde", EXIT_INVALID_STATE)
    if dry_run:
        return "simulação: nada mesclado"
    client.merge_pull(number, pull["sha"])
    return _return_main(client, f"maintenance-{number}")


def correction_task(client, project, config, epic, reason, *, actor, now=None, dry_run=False):
    """QA rejected: the epic passes through Rejected back to In Progress, and one correction task is born from the
    release branch (fix/<n>) in the same milestone; its PR goes into the release, and a new candidate follows."""
    now = _now(now)
    if not reason or not reason.strip():
        raise BbError("a reprovação exige o motivo", EXIT_INVALID_STATE)
    issue = client.issue(epic)
    if dry_run:  # the same rules decide (the owner's qa:rejected, or an independent agent's rejected verdict)
        board.move(client, project, config, epic, "Rejected", actor, reason="qa", return_to="In Progress", now=now,
                   dry_run=True)
        return None
    board.move(client, project, config, epic, "Rejected", actor, reason="qa", return_to="In Progress", now=now)
    board.move(client, project, config, epic, "In Progress", actor, now=now)
    inherited = sorted(label for label in issue["labels"] if label.startswith(flows.INHERITED))
    title = f"Correção: {reason.strip()}"
    task = client.create_issue(title, f"Parte do épico #{epic}. Reprovação na homologação:\n\n> {reason.strip()}",
                               ["type:task", *inherited])
    client.add_sub_issue(epic, task)
    milestone = issue.get("milestone")
    milestone_number = client.milestone_number(milestone) if isinstance(milestone, str) else milestone
    if milestone_number:
        client.update_issue(task, milestone=milestone_number)
    version = next((m["title"][1:] for m in client.paginate("milestones?state=all")
                    if m["number"] == milestone_number), None) if milestone_number else None
    base = client.branch_sha(f"release/{version}") if version else None
    client.create_branch(pipeline.branch_name("fix", task, title), base or client.branch_sha("develop"))
    project.add(task)
    project.set(task, "Status", "Todo")
    return task


def cleanup(client, config, *, now=None, dry_run=True):
    """Delete the merged branches whose issue is closed and has no open PR; report claims expired for more than a
    week on open issues and what is outside the branch model. main, develop, releases, tags and lock refs (whose
    tombstones keep generations monotonic) are never touched."""
    now = _now(now)
    report = {"deleted": [], "kept": [], "outside": [], "locks": []}
    open_heads = {pull["head"] for pull in client.pulls(state="open")}
    for branch in sorted(client.all_branches()):
        if PROTECTED.match(branch):
            continue
        kind, number = pipeline.branch_issue(branch)
        if kind not in ISSUE_PREFIXES:
            report["outside"].append(branch)
            continue
        issue = client.issue(number)
        merged = client.ahead_by("develop", branch) == 0 or client.ahead_by("main", branch) == 0
        if issue and issue["state"] == "closed" and branch not in open_heads and merged:
            report["deleted"].append(branch)
            if not dry_run:
                client.delete_ref(f"refs/heads/{branch}")
        else:
            report["kept"].append(branch)
    open_issues = {f"issue-{issue['number']}" for issue in client.issues("open")}
    for resource, record in sorted(client.locks().all(open_issues).items()):
        expiry = datetime.datetime.fromisoformat(record["expires"].replace("Z", "+00:00"))
        if record.get("state") == "held" and expired(record, now) and now - expiry > LOCK_GRACE:
            report["locks"].append(resource)  # reported for the owner; lock refs are never deleted (ADR-0023)
    return report
