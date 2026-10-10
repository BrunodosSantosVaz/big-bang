"""The v3 board state machine (ADR-0023): fifteen states, transitions per card kind and route, and the facts each
transition needs. Pure rules: callers gather the facts from GitHub, this module only decides.

Facts (all optional, safe defaults): labels (set), claimed, branch, pr_open, pr_merged, subissues_total,
subissues_open, blocked_by_open, candidate, qa (human|agent|not-applicable|pending), qa_decision (pending|approved|
automatic), prototype (pending|required|waived), flag (pending|required|waived), flag_on, delivery (set of deploy|
package|docs|repository), merged_permanent, delivered, accepted, selected, ready_problems (list), triaged.
"""
from . import names

STATES = ("Brainstorm", "Backlog", "Refinement", "Prototyping", "Ready", "Selected", "In Progress", "Todo",
          "Coding", "In Review", "QA", "Releasing", "Done", "Rejected", "Cancelled")
KINDS = ("epic", "task", "bug")
KIND_NAMES = {"epic": "épico", "task": "tarefa", "bug": "bug"}
ALLOWED = {
    "Brainstorm": {"epic", "bug"}, "Backlog": {"epic", "bug"}, "Refinement": {"epic"}, "Prototyping": {"epic"},
    "Ready": {"epic", "bug"}, "Selected": {"epic", "bug"}, "In Progress": {"epic"}, "Todo": {"task"},
    "Coding": {"task", "bug"}, "In Review": {"task", "bug"}, "QA": {"epic", "bug"}, "Releasing": {"epic", "bug"},
    "Done": set(KINDS), "Rejected": set(KINDS), "Cancelled": set(KINDS),
}
FORWARD = {
    "epic": {"Brainstorm": {"Backlog"}, "Backlog": {"Refinement"}, "Refinement": {"Prototyping", "Ready"},
             "Prototyping": {"Ready"}, "Ready": {"Selected", "Refinement"}, "Selected": {"In Progress", "Ready"},
             "In Progress": {"QA", "Releasing", "Done"}, "QA": {"Releasing"}, "Releasing": {"Done"}},
    "task": {"Todo": {"Coding"}, "Coding": {"In Review", "Todo"}, "In Review": {"Done", "Coding"}},
    "bug": {"Brainstorm": {"Backlog"}, "Backlog": {"Ready"}, "Ready": {"Selected"}, "Selected": {"Coding"},
            "Coding": {"In Review", "Selected"}, "In Review": {"QA", "Done", "Coding", "Releasing"},
            "QA": {"Releasing"},
            "Releasing": {"Done"}},
}
# Where a validation may send its card back (proposal section 6): origin -> allowed return states.
REJECT_RETURNS = {
    "epic": {"Refinement": {"Refinement"}, "Prototyping": {"Prototyping", "Refinement"},
             "In Progress": {"In Progress"}, "QA": {"In Progress"}, "Releasing": {"Releasing", "In Progress"}},
    "task": {"In Review": {"Todo", "Coding"}, "Coding": {"Todo"}},
    "bug": {"In Review": {"Selected", "Coding"}, "QA": {"Selected"}, "Releasing": {"Releasing", "Selected"}},
}
REASONS = ("requirements", "prototype", "tests", "code", "security", "docs", "qa", "release")
IMPEDIMENTS = ("blocked", "conflict", "stale", "on-hold")
TERMINAL = ("Done", "Cancelled")
TYPE_LABELS = {"type:epic": "epic", "type:task": "task", "type:test": "task", "type:docs": "task",
               "type:bug": "bug"}


def kind(labels):
    """Card kind from its labels in either dialect; None when absent or contradictory."""
    found = {TYPE_LABELS[names.label(label, "v3")] for label in labels if names.label(label, "v3") in TYPE_LABELS}
    return found.pop() if len(found) == 1 else None


def _has(facts, v3_label):
    labels = facts.get("labels", set())
    return v3_label in labels or names.label(v3_label, "legacy") in labels


def targets(card_kind, current):
    """States reachable from `current` in principle (facts decide whether a transition is allowed now)."""
    if current in TERMINAL:
        return set()
    if current == "Rejected":
        return set(_returns(card_kind)) | {"Cancelled"}
    result = set(FORWARD.get(card_kind, {}).get(current, set()))
    if current in REJECT_RETURNS.get(card_kind, {}):
        result.add("Rejected")
    return result | {"Cancelled"}


