"""The v3 single board (ADR-0023): label catalog, Project fields, the state of each card derived from the receipts
of its issue, validated moves and reconciliation. The issue is the source of truth; the Project only shows it.

A Project adapter has: fields(), ensure_field(name, type, options), add(number), set(number, field, value),
get(number, field), items(). ProjectGraphQL talks to GitHub; the tests use an in-memory one."""
import datetime
import json

from . import config as config_module
from . import autonomy, names, pipeline, policy, receipts, states
from .errors import EXIT_INVALID_STATE, EXIT_USAGE, BbError
from .locks import expired

# --- labels (name, color, description) --------------------------------------------------------------------------------

LABELS = (
    ("type:epic", "5319E7", "Épico: agrupa as tarefas de um objetivo (issue pai)"),
    ("type:task", "1D76DB", "Tarefa do tamanho de um PR"),
    ("type:test", "0E8A16", "Testes de aceite do épico, escritos antes das tarefas"),
    ("type:docs", "0075CA", "Documentação do épico (última tarefa)"),
    ("type:bug", "D73A4A", "Defeito: unidade pequena de release"),
    ("type:foundation", "1D76DB", "Etapa da Fundação (F0 a F5)"),
    ("area:ui", "C5DEF5", "Interface"), ("area:api", "C5DEF5", "API"), ("area:data", "C5DEF5", "Dados"),
    ("area:auth", "C5DEF5", "Autenticação e autorização"), ("area:infra", "C5DEF5", "Infraestrutura"),
    ("area:ci", "C5DEF5", "Esteira e CI"), ("area:docs", "C5DEF5", "Documentação"),
    ("risk:low", "C2E0C6", "Risco baixo"), ("risk:medium", "FBCA04", "Risco médio"),
    ("risk:high", "D93F0B", "Risco alto"), ("risk:critical", "B60205", "Risco crítico: dono decide"),
    ("no-release", "BFD4F2", "Não muda o artefato: sem versão nem homologação"),
    ("prototype:required", "F9D0C4", "O épico precisa de protótipo aprovado"),
    ("prototype:waived", "EDEDED", "Protótipo dispensado com decisão registrada"),
    ("flag:required", "F9D0C4", "O épico entra atrás de feature flag"),
    ("flag:waived", "EDEDED", "Feature flag dispensada (não muda comportamento do artefato)"),
    ("qa:human", "C5DEF5", "Homologação pelo dono"), ("qa:agent", "C5DEF5", "Homologação por agente independente"),
    ("qa:not-applicable", "EDEDED", "Sem homologação de produto (docs, testes, esteira)"),
    ("review:ai", "C5DEF5", "PRs revisados por IA independente"), ("review:human", "FBCA04", "PRs revisados pelo dono"),
    ("tests-review:ai", "C5DEF5", "Testes de aceite revisados por IA"),
    ("tests-review:human", "FBCA04", "Testes de aceite revisados pelo dono"),
    ("approved:refinement", "0E8A16", "Decisão do dono: refinamento aprovado"),
    ("approved:prototype", "0E8A16", "Decisão do dono: protótipo aprovado"),
    ("approved:tests", "0E8A16", "Decisão do dono: testes de aceite aprovados"),
    ("approved:test-change", "D93F0B", "Decisão do dono: mudança em testes de aceite aprovada"),
    ("approved:backlog", "0E8A16", "Decisão do dono: a demanda entra no backlog"),
    ("approved:selection", "0E8A16", "Decisão do dono: o épico entra na próxima sprint"),
    ("approved:cancel", "B60205", "Decisão do dono: o épico é cancelado"),
    ("qa:approved", "0E8A16", "Decisão do dono: homologado"), ("qa:rejected", "B60205", "Decisão do dono: reprovado"),
    ("owner:ai-review", "5319E7", "Decisão do dono: a revisão volta para a IA"),
    ("pr:approved", "0E8A16", "PR aprovado pela revisão exigida"),
    ("blocked", "B60205", "Impedimento: aguardando algo externo"),
    ("conflict", "B60205", "Impedimento: conflito ao integrar"),
    ("stale", "FEF2C0", "Impedimento: posse vencida (projeção da trava)"),
    ("on-hold", "FEF2C0", "Impedimento: pausado por decisão"),
    ("expedite", "B60205", "Urgência autorizada; não dispensa portões"),
    ("blocks-production", "B60205", "Nenhuma publicação passa enquanto estiver aberta"),
    ("reason:requirements", "D4C5F9", "Reprovado por requisitos"), ("reason:prototype", "D4C5F9", "Reprovado no protótipo"),
    ("reason:tests", "D4C5F9", "Reprovado nos testes"), ("reason:code", "D4C5F9", "Reprovado no código"),
    ("reason:security", "D4C5F9", "Reprovado por segurança"), ("reason:docs", "D4C5F9", "Reprovado na documentação"),
    ("reason:qa", "D4C5F9", "Reprovado na homologação"), ("reason:release", "D4C5F9", "Reprovado na publicação"),
    ("severity:critical", "B60205", "Sistema fora, perda de dados ou segurança"),
    ("severity:high", "D93F0B", "Função principal quebrada sem alternativa"),
    ("severity:medium", "FBCA04", "Falha com contorno"), ("severity:low", "C2E0C6", "Cosmético ou raro"),
    ("hotfix", "B60205", "Correção urgente em produção"), ("security", "B60205", "Achado ou trabalho de segurança"),
    ("dependencies", "0366D6", "Atualização de dependências"),
    ("good first issue", "7057FF", "Bom para quem está começando"), ("help wanted", "008672", "Ajuda bem-vinda"),
)

