"""Traceability between business rules and acceptance tests (spec 9.2, DOC-02, DOC-03)."""
import os
import re

from .paths import read_text, to_posix
from . import documentation

RULES_DIR = os.path.join("docs", "negocio", "regras")
ACCEPTANCE_DIR = os.path.join("tests", "aceite")
RULE_FILE = re.compile(r"^RN-(\d{4})-[\w-]+\.md$")
HEADER = re.compile(r"^(\w+):\s*(.*?)\s*(?:#.*)?$")
# RN-0042, RN0042 or test_rn0042_… (a letter right before "rn" would be part of another word)
CITATION = re.compile(r"(?<![a-zA-Z])rn-?(\d{4})(?!\d)", re.I)


def rules(root):
    """{"RN-0042": "vigente" | "substituida" | …} from the key: value header of each rule file."""
    folder = os.path.join(root, RULES_DIR)
    result = {}
    for logical in documentation.logical_files(root, to_posix(RULES_DIR) + "/"):
        name = os.path.basename(logical)
        match = RULE_FILE.match(name)
        if not match:
            continue
        header = {}
        for line in documentation.read(root, logical).splitlines():
            parsed = HEADER.match(line)
            if not parsed:
                break
            header[parsed.group(1)] = parsed.group(2)
        result[f"RN-{match.group(1)}"] = header.get("situacao", "vigente")
    return result


def acceptance_tests(root, test_pattern):
    """[("path:line", line)] of every test declaration (bigbang.toml testes.padrao_teste) in tests/aceite/."""
    pattern = re.compile(test_pattern)
    found = []
    folder = os.path.join(root, ACCEPTANCE_DIR)
    for current, folders, names in os.walk(folder):
        folders[:] = sorted(f for f in folders if f != "__pycache__")
        for name in sorted(names):
            path = os.path.join(current, name)
            try:
                lines = read_text(path).splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, start=1):
                if pattern.search(line):
                    found.append((f"{to_posix(os.path.relpath(path, root))}:{number}", line))
    return found


def problems(root, test_pattern, changed_paths=()):
    """RN vigente without a test, test without an existing RN, RN file deleted in the change."""
    existing = rules(root)
    result = []
    cited = set()
    for where, line in acceptance_tests(root, test_pattern):
        ids = {f"RN-{number}" for number in CITATION.findall(line)}
        if not ids:
            result.append(f"{where}: teste de aceite sem o ID de uma regra de negócio (RN-NNNN) no nome")
        for rule_id in sorted(ids - set(existing)):
            result.append(f"{where}: cita {rule_id}, que não existe em docs/negocio/regras/")
        cited |= ids
    for rule_id, situation in sorted(existing.items()):
        if situation == "vigente" and rule_id not in cited:
            result.append(f"{rule_id} está vigente e nenhum teste de aceite a cita")
    for path in changed_paths:
        if re.match(r"^docs/negocio/regras/RN-\d{4}-", path) and not os.path.exists(os.path.join(root, path)) and \
                not (documentation.is_public(root) and path in documentation.load(root)["paginas"]):
            result.append(f"{path}: regra de negócio apagada (RN nunca é apagada: marque como substituida)")
    return result