def _returns(card_kind):
    return {state for options in REJECT_RETURNS.get(card_kind, {}).values() for state in options}


def problems(card_kind, current, target, facts, *, reason=None, return_to=None):
    """Why `current -> target` is not allowed now (empty list = allowed)."""
    for state in (current, target):
        if state not in STATES:
            return [f"estado desconhecido: {state}"]
    if card_kind not in KINDS:
        return [f"tipo de cartão desconhecido: {card_kind}"]
    for state in (current, target):
        if card_kind not in ALLOWED[state]:
            return [f"o estado {state} não existe para {KIND_NAMES[card_kind]}"]
    if current in TERMINAL:
        return [f"{current} é final: abra outra issue para novo trabalho"]
    if target == "Cancelled":
        return [] if reason and str(reason).strip() else ["cancelar exige motivo registrado"]
    if current == "Rejected":
        if not return_to:
            return ["sair de Rejected exige o retorno registrado na reprovação"]
        if target != return_to:
            return [f"o retorno registrado é {return_to}, não {target}"]
        impediments = [label for label in IMPEDIMENTS if _has(facts, label)]
        return [f"impedimento ativo ({', '.join(impediments)}): resolva antes de retomar"] if impediments else []
    if target == "Rejected":
        return _rejection_problems(card_kind, current, facts, reason, return_to)
    if target not in FORWARD.get(card_kind, {}).get(current, set()):
        return [f"transição não permitida: {current} → {target}"]
    impediments = [label for label in IMPEDIMENTS if _has(facts, label)]
    if impediments:
        return [f"impedimento ativo ({', '.join(impediments)}): resolva antes de avançar"]
    return _preconditions(card_kind, current, target, facts)


def _rejection_problems(card_kind, current, facts, reason, return_to):
    allowed = REJECT_RETURNS.get(card_kind, {}).get(current)
    if allowed is None:
        return [f"{current} não é uma etapa de validação: nada para reprovar"]
    found = []
    if reason not in REASONS:
        found.append(f"motivo da reprovação deve ser um de: {', '.join(REASONS)}")
    if return_to not in allowed:
        found.append(f"retorno de {current} deve ser um de: {', '.join(sorted(allowed))}")
    elif return_to == "Coding" and not facts.get("claimed"):
        found.append("voltar direto a Coding exige posse válida; sem ela o retorno é Todo/Selected")
    return found


def _preconditions(card_kind, current, target, facts):
    if card_kind == "bug" and (current, target) in BUG_AS_TASK:
        key = ("task", current, target)
    elif card_kind == "bug" and (current, target) not in BUG_OWN:
        key = ("epic", current, target)  # same gate as an epic (backlog, selection, QA, release)
    else:
        key = (card_kind, current, target)
    check = PRECONDITIONS.get(key)
    return check(facts) if check else []


def _need(condition, message):
    return [] if condition else [message]


def _done_subissues(facts):
    return _need(facts.get("subissues_total", 0) > 0 and facts.get("subissues_open", 0) == 0,
                 "todas as sub-issues obrigatórias precisam estar concluídas")


def _flag_decided(facts):
    return _need(facts.get("flag") in ("required", "waived"), "decisão de feature flag pendente (required/waived)")


