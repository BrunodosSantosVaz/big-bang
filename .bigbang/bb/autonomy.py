"""The autonomous mode (ADR-0025): it acts only inside autonomy.toml, read from the checkout that runs bb (in the
CI, the target branch: a PR cannot widen its own contract). Without a valid contract nothing is delegated; the
bootstrap refuses an account that cannot enforce the controls the mode depends on."""
import os
import tomllib

from . import policy

KEY = "_autonomy"  # internal key of the loaded configuration mapping; never written to bigbang.toml
MISSING = "modo autonomous sem autonomy.toml: nada é delegado (tudo bloqueado)"
GATE_CHECK = "gate"


def attach(config, root):
    """A copy of the configuration carrying the contract of <root>/autonomy.toml (autonomous mode only)."""
    result = dict(config)
    if policy.mode(config) != "autonomous":
        return result
    path = os.path.join(root, "autonomy.toml")
    if not os.path.exists(path):
        result[KEY] = None
        return result
    try:
        with open(path, "rb") as handle:
            result[KEY] = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as error:
        result[KEY] = {"_invalid": str(error)}
    return result


def contract_of(config):
    return config.get(KEY) if policy.mode(config) == "autonomous" else None


def problems(config, today):
    """Why the contract cannot be used (empty = usable, or not in autonomous mode)."""
    if policy.mode(config) != "autonomous":
        return []
    contract = config.get(KEY)
    if not contract:
        return [MISSING]
    if "_invalid" in contract:
        return [f"autonomy.toml inválido: {contract['_invalid']}"]
    return policy.contract_problems(contract, today)


def usable(config, today):
    """The contract when it can be used now, else None (the gates then block in autonomous mode)."""
    return None if problems(config, today) else contract_of(config)


def publish_problems(config, target, now):
    """Autonomous publication only to a contract target, inside the publish window and with the publish gate."""
    if policy.mode(config) != "autonomous":
        return []
    found = problems(config, now.date())
    if found:
        return found
    contract = config[KEY]
    if target not in contract["targets"]:
        found.append(f"alvo {target} fora do contrato (targets: {', '.join(contract['targets'])})")
    if "publish" not in contract["gates"]:
        found.append("o contrato não delega o portão publish: a publicação é do dono")
    if not policy.in_window(contract["publish_window"], now):
        found.append(f"fora da janela de publicação {contract['publish_window']} (UTC) do contrato")
    return found


def _requires_gate(rules):
    for rule in rules or []:
        if rule.get("type") != "required_status_checks":
            continue
        checks = (rule.get("parameters") or {}).get("required_status_checks") or []
        if any(check.get("context") == GATE_CHECK for check in checks):
            return True
    return False


def bootstrap_problems(client):
    """What the account and repository lack for the autonomous mode: an enforced `gate` on main and develop and a
    production environment that only main can deploy to. Empty list = the controls are in place."""
    repo = client.repository_info()
    if repo is None:
        return ["repositório inacessível com o token atual"]
    found = []
    if repo.get("private") and (repo.get("owner") or {}).get("type") == "Organization":
        status, org = client.api("GET", f"orgs/{repo['owner']['login']}", None)
        plan = ((org or {}).get("plan") or {}).get("name") if status == 200 else None
        if plan in (None, "free"):
            found.append("repositório privado de organização sem plano pago confirmado: rulesets e ambientes "
                         "protegidos podem não ser aplicados")
    if repo.get("private") and (repo.get("owner") or {}).get("type") == "User":
        user = client.user() or {}
        plan = (user.get("plan") or {}).get("name")
        owner = (repo.get("owner") or {}).get("login", "")
        if plan == "free":
            found.append("repositório privado numa conta pessoal Free: rulesets e ambientes protegidos não são "
                         "aplicados; torne o repositório público ou use um plano pago")
        elif not plan or user.get("login", "").casefold() != owner.casefold():
            found.append("não foi possível confirmar o plano do dono do repositório privado (rode com o token "
                         "do dono): sem isso, rulesets e ambientes protegidos podem não ser aplicados")
    for branch in ("main", "develop"):
        rules = client.branch_rules(branch)
        if not _requires_gate(rules):
            found.append(f"a branch {branch} não exige o check {GATE_CHECK} (ruleset)")
        for ruleset_id in sorted({rule.get("ruleset_id") for rule in rules if rule.get("ruleset_id")}):
            ruleset = client.ruleset(ruleset_id) or {}
            if "bypass_actors" not in ruleset:
                found.append(f"não foi possível ver os bypass_actors do ruleset {ruleset_id} (rode com o token do "
                             "dono, que pode editar o ruleset)")
            elif ruleset.get("bypass_actors"):
                found.append(f"o ruleset {ruleset_id} da branch {branch} tem bypass_actors: quem está na lista "
                             "contorna o check gate")
    environment = client.environment("production")
    if not environment:
        found.append("o ambiente production não existe")
        return found
    deployment = environment.get("deployment_branch_policy")
    if not deployment:
        found.append("o ambiente production aceita qualquer branch: restrinja à main")
    elif deployment.get("custom_branch_policies"):
        names = sorted(f"{item.get('name')} ({item.get('type', 'branch')})" if item.get("type", "branch") != "branch"
                       else item.get("name") for item in client.environment_branch_policies("production"))
        if names != ["main"]:
            found.append(f"o ambiente production deve aceitar só a main (hoje: {', '.join(names) or 'nenhuma'})")
    else:
        found.append("o ambiente production aceita qualquer branch protegida (inclui a develop): restrinja à main")
    return found
