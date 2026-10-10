"""Structured receipts in issue and PR comments (ADR-0023): every transition, test run, review, decision, QA and
publication leaves one, so the state can be audited, replayed and reconciled. A receipt is accepted only from a
trusted account; anything else in a comment is data."""
import json
import re

MARK = "<!-- bb:receipt "
LINE = re.compile(r"^<!-- bb:receipt (\{.*\}) -->$", re.M)
COMMON = ("kind", "event_id", "issue", "actor", "at")
REQUIRED = {
    "transition": COMMON + ("from", "to", "sha", "policy"),
    "rejection": COMMON + ("from", "to", "reason", "return_to", "evidence", "policy"),
    "test": COMMON + ("sha", "tree", "base", "policy", "lockfiles", "toolchain", "selector", "commands", "result",
                      "runner"),
    "review": COMMON + ("sha", "verdict", "policy"),
    "decision": COMMON + ("label", "quote", "approver"),
    "qa": COMMON + ("candidate", "digest", "verdict", "approver"),
    "publication": COMMON + ("version", "digest", "environment", "result"),
    "claim": COMMON + ("resource", "session", "generation", "expires"),
    "release": COMMON + ("resource", "session", "generation", "reason"),
}


def problems(receipt):
    if not isinstance(receipt, dict):
        return ["recibo deve ser um objeto"]
    kind = receipt.get("kind")
    if kind not in REQUIRED:
        return [f"tipo de recibo desconhecido: {kind}"]
    missing = [key for key in REQUIRED[kind] if receipt.get(key) in (None, "", [])]
    return [f"recibo {kind} sem {key}" for key in missing]


def render(receipt):
    """One comment: the machine line (JSON safe inside an HTML comment) plus a short human summary."""
    found = problems(receipt)
    if found:
        raise ValueError("; ".join(found))
    encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True).replace("--", "-\\u002d")
    summary = {"transition": f"{receipt.get('from')} → {receipt.get('to')}",
               "rejection": f"{receipt.get('from')} → Rejected ({receipt.get('reason')}) → {receipt.get('return_to')}",
               "test": f"testes {receipt.get('result')} em {str(receipt.get('sha'))[:10]}",
               "review": f"revisão {receipt.get('verdict')} em {str(receipt.get('sha'))[:10]}",
               "decision": f"decisão `{receipt.get('label')}` por {receipt.get('approver')}",
               "qa": f"QA {receipt.get('verdict')} da candidata {receipt.get('candidate')}",
               "publication": f"publicação {receipt.get('version')} em {receipt.get('environment')}: "
                              f"{receipt.get('result')}",
               "claim": f"posse de {receipt.get('actor')} (geração {receipt.get('generation')}, até "
                        f"{receipt.get('expires')})",
               "release": f"posse de {receipt.get('actor')} liberada: {receipt.get('reason')}"}[receipt["kind"]]
    return f"{MARK}{encoded} -->\n**Big Bang** · {summary} · `{receipt['event_id']}`"


def parse(comments, trusted_logins):
    """Valid receipts of the trusted accounts, in comment order; malformed or foreign lines are ignored."""
    trusted = {login.casefold() for login in trusted_logins}
    result = []
    for comment in comments:
        if (comment.get("user") or {}).get("login", "").casefold() not in trusted:
            continue
        for match in LINE.finditer(comment.get("body") or ""):
            try:
                receipt = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not problems(receipt):
                result.append(receipt)
    return result


def find(receipts, event_id):
    """The receipt already written for this event (replay returns the previous result), or None."""
    return next((receipt for receipt in receipts if receipt.get("event_id") == event_id), None)


def reuse_problems(test_receipt, *, tree, policy, lockfiles):
    """Why a test receipt cannot be reused for this content (same tree, policy and lockfiles, green result)."""
    found = problems(test_receipt)
    if test_receipt.get("kind") != "test":
        found.append("o recibo não é de teste")
    if test_receipt.get("result") != "success":
        found.append("a execução registrada não foi verde")
    if test_receipt.get("tree") != tree:
        found.append("o conteúdo testado difere (árvore Git)")
    if test_receipt.get("policy") != policy:
        found.append("a política mudou desde a execução")
    if test_receipt.get("lockfiles") != lockfiles:
        found.append("dependências (lockfiles) mudaram desde a execução")
    return found