# --- Project fields -------------------------------------------------------------------------------------------------

FIELDS = (
    ("Status", "SINGLE_SELECT", states.STATES),
    ("Priority", "SINGLE_SELECT", ("P0", "P1", "P2", "P3")),
    ("Size", "SINGLE_SELECT", ("XS", "S", "M", "L", "XL")),
    ("Sprint", "SINGLE_SELECT", ("Sem sprint",)),
    ("Awaiting", "SINGLE_SELECT", ("owner", "agent", "ci", "external")),
    ("QA decision", "SINGLE_SELECT", ("pending", "approved", "automatic", "not-applicable")),
    ("Prototype", "SINGLE_SELECT", ("pending", "required", "waived")),
    ("Flag", "SINGLE_SELECT", ("pending", "required", "waived")),
    ("Executor", "TEXT", None), ("Session", "TEXT", None), ("Lease expires", "DATE", None),
    ("Attempt", "NUMBER", None),
    ("Rejected from", "SINGLE_SELECT", states.STATES), ("Return to", "SINGLE_SELECT", states.STATES),
    ("Tested SHA", "TEXT", None), ("Candidate", "TEXT", None),
)
# Which gate (policy.GATES) a forward move passes; moves not listed need no approval beyond their facts.
GATE_OF = {("Brainstorm", "Backlog"): "backlog", ("Refinement", "Ready"): "refinement",
           ("Refinement", "Prototyping"): "refinement", ("Prototyping", "Ready"): "prototype",
           ("Ready", "Selected"): "selection", ("QA", "Releasing"): "qa",
           ("QA", "Rejected"): "qa", ("Releasing", "Done"): "publish"}
PLANNING_GATES = ("backlog", "refinement", "prototype", "selection", "cancel")
# The decision label that records the owner's approval of a gate (bb decision writes it with his words). The
# identity of whoever runs a command is never an approval: on a personal account the owner and the AIs share it.
DECISION_OF = {"backlog": "approved:backlog", "refinement": "approved:refinement", "prototype": "approved:prototype",
               "selection": "approved:selection", "qa": "qa:approved", "tests": "approved:tests",
               "cancel": "approved:cancel"}
INITIAL = {"epic": "Brainstorm", "bug": "Brainstorm", "task": "Todo"}


def ensure_labels(client):
    """Create the v3 labels that are missing; returns how many were created."""
    return sum(client.ensure_label(name, color, description) for name, color, description in LABELS)


def ensure_fields(project):
    for name, field_type, options in FIELDS:
        current = project.fields().get(name)
        if name == "Sprint" and current:
            continue  # sprint options are created by the sprint flow and must be kept
        project.ensure_field(name, field_type, list(options) if options else None)