PRECONDITIONS = {
    ("epic", "Brainstorm", "Backlog"): lambda f: _need(f.get("accepted"), "a demanda precisa ser aceita"),
    ("epic", "Backlog", "Refinement"): lambda f: _need(f.get("claimed"), "o refinamento precisa de posse"),
    ("epic", "Refinement", "Prototyping"): lambda f: (
        _need(_has(f, "approved:refinement") or f.get("gate_delegated"), "refinamento ainda não aprovado")
        + _need(f.get("prototype") == "required", "protótipo não marcado como necessário")),
    ("epic", "Refinement", "Ready"): lambda f: (
        _need(_has(f, "approved:refinement") or f.get("gate_delegated"), "refinamento ainda não aprovado")
        + _need(f.get("prototype") == "waived", "protótipo necessário ou sem decisão: passe por Prototyping")
        + _flag_decided(f) + list(f.get("ready_problems", []))),
    ("epic", "Prototyping", "Ready"): lambda f: (
        _need(_has(f, "approved:prototype") or f.get("gate_delegated"), "protótipo ainda não aprovado") + _flag_decided(f)
        + list(f.get("ready_problems", []))),
    ("epic", "Ready", "Selected"): lambda f: (
        _need(f.get("selected"), "seleção explícita para a sprint ausente")
        + _need(f.get("blocked_by_open", 0) == 0, "depende de issue ainda aberta")),
    ("epic", "Selected", "In Progress"): lambda f: _need(f.get("subissues_total", 0) > 0,
                                                         "plano de tarefas ainda não criado"),
    ("epic", "In Progress", "QA"): lambda f: (
        _done_subissues(f) + _need(f.get("qa") in ("human", "agent"), "QA não se aplica: use Releasing ou Done")
        + _need(f.get("candidate"), "candidata ainda não disponível")),
    ("epic", "In Progress", "Releasing"): lambda f: (
        _done_subissues(f) + _need(f.get("qa") == "not-applicable", "QA se aplica: passe por QA")
        + _need("repository" not in f.get("delivery", set()), "entrega só no repositório: vá direto a Done")),
    ("epic", "In Progress", "Done"): lambda f: (
        _done_subissues(f) + _need(f.get("delivery") == {"repository"}, "há publicação a fazer: use Releasing")
        + _need(f.get("qa") == "not-applicable", "QA se aplica: passe por QA")
        + _need(f.get("merged_permanent"), "falta integrar na branch permanente com CI verde")),
    ("epic", "QA", "Releasing"): lambda f: _need(
        _has(f, "qa:approved") or f.get("qa_decision") in ("approved", "automatic") or f.get("gate_delegated"),
        "QA ainda não aprovado"),
    ("epic", "Releasing", "Done"): lambda f: (
        _need(f.get("delivered"), "entrega efetiva ainda não comprovada")
        + _need(f.get("flag") != "required" or f.get("flag_on"), "a feature flag do épico ainda está desligada")),
    ("task", "Todo", "Coding"): lambda f: (
        _need(f.get("claimed"), "posse não confirmada") + _need(f.get("branch"), "branch da tarefa não existe")
        + _need(f.get("blocked_by_open", 0) == 0, "dependência ainda aberta")),
    ("task", "Coding", "In Review"): lambda f: _need(f.get("pr_open"), "PR ainda não aberto"),
    ("task", "Coding", "Todo"): lambda f: _need(not f.get("claimed"), "libere a posse antes de voltar a Todo"),
    ("task", "In Review", "Done"): lambda f: _need(f.get("pr_merged"), "PR ainda não mesclado"),
    ("task", "In Review", "Coding"): lambda f: _need(f.get("claimed"), "voltar a Coding exige posse válida"),
    ("bug", "Backlog", "Ready"): lambda f: _need(f.get("triaged"), "triagem (reprodução e severidade) pendente"),
    ("bug", "Selected", "Coding"): lambda f: (
        _need(f.get("claimed"), "posse não confirmada") + _need(f.get("branch"), "branch da correção não existe")),
    ("bug", "Coding", "Selected"): lambda f: _need(not f.get("claimed"), "libere a posse antes de voltar"),
    ("bug", "In Review", "QA"): lambda f: (
        _need(f.get("pr_merged"), "PR ainda não mesclado")
        + _need(f.get("qa") in ("human", "agent"), "QA não se aplica: conclua sem QA")),
    ("bug", "In Review", "Releasing"): lambda f: (
        _need(f.get("pr_merged"), "PR ainda não mesclado")
        + _need(f.get("qa") == "not-applicable", "QA se aplica: passe por QA")
        + _need(f.get("delivery") != {"repository"}, "entrega só no repositório: conclua em Done")),
    ("bug", "In Review", "Done"): lambda f: (
        _need(f.get("pr_merged"), "PR ainda não mesclado") + _need(f.get("qa") == "not-applicable", "QA se aplica")
        + _need(f.get("delivery") == {"repository"}, "há publicação a fazer: passe por QA/Releasing")),
}
BUG_OWN = {("Backlog", "Ready"), ("Selected", "Coding"), ("Coding", "Selected"), ("In Review", "QA"),
           ("In Review", "Done"), ("In Review", "Releasing")}
BUG_AS_TASK = {("Coding", "In Review"), ("In Review", "Coding")}
