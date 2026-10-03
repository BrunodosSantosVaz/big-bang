"""`bb verificar` (spec 5.1 and 15.5): framework integrity, generated files intact, workflow rules, marked blocks."""
import os

from . import checksums, generator, workflow_rules
from . import config as config_module
from .errors import BbError
from .paths import read_text

DEPENDENCY_MARKERS = ("<!-- bb:dependencias:inicio -->", "<!-- bb:dependencias:fim -->")
CHANGE_MESSAGES = {
    "criar": "arquivo gerado ausente (rode bb gerar)",
    "alterar": "arquivo gerado editado à mão ou desatualizado (personalize no bigbang.toml e rode bb gerar)",
    "remover": "arquivo gerado obsoleto (rode bb gerar para remover)",
}


def run(root):
    """Return the list of problems; empty means the project is consistent."""
    result = list(checksums.problems(root))
    try:
        config = config_module.load(root, required=False)
    except BbError as exc:
        return result + [exc.message]
    try:
        plan = generator.build_plan(root)
    except BbError as exc:
        return result + [exc.message]
    result += [f"{path}: {CHANGE_MESSAGES[kind]}" for kind, path in generator.changes(plan, root)]
    result += _stack_dependencies(root, config)
    result += _workflows(root)
    return result


def _stack_dependencies(root, config):
    path = os.path.join(root, generator.STACK_FILE)
    if config is None or not os.path.exists(path):
        return []
    text = read_text(path)
    return [f"STACK.md: o marcador {marker} precisa aparecer uma vez" for marker in DEPENDENCY_MARKERS
            if text.count(marker) != 1]


def _workflows(root):
    folder = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(folder):
        return []
    result = []
    for name in sorted(os.listdir(folder)):
        if name.endswith((".yml", ".yaml")):
            result += workflow_rules.problems(f".github/workflows/{name}", read_text(os.path.join(folder, name)))
    return result
