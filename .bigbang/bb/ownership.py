"""Optimistic issue ownership (spec 13). Labels are a display; session comments choose the winner."""
import datetime
import json
import re
import time
import uuid
from urllib.parse import quote

from . import github
from .errors import EXIT_INVALID_STATE, EXIT_USAGE, BbError

CLAIM = re.compile(r"^<!-- bb:assumida nome=([a-z0-9]+(?:-[a-z0-9]+)*) sessao=([a-zA-Z0-9-]+) -->", re.M)
PUSH = re.compile(r"^<!-- bb:push sessao=([a-zA-Z0-9-]+) -->$", re.M)
UTC = datetime.timezone.utc


def api(path, method="GET", **fields):
    args = ["api", "-X", method, path]
    for key, value in fields.items():
        args.extend(["-f", f"{key}={value}"])
    return json.loads(github.run(*args) or "null")


def listing(path):
    separator = "&" if "?" in path else "?"
    pages = json.loads(github.run("api", path + separator + "per_page=100", "--paginate", "--slurp"))
    return [item for page in pages for item in page]


def labels(issue):
    return {label["name"] for label in issue.get("labels", [])}


def active_claims(repository, number, owner):
    result = []
    comments = [c for c in listing(f"repos/{repository}/issues/{number}/comments") if
                c.get("user", {}).get("login", "").casefold() == owner.casefold()]
    pushes = {}
    for comment in comments:
        match = PUSH.search(comment.get("body") or "")
        if match:
            pushes[match[1]] = max(pushes.get(match[1], ""), comment["created_at"])
    for comment in comments:
        match = CLAIM.search(comment.get("body") or "")
        if match:
            result.append({**comment, "name": match[1], "session": match[2],
                           "last_push": pushes.get(match[2])})
    return sorted(result, key=lambda c: (c["created_at"], c["name"], c["id"]))


def issue_data(repository, number):
    return api(f"repos/{repository}/issues/{number}")


def _add_label(repository, number, label):
    api(f"repos/{repository}/issues/{number}/labels", "POST", **{"labels[]": label})


def _remove_label(repository, number, label):
    try:
        api(f"repos/{repository}/issues/{number}/labels/{quote(label, safe='')}", "DELETE")
    except BbError as exc:
        if "404" not in exc.message:
            raise


def _close_claim(repository, claim, reason):
    body = claim["body"].replace("bb:assumida", "bb:liberada", 1)
    api(f"repos/{repository}/issues/comments/{claim['id']}", "PATCH", body=body + "\n\n" + reason)


def blocked(repository, number):
    """A merged blocker counts as done even while its issue awaits production."""
    for blocker in listing(f"repos/{repository}/issues/{number}/dependencies/blocked_by"):
        if blocker["state"].lower() == "closed" and "teste-aceite" not in labels(blocker):
            continue
        parent = api(f"repos/{repository}/issues/{number}/parent")
        blocker_parent = api(f"repos/{repository}/issues/{blocker['number']}/parent")
        if parent["number"] != blocker_parent["number"]:
            raise BbError(f"#{number}: bloqueador de outro épico", EXIT_INVALID_STATE)
        prs = json.loads(github.run("pr", "list", "--repo", repository, "--state", "merged",
                                   "--search", f"in:body \"Refs #{blocker['number']}\"", "--limit", "100",
                                   "--json", "body,headRefName,baseRefName"))
        reference = re.compile(rf"\bRefs\s+#{blocker['number']}\b", re.I)
        if not any(reference.search(pr.get("body", "")) and
                   re.match(rf"^epico/{parent['number']}-", pr["baseRefName"]) and
                   re.match(rf"^(teste|feature|docs)/{blocker['number']}-", pr["headRefName"]) for pr in prs):
            raise BbError(f"#{number} bloqueada pela #{blocker['number']} (PR ainda não mesclado)", EXIT_INVALID_STATE)


def _capacity(config, number, name):
    repo = config["projeto"]["repositorio"]
    owned = []
    for issue in listing(f"repos/{repo}/issues?state=open"):
        if "pull_request" in issue or issue["number"] == number:
            continue
        claims = active_claims(repo, issue["number"], config["projeto"]["dono"]) if issue.get("comments") else []
        if f"ia:{name}" in labels(issue) or any(c["name"] == name for c in claims):
            owned.append(issue["number"])
    if len(owned) >= config["ias"]["tarefas_por_ia"]:
        raise BbError(f"{name} atingiu o limite de tarefas: {owned}", EXIT_INVALID_STATE)


def _preflight(config, number, name, allow_occupied=False):
    if number <= 0 or name not in config["ias"]["nomes"] or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise BbError("issue inválida ou nome fora de ias.nomes", EXIT_USAGE)
    if config["ias"]["espera_confirmacao_segundos"] < 1:
        raise BbError("espera_confirmacao_segundos precisa ser pelo menos 1", EXIT_USAGE)
    repo, owner = config["projeto"]["repositorio"], config["projeto"]["dono"]
    data = issue_data(repo, number)
    if "pull_request" in data or data["state"].lower() != "open":
        raise BbError(f"#{number} não é uma issue aberta", EXIT_INVALID_STATE)
    claims = active_claims(repo, number, owner)
    occupied = [label for label in labels(data) if label.startswith("ia:")]
    if (claims or occupied) and not allow_occupied:
        who = f"{claims[0]['name']} desde {claims[0]['created_at']}" if claims else ", ".join(occupied)
        raise BbError(f"#{number} já está com {who}", EXIT_INVALID_STATE)
    blocked(repo, number)
    _capacity(config, number, name)
    return claims


