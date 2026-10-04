"""`bb checklist producao` (spec 8.2): the final production validation, required by "Publicar em produção".

Each of the 11 items must say how THIS project verifies it, in docs/operacao/checklist-producao.md (created from
.bigbang/modelos/checklist-producao.md in the Foundation): `cmd: <command>` (must succeed), `portao: <gate>` (an
automated gate of the pipeline that already proves it) or `nao-se-aplica: <reason>`. An item without a verification
fails. Two checks are built in and cannot be skipped: .env.example without values and documented in the README, and
no open critical or high security finding."""
import json
import os
import re
import subprocess

from . import github
from .errors import BbError
from .paths import read_text

CHECKLIST_FILE = os.path.join("docs", "operacao", "checklist-producao.md")
ITEMS = (
    "O backend sobe sem erro",
    "O front compila",
    "As migrações rodam do zero e a partir da versão anterior",
    "O ambiente sobe pelo método de deploy do alvo",
    "Nenhum segredo no pacote do front",
    "Rotas privadas exigem autenticação",
    "CORS de produção configurado por ambiente",
    "Testes de limite de requisições presentes e passando",
    "/api/health responde sem autenticação",
    "O README documenta as variáveis de ambiente sem valores",
    "A auditoria de segurança não tem achado crítico ou alto aberto",
)
GATES = ("candidata", "ci", "seguranca", "staging", "testes", "builtin")
VERIFICATION = re.compile(r"verificação:\s*`?\s*(cmd|portao|nao-se-aplica)\s*:\s*(.+?)`?\s*$", re.I)


def _item_lines(text):
    """{item: (kind, value)} for the items that have a verification."""
    found = {}
    for line in text.splitlines():
        for item in ITEMS:
            if item.lower() in line.lower():
                match = VERIFICATION.search(line)
                if match:
                    found[item] = (match.group(1).lower(), match.group(2).strip())
    return found


def _env_problems(root):
    example = os.path.join(root, ".env.example")
    if not os.path.exists(example):
        return []
    problems, keys = [], []
    for line in read_text(example).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        keys.append(key.strip())
        if value.strip().strip('"').strip("'"):
            problems.append(f".env.example: {key.strip()} tem valor (o modelo nunca leva valores, SEG-15)")
    readme = read_text(os.path.join(root, "README.md")) if os.path.exists(os.path.join(root, "README.md")) else ""
    for key in keys:
        if key not in readme:
            problems.append(f"README.md não documenta a variável de ambiente {key}")
    return problems


def _security_findings(repository):
    issues = json.loads(github.run("api", f"repos/{repository}/issues?labels=seguranca&state=open&per_page=100",
                                   "--jq", "[.[] | select(has(\"pull_request\") | not) | "
                                           "{number, labels: [.labels[].name]}]"))
    return [f"achado de segurança aberto: #{issue['number']}" for issue in issues
            if {"severidade:critica", "severidade:alta"} & set(issue["labels"])]


def run(root, repository=None, with_github=True):
    """(results [(item, status, detail)], problems [str])."""
    path = os.path.join(root, CHECKLIST_FILE)
    if not os.path.exists(path):
        return [], [f"{CHECKLIST_FILE} não existe: crie a partir de .bigbang/modelos/checklist-producao.md e diga "
                    "como o projeto verifica cada item"]
    defined = _item_lines(read_text(path))
    results, problems = [], []
    for item in ITEMS:
        if item not in defined:
            problems.append(f"item sem verificação: {item}")
            results.append((item, "faltando", ""))
            continue
        kind, value = defined[item]
        if kind == "cmd":
            completed = subprocess.run(value, shell=True, cwd=root, capture_output=True, text=True, check=False)
            ok = completed.returncode == 0
            results.append((item, "ok" if ok else "reprovado", value))
            if not ok:
                problems.append(f"{item}: `{value}` falhou ({completed.returncode})")
        elif kind == "portao":
            if value.lower() not in GATES:
                problems.append(f"{item}: portão desconhecido '{value}' (use {', '.join(GATES)})")
                results.append((item, "reprovado", value))
            else:
                results.append((item, "ok", f"portão {value}"))
        else:
            results.append((item, "não se aplica", value))
    builtin = _env_problems(root)
    if with_github:
        if not repository:
            raise BbError("informe o repositório para conferir os achados de segurança")
        builtin += _security_findings(repository)
    problems += builtin
    return results, problems
