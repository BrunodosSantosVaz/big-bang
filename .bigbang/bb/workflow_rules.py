"""Rules every GitHub Actions workflow must follow (spec 14.1 and SEG-18). Text-based, no YAML dependency."""
import re

PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"^\s*#\s*v\d+(\.\d+){0,2}\s*$")
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$", re.M)
RUNS_ON = re.compile(r"^\s*runs-on:\s*(.+?)\s*$", re.M)
TOP_PERMISSIONS = re.compile(r"^permissions:", re.M)
PR_HEAD = re.compile(r"github\.event\.pull_request\.head\.(sha|ref)|github\.head_ref")


def problems(name, text):
    """Return the list of rule violations of one workflow file (messages in Portuguese)."""
    result = []
    if not TOP_PERMISSIONS.search(text):
        result.append(f"{name}: falta `permissions:` no topo (permissão mínima declarada)")
    if re.search(r"^permissions:\s*write-all", text, re.M):
        result.append(f"{name}: `permissions: write-all` é proibido")
    for action, rest in USES.findall(text):
        action = action.strip("'\"")
        if action.startswith(("./", "docker://")):
            continue
        if not PINNED.match(action):
            result.append(f"{name}: action sem SHA completo: {action}")
        elif not VERSION_COMMENT.match(rest):
            result.append(f"{name}: action sem a versão em comentário: {action}")
    for runner in RUNS_ON.findall(text):
        if "latest" in runner:
            result.append(f"{name}: runner em versão móvel: {runner} (use, por exemplo, ubuntu-24.04)")
    if "pull_request_target" in text and PR_HEAD.search(text):
        result.append(f"{name}: pull_request_target com checkout do código do PR é proibido")
    return result
