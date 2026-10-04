"""Owner decisions as labels (spec 11.9) and the AI review approval (spec 11.8).

All AIs use the owner's account, so GitHub cannot tell who put a label. `bb decisao` makes every decision traceable:
it first comments the owner's own words, then puts the label. `bb revisao aprovar` only puts `pr-aprovado` when the
PR does not require the owner's review."""
import datetime
import json

from . import github, pipeline
from .errors import EXIT_USAGE, EXIT_VERIFICATION_FAILED, BbError

DECISIONS = ("refinamento-aprovado", "prototipo-aprovado", "testes-aprovados", "teste-alterado-aprovado",
             "homologado", "reprovado", "dono:revisao-ia", "pr-aprovado")
OPPOSITES = {"homologado": ("reprovado",), "reprovado": ("homologado",), "dono:revisao-ia": ("revisao-humana",)}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _labels(repository, number):
    return set(json.loads(github.run("api", f"repos/{repository}/issues/{number}", "--jq", "[.labels[].name]")))


def _comment(repository, number, body):
    github.run("api", "-X", "POST", f"repos/{repository}/issues/{number}/comments", "-f", f"body={body}",
               "--silent")


def _add_label(repository, number, label):
    github.run("api", "-X", "POST", f"repos/{repository}/issues/{number}/labels", "-f", f"labels[]={label}",
               "--silent")


def _remove_label(repository, number, label):
    try:
        github.run("api", "-X", "DELETE", f"repos/{repository}/issues/{number}/labels/{label}", "--silent")
    except BbError:
        pass  # the label was not there


def record_decision(repository, label, number, phrase, ai_name):
    """Comment the owner's phrase, then put the decision label (and drop its opposite)."""
    if label not in DECISIONS:
        raise BbError(f"{label} não é uma decisão do dono; use uma de: {', '.join(DECISIONS)}", EXIT_USAGE)
    if not phrase or not phrase.strip():
        raise BbError("informe a frase do dono (--frase), com as palavras dele", EXIT_USAGE)
    quoted = "\n".join(f"> {line}" for line in phrase.strip().splitlines())
    _comment(repository, number, f"**Decisão do dono:** `{label}`\n\n{quoted}\n\n"
                                 f"Registrada por `{ai_name}` em {_now()}, com `bb decisao`.")
    _add_label(repository, number, label)
    for opposite in OPPOSITES.get(label, ()):
        _remove_label(repository, number, opposite)


def review_blockers(pr_labels, issue_labels, head, changed_paths, diff_text, zones, marker):
    """Reasons why the AI may NOT approve this PR (empty = the AI review is enough)."""
    owner_says_ai = "dono:revisao-ia" in pr_labels or "dono:revisao-ia" in issue_labels
    kind, issue = pipeline.branch_issue(head)
    if kind == "teste":
        if "testes-revisao-humana" in issue_labels and not owner_says_ai:
            return ["os testes de aceite deste épico são revisados pelo dono (testes-revisao-humana): ele põe "
                    "testes-aprovados"]
        return []
    if owner_says_ai:
        return []
    if "revisao-humana" in pr_labels:
        return ["o PR tem revisao-humana: só o dono põe pr-aprovado"]
    allow_acceptance = issue is not None and pipeline.only_own_marks_released(diff_text, issue, marker)
    sensitive = pipeline.sensitive_paths(changed_paths, zones, acceptance_allowed=allow_acceptance)
    if sensitive:
        return [f"o PR toca zona sensível ({', '.join(sensitive[:3])}): a revisão é do dono"]
    return []


def approve_review(repository, number, ai_name, zones, marker, report=""):
    data = json.loads(github.run("pr", "view", str(number), "--repo", repository, "--json",
                                 "headRefName,labels,state"))
    if data["state"] != "OPEN":
        raise BbError(f"o PR #{number} não está aberto", EXIT_USAGE)
    pr_labels = {label["name"] for label in data["labels"]}
    _, issue = pipeline.branch_issue(data["headRefName"])
    issue_labels = _labels(repository, issue) if issue else set()
    diff_text = github.run("pr", "diff", str(number), "--repo", repository)
    changed = [line.split(" b/", 1)[1] for line in diff_text.splitlines() if line.startswith("diff --git ")]
    blockers = review_blockers(pr_labels, issue_labels, data["headRefName"], changed, diff_text, zones, marker)
    if blockers:
        raise BbError("bb revisao aprovar recusado: " + "; ".join(blockers), EXIT_VERIFICATION_FAILED)
    body = f"**Revisão da IA: aprovado** (`{ai_name}`, {_now()}, contexto limpo: `.bigbang/agents/revisor-pr.md`)."
    if report.strip():
        body += "\n\n" + report.strip()
    _comment(repository, number, body)
    _add_label(repository, number, "pr-aprovado")