def _iso(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trusted(config):
    return {config_module.get(config, "project.owner")}


def history(client, number, trusted):
    """Transition and rejection receipts of an issue, in order."""
    return [r for r in receipts.parse(client.comments(number), trusted) if r["kind"] in ("transition", "rejection")]


def current_state(client, number, trusted, issue=None):
    moves = history(client, number, trusted)
    if moves:
        return moves[-1]["to"]
    issue = issue or client.issue(number)
    kind = states.kind(set(issue["labels"])) if issue else None
    return INITIAL.get(kind, "Brainstorm")


def _label_value(labels, prefix, values, default):
    found = [label.split(":", 1)[1] for label in labels if label.startswith(prefix)]
    found = [value for value in found if value in values]
    return found[0] if len(found) == 1 else default


def facts(client, config, number, *, now=None):
    """The facts of states.problems gathered from GitHub (labels, lock, branch, hierarchy, dependencies)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    issue = client.issue(number)
    labels = set(issue["labels"])
    lock = client.locks().current(f"issue-{number}")
    subissues = client.sub_issues(number)
    branch_prefixes = [f"{kind}/{number}-" for kind in ("test", "feature", "docs", "fix", "bugfix", "hotfix")]
    profile = config_module.get(config, "delivery.profile")
    delivery = {"repository"} if "no-release" in labels else {"package" if profile == "compiled" else "deploy"}
    return {"labels": {names.label(label, "v3") for label in labels} | labels,
            "claimed": bool(lock) and not expired(lock, now),
            "branch": any(client.branches(prefix) for prefix in branch_prefixes),
            "subissues_total": len(subissues),
            "subissues_open": sum(1 for sub in subissues if sub["state"] == "open"),
            "blocked_by_open": sum(1 for blocker in client.blocked_by(number) if blocker["state"] == "open"),
            "qa": _label_value(labels, "qa:", ("human", "agent", "not-applicable"), "pending"),
            "qa_decision": "approved" if "qa:approved" in labels or "homologado" in labels else "pending",
            "prototype": _label_value(labels, "prototype:", ("required", "waived"), "pending"),
            "flag": _label_value(labels, "flag:", ("required", "waived"), "pending"),
            "flag_on": False, "delivery": delivery, "candidate": False, "delivered": False,
            "merged_permanent": False, "pr_open": False, "pr_merged": False, "triaged": "triaged" in labels,
            "ready_problems": []}


def attempts(client, number, trusted):
    """Rejections recorded for a card (the attempt counter comes from receipts, the board only shows it)."""
    return sum(1 for receipt in history(client, number, trusted) if receipt["kind"] == "rejection")


# Decisions withdrawn when a card goes back (rejected or not): a decision of a past cycle never approves the next one.
WITHDRAWN_ON_RETURN = {
    "Refinement": ("approved:refinement", "approved:prototype", "approved:selection", "qa:approved", "qa:rejected"),
    "Prototyping": ("approved:prototype", "approved:selection", "qa:approved", "qa:rejected"),
    "Ready": ("approved:selection", "qa:approved", "qa:rejected"),
    "In Progress": ("qa:approved", "qa:rejected"),
    "Selected": ("qa:approved", "qa:rejected"),
}
BACKWARD = {("Ready", "Refinement"), ("Selected", "Ready")}


def record_qa(client, config, number, *, candidate, digest, verdict, approver, now=None):
    """Record the QA verdict of an independent agent on a candidate (the evidence of a delegated QA gate)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if verdict not in ("approved", "rejected"):
        raise BbError("veredito de QA deve ser approved ou rejected", EXIT_USAGE)
    agents = config_module.get(config, "agents.names") or []
    if approver not in agents or approver.casefold() in {login.casefold() for login in _trusted(config)}:
        raise BbError(f"veredito de QA só de um agente declarado em agents.names (recebido: {approver})", EXIT_USAGE)
    receipt = {"kind": "qa", "event_id": f"qa-{number}-{candidate}-{approver}-{_iso(now)}", "issue": number,
               "actor": approver, "at": _iso(now), "candidate": candidate, "digest": digest, "verdict": verdict,
               "approver": approver}
    found = receipts.problems(receipt)
    if found:
        raise BbError("; ".join(found), EXIT_USAGE)
    client.comment(number, receipts.render(receipt))
    return receipt


def _independent_qa(client, number, receipts_now, actor, trusted, candidate=None):
    """Verdict ('approved' | 'rejected') of the last QA receipt recorded after the card entered QA, for the current
    candidate, by an agent that neither moves the card nor held any claim on the epic or its sub-issues (who
    delivers never homologates); None when there is no such evidence."""
    entered = max((i for i, r in enumerate(receipts_now) if r["kind"] in ("transition", "rejection")
                   and r.get("to") == "QA"), default=None)
    verdicts = [r for r in receipts_now[entered + 1:] if r["kind"] == "qa"] if entered is not None else []
    if not verdicts or not candidate or verdicts[-1]["candidate"] != candidate:
        return None  # no candidate on the card, or another candidate homologated: the bytes going out were not seen
    delivered_by = {actor.casefold()}
    for issue in [number] + [child["number"] for child in client.sub_issues(number)]:
        found = receipts_now if issue == number else receipts.parse(client.comments(issue), trusted)
        delivered_by |= {r["actor"].casefold() for r in found if r["kind"] == "claim"}
    if verdicts[-1]["approver"].casefold() in delivered_by:
        return None
    return verdicts[-1]["verdict"]


def _born(client, number, issue):
    """When the oldest piece of work of a card was created (the card itself or any sub-issue): no PR of that work
    can be older. Unknown creation dates mean no bound."""
    dates = [issue.get("created_at")] + [child.get("created_at") for child in client.sub_issues(number)]
    return None if None in dates else min(dates)


def _gate(card_kind, current, target):
    if target == "Cancelled" and card_kind in ("epic", "bug"):
        return "cancel"
    return GATE_OF.get((current, target))


def _epic_paths(client, number, since=None):
    """Files changed by the merged PRs of an epic's sub-issues (the evidence of a QA or publication risk). Only the
    PRs updated since the card or its oldest sub-issue was created are read (the card's own PRs included): its
    work cannot be older than that."""
    children = {child["number"] for child in client.sub_issues(number)} | {number}
    paths = set()
    page = 1
    while True:
        _, items = client.call("GET", f"pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}")
        for raw in items or []:
            if since and raw.get("updated_at") and raw["updated_at"] < since:
                return sorted(paths)
            if not raw.get("merged_at") and not raw.get("merged"):
                continue
            _, issue = pipeline.branch_issue(raw["head"]["ref"])
            if issue in children:
                for file in client.paginate(f"pulls/{raw['number']}/files"):
                    paths.add(file["filename"])
                    if file.get("previous_filename"):
                        paths.add(file["previous_filename"])
        if len(items or []) < 100:
            return sorted(paths)
        page += 1


def _gate_decision(config, client, number, card_kind, current, target, labels, since=None, now=None):
    """(gate, approver, risk) of a move, or (None, None, None) when no gate applies."""
    gate = _gate(card_kind, current, target)
    if gate is None:
        return None, None, None
    if gate in PLANNING_GATES:
        risk = policy.planning_risk(labels)
    else:
        risk = policy.delivery_risk(labels, _epic_paths(client, number, since),
                                    config_module.get(config, "security.sensitive_paths"))
    today = (now or datetime.datetime.now(datetime.timezone.utc)).date()
    who = policy.approver(policy.mode(config), gate, risk, autonomy.usable(config, today))
    if gate == "qa" and who == "agent" and "qa:human" in labels:
        who = "owner"  # the card asks for the owner's homologation: no mode or risk delegates it
    return gate, who, risk


def _approval_problems(config, card_kind, current, target, gathered, decision):
    gate, who, risk = decision
    if gate is None:
        return []
    mode = policy.mode(config)
    labels = gathered["labels"]
    if who == "agent":
        if (current, target) == ("QA", "Rejected") and not gathered.get("qa_agent_rejected") and \
                "qa:rejected" not in labels and names.label("qa:rejected", "legacy") not in labels:
            return ["reprovação de QA delegada sem evidência: registre o veredito rejected de um agente "
                    "independente (bb qa verdict) ou a decisão qa:rejected do dono"]
        return []
    if gate == "publish" and gathered.get("delivered"):
        return []  # the publish job only runs after the owner approved the production environment
    evidence = "qa:rejected" if (current, target) == ("QA", "Rejected") else DECISION_OF.get(gate)
    if evidence and (evidence in labels or names.label(evidence, "legacy") in labels):
        return []  # the owner's recorded decision passes any gate, also one outside the autonomy contract
    if who == "blocked":
        reasons = autonomy.problems(config, gathered.get("today") or datetime.datetime.now(datetime.timezone.utc).date())
        return [f"portão {gate} fora do contrato do modo {mode} (risco {risk}): bloqueado para o agente; só a "
                f"decisão registrada {evidence or 'do dono'} libera"] + [f"  {reason}" for reason in reasons]
    return [f"portão {gate} é do dono no modo {mode} (risco {risk}): falta a decisão registrada "
            f"{evidence or ''} (bb decision, com as palavras dele)".replace(" )", ")")]


def move(client, project, config, number, target, actor, *, reason=None, return_to=None, facts=None,
         event_id=None, sha=None, now=None, dry_run=False):
    """Validate and apply one transition; returns the receipt written (or found, on replay). With dry_run, only
    validates: returns the receipt that would be written and changes nothing."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    trusted = _trusted(config)
    issue = client.issue(number)
    if not issue or issue["pull_request"]:
        raise BbError(f"#{number} não é uma issue", EXIT_USAGE)
    card_kind = states.kind(set(issue["labels"]))
    if card_kind is None:
        raise BbError(f"#{number} sem tipo (type:epic, type:task, type:test, type:docs ou type:bug)", EXIT_INVALID_STATE)
    receipts_now = receipts.parse(client.comments(number), trusted)
    if event_id and receipts.find(receipts_now, event_id):
        return receipts.find(receipts_now, event_id)
    moves = [r for r in receipts_now if r["kind"] in ("transition", "rejection")]
    current = moves[-1]["to"] if moves else INITIAL.get(card_kind, "Brainstorm")
    recorded_return = moves[-1].get("return_to") if moves and moves[-1]["kind"] == "rejection" else None
    gathered = globals()["facts"](client, config, number, now=now)
    gathered.update(facts or {})
    gathered["accepted"] = gathered["selected"] = True  # the approval check below is their evidence
    decision = _gate_decision(config, client, number, card_kind, current, target, gathered["labels"],
                              since=_born(client, number, issue), now=now)
    gathered["gate_delegated"] = decision[1] == "agent"
    if decision[0] == "qa" and decision[1] == "agent":
        verdict = _independent_qa(client, number, receipts_now, actor, trusted, project.get(number, "Candidate"))
        if verdict == "approved":
            gathered["qa_decision"] = "automatic"
        gathered["qa_agent_rejected"] = verdict == "rejected"
    gathered["today"] = now.date()
    if card_kind == "epic" and target == "In Progress" and current in ("Selected", "Rejected") and \
            policy.mode(config) == "autonomous":
        limit = policy.limits(config, now.date())["epics_in_progress"]
        busy = [other["number"] for other in client.issues("open", labels=["type:epic"])
                if other["number"] != number and current_state(client, other["number"], trusted) in ("In Progress", "QA")]
        if len(busy) >= limit:
            raise BbError(f"#{number}: WIP do contrato atingido ({limit} épico(s) em andamento: "
                          + ", ".join(f"#{n}" for n in busy) + ")", EXIT_INVALID_STATE)
    found = states.problems(card_kind, current, target, gathered, reason=reason,
                            return_to=recorded_return if current == "Rejected" else return_to)
    found += [] if found else _approval_problems(config, card_kind, current, target, gathered, decision)
    if found:
        raise BbError(f"#{number}: {current} → {target} recusado:\n" + "\n".join(f"  - {p}" for p in found),
                      EXIT_INVALID_STATE)
    _, policy_hash = policy.snapshot({"mode": policy.mode(config), "limits": policy.limits(config, now.date())})
    receipt = {"event_id": event_id or f"move-{number}-{len(moves) + 1}-{target}", "issue": number,
               "actor": actor, "at": _iso(now), "from": current, "to": target, "policy": policy_hash}
    if sha:
        receipt["sha"] = sha
    if decision[0]:  # who approved, never presented as someone else: an agent signs as an agent
        by = f"agent:{actor}" if decision[1] == "agent" else f"owner:{config_module.get(config, 'project.owner')}"
        receipt["approval"] = {"gate": decision[0], "by": by, "risk": decision[2], "mode": policy.mode(config)}
    if target == "Rejected":
        receipt.update(kind="rejection", reason=reason, return_to=return_to,
                       evidence=[f"reprovado em {current} por {actor}"])
    else:
        receipt["kind"] = "transition"
    if dry_run:
        return receipt
    done_attempts = attempts(client, number, trusted) + (1 if target == "Rejected" else 0)
    _effects(client, project, number, issue, card_kind, current, target, receipt, done_attempts)
    client.comment(number, receipts.render(receipt))  # recorded only after the effects happened
    if target == "Rejected" and done_attempts >= policy.limits(config)["attempts"]:
        client.add_labels(number, ["blocked"])
        client.comment(number, f"**Big Bang** · {done_attempts} reprovações: limite de tentativas atingido. O cartão "
                               "fica em Rejected com `blocked` até o dono decidir o próximo passo.")
    return receipt


def _effects(client, project, number, issue, card_kind, current, target, receipt, done_attempts):
    if target == "Done" and issue["state"] == "open":
        client.update_issue(number, state="closed", state_reason="completed")
    if target == "Cancelled" and issue["state"] == "open":
        client.update_issue(number, state="closed", state_reason="not_planned")
    project.add(number)
    project.set(number, "Status", target)
    returning_to = receipt.get("return_to") if target == "Rejected" else \
        (target if (current, target) in BACKWARD else None)
    for label in WITHDRAWN_ON_RETURN.get(returning_to, ()):
        for spelling in {label, names.label(label, "legacy")}:
            if spelling in issue["labels"]:
                client.remove_label(number, spelling)
    if target == "Rejected":
        client.add_labels(number, [f"reason:{receipt['reason']}"])
        project.set(number, "Rejected from", current)
        project.set(number, "Return to", receipt["return_to"])
    if current == "Rejected" or target == "Rejected":
        project.set(number, "Attempt", done_attempts)


def reconcile(client, project, config, *, now=None):
    """Put every open card (and every card already on the board) back in the state its receipts record. Returns
    the cards fixed; a manual move is reverted with a comment explaining why."""
    trusted = _trusted(config)
    fixed = []
    numbers = {issue["number"] for issue in client.issues("open")} | set(project.items())
    for number in sorted(numbers):
        issue = client.issue(number)
        if not issue or issue["pull_request"] or states.kind(set(issue["labels"])) is None:
            continue
        expected = current_state(client, number, trusted, issue)
        shown = project.get(number, "Status")
        if shown != expected:
            project.add(number)
            project.set(number, "Status", expected)
            if shown is not None:
                client.comment(number, f"**Big Bang** · movimento manual de *{shown}* desfeito: o estado registrado é "
                                       f"*{expected}*. Use `bb move` (o controlador confere portões e evidências).")
            fixed.append((number, shown, expected))
    return fixed


VIEWS = (("Board", "BOARD_LAYOUT"), ("Table", "TABLE_LAYOUT"), ("Roadmap", "ROADMAP_LAYOUT"))


def create_project(graphql, owner, title, repository):
    """Create (or find, by exact title) the single Project of a repository, link it and return its number. Views:
    Board, Table and Roadmap. Fields come from ensure_fields(ProjectGraphQL(...))."""
    data = graphql("query($l:String!){ user(login:$l){ id projectsV2(first:100){ nodes{ id number title } } } }",
                   {"l": owner})
    user = data.get("user") or {}
    existing = [node for node in (user.get("projectsV2") or {}).get("nodes", []) if node["title"] == title]
    if existing:
        project_id, number = existing[0]["id"], existing[0]["number"]
    else:
        created = graphql("mutation($o:ID!,$t:String!){ createProjectV2(input:{ownerId:$o, title:$t}){ "
                          "projectV2{ id number } } }", {"o": user["id"], "t": title})
        project_id = created["createProjectV2"]["projectV2"]["id"]
        number = created["createProjectV2"]["projectV2"]["number"]
    repo = graphql("query($o:String!,$r:String!){ repository(owner:$o,name:$r){ id } }",
                   {"o": repository.split("/")[0], "r": repository.split("/")[1]})
    graphql("mutation($p:ID!,$r:ID!){ linkProjectV2ToRepository(input:{projectId:$p, repositoryId:$r}){ "
            "repository{ id } } }", {"p": project_id, "r": repo["repository"]["id"]})
    views = graphql("query($id:ID!){ node(id:$id){ ... on ProjectV2 { views(first:20){ nodes{ id name } } } } }",
                    {"id": project_id})["node"]["views"]["nodes"]
    names_now = {view["name"] for view in views}
    if "Board" not in names_now and views:
        graphql("mutation($v:ID!){ updateProjectV2View(input:{viewId:$v, name:\"Board\", layout:BOARD_LAYOUT}){ "
                "projectV2View{ id } } }", {"v": views[0]["id"]})
        names_now.add("Board")
    for name, layout in VIEWS[1:]:
        if name not in names_now:
            graphql(f"mutation($p:ID!,$n:String!){{ createProjectV2View(input:{{projectId:$p, name:$n, "
                    f"layout:{layout}}}){{ projectV2View{{ id }} }} }}", {"p": project_id, "n": name})
    return number


class ProjectGraphQL:
    """Project (v2) of a user or organization through the GitHub GraphQL API (gh api graphql)."""

    def __init__(self, owner, number, repository, graphql):
        self.owner, self.number, self.repository, self.graphql = owner, number, repository, graphql
        self._id, self._fields, self._items = None, None, None

    def _project(self):
        if self._id is None:
            for kind in ("user", "organization"):
                data = self.graphql(f"query($l:String!,$n:Int!){{ {kind}(login:$l){{ projectV2(number:$n){{ id }} }} }}",
                                    {"l": self.owner, "n": self.number})
                node = (data.get(kind) or {}).get("projectV2") if data else None
                if node:
                    self._id = node["id"]
                    break
            if self._id is None:
                raise BbError(f"Project {self.owner}#{self.number} não encontrado", EXIT_INVALID_STATE)
        return self._id

    def _load_fields(self):
        data = self.graphql("query($id:ID!){ node(id:$id){ ... on ProjectV2 { fields(first:50){ nodes{ "
                            "... on ProjectV2FieldCommon { id name dataType } "
                            "... on ProjectV2SingleSelectField { options { id name } } } } } } }",
                            {"id": self._project()})
        self._fields = {}
        for node in data["node"]["fields"]["nodes"]:
            options = {option["name"]: option["id"] for option in node.get("options", [])}
            self._fields[node["name"]] = {"id": node["id"], "type": node["dataType"], "options": options}
        return self._fields

    def fields(self):
        return {name: {"type": spec["type"], "options": list(spec["options"])}
                for name, spec in (self._fields or self._load_fields()).items()}

    def ensure_field(self, name, field_type, options=None):
        fields = self._fields or self._load_fields()
        colors = ["GRAY", "BLUE", "GREEN", "YELLOW", "ORANGE", "RED", "PINK", "PURPLE"]
        payload = [{"name": option, "color": colors[index % len(colors)], "description": ""}
                   for index, option in enumerate(options or [])]
        if name not in fields:
            variables = {"p": self._project(), "n": name, "t": field_type}
            query = ("mutation($p:ID!,$n:String!,$t:ProjectV2CustomFieldType!{o}){{ createProjectV2Field(input:{{"
                     "projectId:$p, name:$n, dataType:$t{v} }}){{ projectV2Field{{ ... on ProjectV2FieldCommon {{ id }} }} }} }}")
            if payload:
                variables["o"] = payload
                query = query.format(o=",$o:[ProjectV2SingleSelectFieldOptionInput!]", v=", singleSelectOptions:$o")
            else:
                query = query.format(o="", v="")
            self.graphql(query, variables)
        elif payload and list(fields[name]["options"]) != list(options):
            for option in payload:  # keep the ids of the options that already exist
                if option["name"] in fields[name]["options"]:
                    option["id"] = fields[name]["options"][option["name"]]
            self.graphql("mutation($f:ID!,$o:[ProjectV2SingleSelectFieldOptionInput!]!){ updateProjectV2Field(input:{"
                         "fieldId:$f, singleSelectOptions:$o }){ projectV2Field{ ... on ProjectV2FieldCommon { id } } } }",
                         {"f": fields[name]["id"], "o": payload})
        self._fields = None

    def _load_items(self):
        self._items = {}
        cursor = None
        while True:
            data = self.graphql("query($id:ID!,$c:String){ node(id:$id){ ... on ProjectV2 { items(first:100, after:$c){ "
                                "pageInfo{ hasNextPage endCursor } nodes{ id content{ ... on Issue { number repository{ "
                                "nameWithOwner } } } fieldValues(first:30){ nodes{ "
                                "... on ProjectV2ItemFieldSingleSelectValue { name field{ ... on ProjectV2FieldCommon { name } } } "
                                "... on ProjectV2ItemFieldTextValue { text field{ ... on ProjectV2FieldCommon { name } } } "
                                "... on ProjectV2ItemFieldNumberValue { number field{ ... on ProjectV2FieldCommon { name } } } "
                                "... on ProjectV2ItemFieldDateValue { date field{ ... on ProjectV2FieldCommon { name } } } "
                                "} } } } } } }", {"id": self._project(), "c": cursor})
            items = data["node"]["items"]
            for node in items["nodes"]:
                content = node.get("content") or {}
                if (content.get("repository") or {}).get("nameWithOwner", "").casefold() != self.repository.casefold():
                    continue
                values = {}
                for value in node["fieldValues"]["nodes"]:
                    field = (value.get("field") or {}).get("name")
                    if field:
                        values[field] = next(value[key] for key in ("name", "text", "number", "date") if key in value)
                self._items[content["number"]] = {"id": node["id"], "values": values}
            if not items["pageInfo"]["hasNextPage"]:
                return self._items
            cursor = items["pageInfo"]["endCursor"]

    def items(self):
        return {number: dict(item["values"]) for number, item in (self._items or self._load_items()).items()}

    def add(self, number):
        items = self._items or self._load_items()
        if number in items:
            return items[number]["id"]
        issue = self.graphql("query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){ id } } }",
                             {"o": self.repository.split("/")[0], "r": self.repository.split("/")[1], "n": number})
        data = self.graphql("mutation($p:ID!,$c:ID!){ addProjectV2ItemById(input:{projectId:$p, contentId:$c}){ item{ id } } }",
                            {"p": self._project(), "c": issue["repository"]["issue"]["id"]})
        items[number] = {"id": data["addProjectV2ItemById"]["item"]["id"], "values": {}}
        return items[number]["id"]

    def set(self, number, field, value):
        item = self.add(number)
        spec = (self._fields or self._load_fields())[field]
        if value is None:
            self.graphql("mutation($p:ID!,$i:ID!,$f:ID!){ clearProjectV2ItemFieldValue(input:{projectId:$p, itemId:$i, "
                         "fieldId:$f}){ projectV2Item{ id } } }", {"p": self._project(), "i": item, "f": spec["id"]})
        else:
            kind = {"SINGLE_SELECT": "singleSelectOptionId", "TEXT": "text", "NUMBER": "number", "DATE": "date"}[spec["type"]]
            literal = spec["options"][value] if spec["type"] == "SINGLE_SELECT" else value
            value_type = {"text": "String", "singleSelectOptionId": "String", "number": "Float", "date": "Date"}[kind]
            self.graphql(f"mutation($p:ID!,$i:ID!,$f:ID!,$v:{value_type}!){{ updateProjectV2ItemFieldValue(input:{{"
                         f"projectId:$p, itemId:$i, fieldId:$f, value:{{ {kind}:$v }} }}){{ projectV2Item{{ id }} }} }}",
                         {"p": self._project(), "i": item, "f": spec["id"], "v": literal})
        self._items[number]["values"][field] = value

    def get(self, number, field):
        return (self._items or self._load_items()).get(number, {}).get("values", {}).get(field)