def claim(config, number, name):
    _preflight(config, number, name)
    repo, owner = config["projeto"]["repositorio"], config["projeto"]["dono"]
    github.run("label", "create", f"ia:{name}", "--repo", repo, "--color", "5319E7", "--force",
               "--description", "Posse de tarefa por IA")
    session = str(uuid.uuid4())
    body = f"<!-- bb:assumida nome={name} sessao={session} -->\nPosse solicitada por `{name}`."
    try:
        _add_label(repo, number, f"ia:{name}")
        comment = api(f"repos/{repo}/issues/{number}/comments", "POST", body=body)
        time.sleep(config["ias"]["espera_confirmacao_segundos"])
        contenders = active_claims(repo, number, owner)
        if not contenders or contenders[0]["session"] != session:
            winner = contenders[0]["name"] if contenders else "nenhuma sessão válida"
            raise BbError(f"#{number}: disputa perdida; posse de {winner}", EXIT_INVALID_STATE)
        # A blocker or issue may have changed during the confirmation window.
        if issue_data(repo, number)["state"].lower() != "open":
            raise BbError(f"#{number} foi fechada durante a confirmação", EXIT_INVALID_STATE)
        blocked(repo, number)
        _capacity(config, number, name)
        _add_label(repo, number, f"ia:{name}")
    except BaseException:
        # Reconcile by UUID even if GitHub accepted the POST but the response was lost.
        for pending in active_claims(repo, number, owner):
            if pending["session"] == session:
                api(f"repos/{repo}/issues/comments/{pending['id']}", "DELETE")
        remaining = active_claims(repo, number, owner)
        if not any(c["name"] == name for c in remaining):
            _remove_label(repo, number, f"ia:{name}")
        raise
    return {"name": name, "session": session, "issue": number, "comment": comment["id"]}


def release(config, number, name=None, session=None, automated=False):
    repo, owner = config["projeto"]["repositorio"], config["projeto"]["dono"]
    claims = active_claims(repo, number, owner)
    if not automated and claims and not any(c["name"] == name and c["session"] == session for c in claims):
        raise BbError(f"#{number}: só a sessão dona pode liberar a posse", EXIT_INVALID_STATE)
    selected = claims if automated else [c for c in claims if c["name"] == name and c["session"] == session]
    for current in selected:
        _close_claim(repo, current, "Posse liberada pelo merge." if automated else "Posse liberada pela sessão dona.")
    remaining = active_claims(repo, number, owner)
    live_names = {c["name"] for c in remaining}
    for label in labels(issue_data(repo, number)):
        if label.startswith("ia:") and label[3:] not in live_names and (automated or label == f"ia:{name}"):
            _remove_label(repo, number, label)
    if not remaining and "parada" in labels(issue_data(repo, number)):
        _remove_label(repo, number, "parada")


def timestamp(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def last_activity(config, number, claims):
    """GitHub server timestamps of acquisition and push heartbeats, never user-controlled commit dates."""
    dates = [timestamp(c["created_at"]) for c in claims]
    dates.extend(timestamp(c["last_push"]) for c in claims if c.get("last_push"))
    return max(dates) if dates else None


def touch(config, number):
    repo, owner = config["projeto"]["repositorio"], config["projeto"]["dono"]
    for current in active_claims(repo, number, owner):
        # Append-only telemetry cannot resurrect a session released while the push event was being processed.
        api(f"repos/{repo}/issues/{number}/comments", "POST",
            body=f"<!-- bb:push sessao={current['session']} -->\nPush registrado para `{current['name']}`.")
    claims = active_claims(repo, number, owner)
    if claims and not stale(config, number, claims) and "parada" in labels(issue_data(repo, number)):
        _remove_label(repo, number, "parada")


def stale(config, number, claims, now=None):
    activity = last_activity(config, number, claims)
    now = now or datetime.datetime.now(UTC)
    return activity is not None and now - activity > datetime.timedelta(hours=config["ias"]["trava_expira_horas"])


def recover(config, number, name, phrase):
    if not phrase or not phrase.strip():
        raise BbError("--forcar exige --frase com a ordem do dono", EXIT_USAGE)
    repo, owner = config["projeto"]["repositorio"], config["projeto"]["dono"]
    claims = _preflight(config, number, name, allow_occupied=True)
    if not claims or not stale(config, number, claims):
        raise BbError(f"#{number}: posse ainda ativa; --forcar recusado", EXIT_INVALID_STATE)
    api(f"repos/{repo}/issues/{number}/comments", "POST",
        body=f"**Ordem do dono para retomar a posse** (`{name}`):\n\n" + "\n".join("> " + line for line in phrase.splitlines()))
    refreshed = active_claims(repo, number, owner)
    if {c["session"] for c in refreshed} != {c["session"] for c in claims} or not stale(config, number, refreshed):
        raise BbError(f"#{number}: posse mudou ou recebeu push durante a retomada; --forcar recusado",
                      EXIT_INVALID_STATE)
    claims = refreshed
    for current in claims:
        _close_claim(repo, current, "Posse retomada por ordem do dono; histórico preservado.")
    live_names = {c["name"] for c in active_claims(repo, number, owner)}
    for label in labels(issue_data(repo, number)):
        if (label.startswith("ia:") and label[3:] not in live_names) or (label == "parada" and not live_names):
            _remove_label(repo, number, label)
    return claim(config, number, name)
