"""Read-only ownership and flag reports; stale labels are written only by the dedicated automation."""
import datetime
import os
import tomllib

from . import ownership
from .errors import EXIT_INVALID_STATE, BbError


def possessions(config, now=None):
    repo, owner = config["projeto"]["repositorio"], config["projeto"]["dono"]
    result = []
    for issue in ownership.listing(f"repos/{repo}/issues?state=open"):
        if "pull_request" in issue:
            continue
        claims = ownership.active_claims(repo, issue["number"], owner) if issue.get("comments") else []
        marks = sorted(x for x in ownership.labels(issue) if x.startswith("ia:"))
        if claims or marks:
            result.append({"issue": issue["number"], "title": issue["title"], "labels": marks,
                           "claims": claims, "stale": ownership.stale(config, issue["number"], claims, now)})
    return result


def mark_stale(config, simulate=True):
    repo = config["projeto"]["repositorio"]
    for entry in possessions(config):
        if entry["stale"]:
            print(f"#{entry['issue']}: posse parada" + (" (simulação)" if simulate else ""))
        if not simulate:
            # Re-read: a push or release may have arrived while collecting the report.
            claims = ownership.active_claims(repo, entry["issue"], config["projeto"]["dono"])
            if ownership.stale(config, entry["issue"], claims):
                ownership._add_label(repo, entry["issue"], "parada")
            # Reconcile after the write: a concurrent push may have renewed or released the session.
            current = ownership.active_claims(repo, entry["issue"], config["projeto"]["dono"])
            if not ownership.stale(config, entry["issue"], current):
                if "parada" in ownership.labels(ownership.issue_data(repo, entry["issue"])):
                    ownership._remove_label(repo, entry["issue"], "parada")


def _date(value, field, name):
    if type(value) is not datetime.date:
        raise BbError(f"flag {name}: {field} precisa de uma data TOML (AAAA-MM-DD)", EXIT_INVALID_STATE)
    return value


def flags(root, config, today=None):
    path = os.path.join(root, "flags.toml")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BbError(f"flags.toml inválido: {exc}", EXIT_INVALID_STATE) from exc
    today = today or datetime.datetime.now(ownership.UTC).date()
    entries = data.get("flag", [])
    if not isinstance(entries, list):
        raise BbError("flags.toml: use [[flag]]", EXIT_INVALID_STATE)
    result, names = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BbError("flags.toml: cada flag precisa ser uma tabela [[flag]]", EXIT_INVALID_STATE)
        name = entry.get("nome")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise BbError("flags.toml: nome ausente ou duplicado", EXIT_INVALID_STATE)
        names.add(name)
        for field in ("dono", "motivo", "epico"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise BbError(f"flag {name}: falta {field}", EXIT_INVALID_STATE)
        created = _date(entry.get("criada_em"), "criada_em", name)
        expires = _date(entry.get("expira_em"), "expira_em", name)
        state = entry.get("estado", {})
        if expires < created or created > today or not isinstance(state, dict) or any(
                type(state.get(key)) is not bool for key in ("staging", "producao")):
            raise BbError(f"flag {name}: datas ou estado inválidos", EXIT_INVALID_STATE)
        old = state["producao"] and (today - created).days > config["flags"]["validade_maxima_dias"]
        if expires < today or old:
            result.append({"name": name, "owner": entry["dono"], "epic": entry["epico"],
                           "expired": expires < today, "old": old, "created": created})
    return result


def report(root, config):
    entries = possessions(config)
    print("## Posses das IAs\n")
    if not entries:
        print("Nenhuma posse aberta.\n")
    for entry in entries:
        names = ", ".join(c["name"] for c in entry["claims"]) or ", ".join(entry["labels"])
        state = "PARADA" if entry["stale"] else "ativa"
        if not entry["claims"]:
            state = "label sem comentário de sessão; verificar com o dono"
        print(f"- #{entry['issue']} {entry['title']}: {names} — {state}")
    print("\n## Flags vencidas ou antigas em produção\n")
    alerts = flags(root, config)
    if not alerts:
        print("Nenhuma.\n")
    for alert in alerts:
        reason = "validade vencida" if alert["expired"] else f"ligada em produção e criada em {alert['created']}"
        print(f"- {alert['name']} ({alert['epic']}, dono: {alert['owner']}): {reason}; abrir tarefa de limpeza.")
    print("\n## Achados de segurança abertos\n")
    issues = ownership.listing(f"repos/{config['projeto']['repositorio']}/issues?state=open&labels=seguranca")
    findings = [issue for issue in issues if "pull_request" not in issue]
    if not findings:
        print("Nenhum.\n")
    for issue in findings:
        print(f"- #{issue['number']} {issue['title']} ({', '.join(sorted(ownership.labels(issue)))})")
