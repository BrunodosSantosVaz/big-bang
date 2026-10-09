"""Pure rules of the pipeline (spec 6.5, 11.3, 11.5, 11.10, 15.5). The Bash scripts call these through
`bb esteira ...`, so every decision with a rule lives here, tested, and the scripts only orchestrate gh and git.
"""
import fnmatch
import re
import unicodedata

# --- epic issue form (spec 6.5): the "### <label>" headings GitHub renders for each field ----------------------------

FIELD_PROBLEM = "Problema ou oportunidade"
FIELD_GOAL = "Objetivo e resultado esperado"
FIELD_ARTIFACT = "Muda o artefato?"
FIELD_PROTOTYPE = "Precisa de protótipo?"
FIELD_TEST_REVIEW = "Quem revisa os testes de aceite?"
FIELD_PR_REVIEW = "Quem revisa os PRs?"
FIELD_DEPENDS = "Depende de outro épico ainda não publicado?"
FIELD_SCOPE = "Escopo"
FIELD_RULES = "Regras de negócio envolvidas"
FIELD_CRITERIA = "Critérios de aceite"
FIELD_STRIDE = "Análise de ameaças (STRIDE)"
FIELD_RISKS = "Riscos"
FIELD_TASKS = "Tarefas previstas"

ARTIFACT_NO = "Não: documentação, testes, esteira"
NO_RESPONSE = "_No response_"

# answer -> (label to add, labels to remove); a missing answer uses the default of the spec
DROPDOWNS = {
    FIELD_ARTIFACT: ({"Sim": (None, {"sem-release"}), ARTIFACT_NO: ("sem-release", set())}, "Sim"),
    FIELD_PROTOTYPE: ({"Sim": ("com-prototipo", {"sem-prototipo"}), "Não": ("sem-prototipo", {"com-prototipo"})},
                      "Sim"),
    FIELD_TEST_REVIEW: ({"IA": ("testes-revisao-ia", {"testes-revisao-humana"}),
                         "Eu": ("testes-revisao-humana", {"testes-revisao-ia"})}, "IA"),
    FIELD_PR_REVIEW: ({"IA": ("revisao-ia", {"revisao-humana"}), "Eu": ("revisao-humana", {"revisao-ia"})}, "IA"),
}

HEADING = re.compile(r"^###[ \t]+(.+?)[ \t]*$", re.M)
ISSUE_REF = re.compile(r"#(\d+)\b")
LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(?:\[[ xX]\]\s*)?(.+?)\s*$")
DEPENDS_ON = re.compile(r"\s*\(\s*depende de:\s*([\d,\s]+)\)\s*$", re.I)
CRITERION = re.compile(r"\bCA-(\d+)\b")


def sections(body):
    """Map each `### heading` of an issue body to its text (empty for GitHub's `_No response_`)."""
    body = (body or "").replace("\r\n", "\n")
    marks = list(HEADING.finditer(body))
    result = {}
    for current, following in zip(marks, marks[1:] + [None]):
        text = body[current.end():following.start() if following else len(body)].strip()
        result[current.group(1)] = "" if text == NO_RESPONSE else text
    return result


def form_label_changes(body, previous_body=None):
    """Labels to add and remove from the epic form answers.

    On an edit (previous_body given) only the questions whose answer changed are applied, so a label changed later
    by the AI or by the owner is not overwritten by an unrelated edit of the body.
    """
    now = sections(body)
    before = sections(previous_body) if previous_body is not None else None
    add, remove = set(), set()
    for field, (options, default) in DROPDOWNS.items():
        answer = now.get(field) or default
        if before is not None and (before.get(field) or default) == answer:
            continue
        if answer not in options:
            continue
        label, unwanted = options[answer]
        if label:
            add.add(label)
        remove |= unwanted
    depends_now = dependencies(body)
    if before is None or depends_now != dependencies(previous_body):
        (add if depends_now else remove).add("tem-dependencia")
    return add, remove - add


SEVERITIES = {"crítica": "severidade:critica", "alta": "severidade:alta", "média": "severidade:media",
              "baixa": "severidade:baixa"}


def severity_label(body):
    """Label of the "Severidade" answer of the bug form, or None."""
    return SEVERITIES.get(sections(body).get("Severidade", "").strip().lower())


def dependencies(body):
    return [int(n) for n in ISSUE_REF.findall(sections(body).get(FIELD_DEPENDS, ""))]


def planned_tasks(body):
    """Tasks of the epic: list of (title, [indexes of tasks it depends on]) from "Tarefas previstas"."""
    tasks = []
    for line in sections(body).get(FIELD_TASKS, "").splitlines():
        item = LIST_ITEM.match(line)
        if not item:
            continue
        title, deps = item.group(1), []
        depends = DEPENDS_ON.search(title)
        if depends:
            deps = [int(n) for n in re.findall(r"\d+", depends.group(1))]
            title = title[:depends.start()].strip()
        if title:
            tasks.append((title, deps))
    return tasks


def acceptance_criteria(body):
    """{n: text} of each CA-n in "Critérios de aceite"."""
    text = sections(body).get(FIELD_CRITERIA, "")
    marks = list(CRITERION.finditer(text))
    return {int(m.group(1)): text[m.start():(nxt.start() if nxt else len(text))].strip()
            for m, nxt in zip(marks, marks[1:] + [None])}


def readiness_problems(body, labels):
    """Definition of Ready (spec 11.3): the reasons why the epic cannot enter the sprint (empty = ready)."""
    labels = set(labels)
    parts = sections(body)
    problems = []
    for field in (FIELD_PROBLEM, FIELD_GOAL, FIELD_SCOPE, FIELD_RULES):
        if not parts.get(field):
            problems.append(f"falta \"{field}\"")
    criteria = acceptance_criteria(body)
    if not criteria:
        problems.append("falta critério de aceite no formato CA-n")
    for number, text in sorted(criteria.items()):
        lowered = text.lower()
        if not all(word in lowered for word in ("dado", "quando", "então")):
            problems.append(f"CA-{number} não está no formato Dado/Quando/Então")
    tasks = planned_tasks(body)
    if not tasks:
        problems.append("falta \"Tarefas previstas\" com pelo menos uma tarefa")
    for index, (title, deps) in enumerate(tasks, start=1):
        for dep in deps:
            if not 1 <= dep <= len(tasks) or dep == index:
                problems.append(f"tarefa {index} ({title}) depende de uma tarefa inexistente: {dep}")
    for field, (options, _) in DROPDOWNS.items():
        answer = parts.get(field)
        if answer and answer not in options:
            problems.append(f"resposta inválida em \"{field}\": {answer}")
    if {"revisao-humana", "seguranca"} & labels and not parts.get(FIELD_STRIDE):
        problems.append("épico sensível (revisao-humana ou seguranca) sem análise de ameaças STRIDE")
    if "refinamento-aprovado" not in labels:
        problems.append("falta a label refinamento-aprovado (decisão do dono)")
    if "com-prototipo" in labels and "prototipo-aprovado" not in labels:
        problems.append("épico com-prototipo sem a label prototipo-aprovado")
    return problems


# --- names: branches and PR titles (spec 3.2, 11.5) ------------------------------------------------------------------

SLUG_MAX = 40
CONVENTIONAL = re.compile(r"^(feat|fix|docs|test|refactor|build|ci|chore|perf|style|revert)(\(([\w./-]+)\))?(!)?: (\S.*)$")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
ISSUE_BRANCH = re.compile(r"^(feature|teste|docs|bugfix|hotfix|epico|fundacao)/(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*$")


def slug(text):
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:SLUG_MAX].strip("-")
    return value or "tarefa"


def branch_name(kind, number, title):
    return f"{kind}/{number}-{slug(title)}"


def branch_issue(branch):
    """(kind, issue number) of an issue branch, or (None, None)."""
    match = ISSUE_BRANCH.match(branch or "")
    return (match.group(1), int(match.group(2))) if match else (None, None)


def branch_problem(head, base):
    """Why a PR from `head` into `base` breaks the branch model (spec 11.5), or None when it is right."""
    kind, _ = branch_issue(head)
    if kind in ("feature", "teste", "docs"):
        expected = "o epico/<n>-<slug> do épico"
        ok = base.startswith("epico/")
    elif kind in ("bugfix", "hotfix"):
        expected, ok = "main", base == "main"
    elif kind == "epico":
        expected, ok = "release/x.y.z ou develop", base == "develop" or bool(re.match(r"^release/\d+\.\d+\.\d+$", base))
    elif kind == "fundacao":
        expected, ok = "develop", base == "develop"
    elif re.match(r"^framework/v\d+\.\d+\.\d+$", head):
        expected, ok = "develop", base == "develop"
    elif re.match(r"^release/\d+\.\d+\.\d+$", head):
        expected, ok = "main", base == "main"
    elif re.match(r"^sync/\d+-[a-z0-9-]+$", head):
        expected, ok = "o epico/* correspondente", base.startswith("epico/") and base[6:] == head[5:]
    elif head.startswith("dependabot/github_actions/"):
        expected, ok = "develop", base == "develop"
    elif head.startswith("dependabot/"):
        expected, ok = "main", base == "main"
    else:
        return (f"branch '{head}' fora do padrão: use feature|teste|docs|bugfix|hotfix|fundacao/<n>-<slug>, "
                "epico/<n>-<slug>, release/x.y.z, framework/vX.Y.Z ou sync/<n>-<slug>")
    return None if ok else f"'{head}' deve abrir PR para {expected}, não para '{base}'"


def title_problem(title):
    if CONVENTIONAL.match(title or ""):
        return None
    return ("título fora do Conventional Commits: use <tipo>(escopo opcional): descrição, com tipo feat, fix, docs, "
            "test, refactor, build, ci, chore, perf, style ou revert (ex.: feat(pedidos): bloqueia pedido sem estoque)")


def parse_title(title):
    match = CONVENTIONAL.match(title or "")
    if not match:
        return None
    return {"type": match.group(1), "scope": match.group(3) or "", "breaking": bool(match.group(4)),
            "description": match.group(5)}


# --- version and changelog (spec 11.10) ------------------------------------------------------------------------------

def next_version(current, titles, bodies=()):
    """SemVer bump from the PR titles of the release unit: breaking -> major (minor before 1.0), feat -> minor,
    anything else -> patch."""
    match = SEMVER.match(current or "0.0.0")
    if not match:
        raise ValueError(f"versão atual inválida: {current}")
    major, minor, patch = (int(part) for part in match.groups())
    parsed = [parse_title(title) for title in titles]
    breaking = any(p and p["breaking"] for p in parsed) or any("BREAKING CHANGE" in (b or "") for b in bodies)
    feature = any(p and p["type"] == "feat" for p in parsed)
    if breaking:
        return f"{major + 1}.0.0" if major >= 1 else f"0.{minor + 1}.0"
    if feature:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump_kind(current, chosen, titles, bodies=()):
    """Whether a version informed by hand agrees with the classification (to demand confirmar_versao)."""
    return chosen == next_version(current, titles, bodies)


CHANGELOG_SECTIONS = ("Adicionado", "Alterado", "Corrigido", "Removido", "Segurança")
UNRELEASED = "## [Não publicado]"
CHANGELOG_HEADER = """# Changelog

Todas as mudanças relevantes deste sistema, no formato
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), com versões [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]
"""


def changelog_entries(items):
    """items: (number, title, labels). Returns {section: [lines]} for the titles that change the artifact."""
    grouped = {name: [] for name in CHANGELOG_SECTIONS}
    for number, title, labels in items:
        parsed = parse_title(title)
        if not parsed:
            continue
        text = parsed["description"][:1].upper() + parsed["description"][1:]
        if parsed["breaking"]:
            text = f"**Quebra de compatibilidade:** {text}"
        line = f"- {text} (#{number})"
        if "seguranca" in labels:
            grouped["Segurança"].append(line)
        elif parsed["type"] == "feat":
            grouped["Adicionado"].append(line)
        elif parsed["type"] == "fix":
            grouped["Corrigido"].append(line)
        elif parsed["type"] in ("refactor", "perf") or parsed["breaking"]:
            grouped["Alterado"].append(line)
        elif parsed["type"] == "revert":
            grouped["Removido"].append(line)
    return grouped


def _unreleased_entries(text):
    """{section: [lines]} written by hand under [Não publicado] (the documentation task's draft)."""
    grouped, current = {name: [] for name in CHANGELOG_SECTIONS}, None
    for line in text.splitlines():
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1) if heading.group(1) in grouped else None
        elif current and line.strip():
            grouped[current].append(line.rstrip())
    return grouped


def changelog_with_release(changelog, version, date, items):
    """Insert the `## [version] - date` section (generated + the [Não publicado] draft) and empty the draft."""
    changelog = (changelog or CHANGELOG_HEADER).replace("\r\n", "\n")
    if f"## [{version}]" in changelog:
        return changelog  # idempotent
    if UNRELEASED not in changelog:
        changelog = changelog.rstrip("\n") + "\n\n" + UNRELEASED + "\n"
    start = changelog.index(UNRELEASED) + len(UNRELEASED)
    following = re.search(r"^## \[", changelog[start:], re.M)
    end = start + following.start() if following else len(changelog)
    generated = changelog_entries(items)
    draft = _unreleased_entries(changelog[start:end])
    lines = [f"## [{version}] - {date}", ""]
    for name in CHANGELOG_SECTIONS:
        entries = generated[name] + [line for line in draft[name] if line not in generated[name]]
        if entries:
            lines += [f"### {name}", "", *entries, ""]
    if len(lines) == 2:
        lines += ["- Manutenção sem mudança visível para quem usa.", ""]
    before, after = changelog[:start].rstrip("\n"), changelog[end:].lstrip("\n")
    result = before + "\n\n" + "\n".join(lines).rstrip("\n") + "\n"
    return result + ("\n" + after if after else "")


def changelog_has_version(changelog, version):
    return f"## [{version}]" in (changelog or "")


# --- paths: artifact and sensitive zones (spec 5.4, 11.8) -------------------------------------------------------------

ALWAYS_SENSITIVE = (".github/**", "tests/aceite/**", ".bigbang-docs.json", ".bigbang-producao.json", "STACK.md", "DESIGN.md", "PRODUTO.md", "bigbang.toml",
                    "flags.toml")
DEPENDENCY_FILES = ("package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
                    "pyproject.toml", "requirements*.txt", "poetry.lock", "uv.lock", "Pipfile", "Pipfile.lock",
                    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "pom.xml", "build.gradle", "build.gradle.kts",
                    "composer.json", "composer.lock", "*.csproj", "packages.lock.json", "Gemfile", "Gemfile.lock")


def _glob_regex(pattern):
    """`**` crosses folders, `*` and `?` do not; a pattern ending in `/` is a folder prefix."""
    if pattern.endswith("/"):
        pattern += "**"
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def matches(path, patterns):
    return any(_glob_regex(pattern).match(path) for pattern in patterns)


def artifact_paths(paths, artifact_patterns):
    return [path for path in paths if matches(path, artifact_patterns)]


def sensitive_paths(paths, zones, acceptance_allowed=False):
    """Paths that force human review. The epic's test PR may touch tests/aceite/ (its review follows the
    testes-revisao-* labels)."""
    result = []
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        if acceptance_allowed and path.startswith("tests/aceite/"):
            continue
        if matches(path, ALWAYS_SENSITIVE) or matches(path, zones) or any(
                fnmatch.fnmatchcase(name, pattern) for pattern in DEPENDENCY_FILES):
            result.append(path)
    return result


# --- version file of the stack (decided in F2) ------------------------------------------------------------------------

VERSION_LINE = re.compile(r"(?im)^(.*\b(?:version|versao|__version__)\b.*?)(\d+\.\d+\.\d+)")


def with_version(text, version):
    """Replace the first SemVer on a line that names the version (package.json, pyproject.toml, version.py…)."""
    if not SEMVER.match(version):
        raise ValueError(f"versão inválida: {version}")
    new, count = VERSION_LINE.subn(lambda m: m.group(1) + version, text, count=1)
    if count != 1:
        raise ValueError("nenhuma linha com version/versao e número SemVer no arquivo de versão")
    return new


# --- acceptance tests: releasing the pending marks of the PR's own task (spec 11.7) ---------------------------------

def _acceptance_changes(diff):
    """{file: (removed lines, added lines)} of the files under tests/aceite/ in a unified diff."""
    changes, current = {}, None
    for line in (diff or "").splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
            current = path if path.startswith("tests/aceite/") else None
            if current:
                changes.setdefault(current, ([], []))
        elif current and line.startswith("-") and not line.startswith("---"):
            changes[current][0].append(line[1:])
        elif current and line.startswith("+") and not line.startswith("+++"):
            changes[current][1].append(line[1:])
    return changes


def _released(line, marker, issue):
    """The line without the pending mark of `issue` (decorator removed, or test.failing -> test)."""
    without_reason = re.sub(rf"\s*(#|//)\s*pendente da tarefa #{issue}\b.*$", "", line)
    base = marker.rsplit(".", 1)[0] if "." in marker else ""
    return without_reason.replace(marker, base) if base else without_reason.replace(marker, "")


def only_own_marks_released(diff, issue, marker):
    """True when every change under tests/aceite/ only releases pending marks that cite `#issue`."""
    changes = _acceptance_changes(diff)
    if not changes:
        return False
    for removed, added in changes.values():
        for line in removed:
            if marker not in line or f"#{issue}" not in line:
                return False
        expected = [_released(line, marker, issue) for line in removed]
        for line in added:
            if line not in expected:
                return False
    return True


# --- compiled profile: build matrix and asset names (spec 14.3) ------------------------------------------------------

RUNNERS = {"windows-x64": "windows-2025", "windows-arm64": "windows-11-arm", "linux-x64": "ubuntu-24.04",
           "linux-arm64": "ubuntu-24.04-arm", "macos-x64": "macos-15-intel", "macos-arm64": "macos-15",
           "android": "ubuntu-24.04"}  # android: APK/AAB built on Linux (the runner has the Android SDK and a JDK)


def build_matrix(systems):
    """GitHub Actions matrix include list: one fixed-version runner per system."""
    return [{"sistema": system, "runner": RUNNERS[system]} for system in systems]


def candidate_asset_name(slug, version, rc, system, filename):
    """`<slug>-vX.Y.Z-rc.N-<sistema><ext>`: the promotion only drops `-rc.N`, so the bytes and the hash stay."""
    ext = ""
    for known in (".tar.gz", ".exe", ".msi", ".zip", ".dmg", ".pkg", ".AppImage", ".deb", ".rpm", ".tgz",
                  ".apk", ".aab"):
        if filename.endswith(known):
            ext = known
            break
    return f"{slug}-v{version}-rc.{rc}-{system}{ext}"


def promoted_name(candidate_name):
    """Production name of a candidate asset: the same name without `-rc.N`."""
    return re.sub(r"-rc\.\d+(?=-|\.|$)", "", candidate_name, count=1)


# --- security gates (SEG-17, SEG-IA-01) -----------------------------------------------------------------------------

HIGH_SEVERITY = 7.0  # CVSS: 7.0-8.9 high, 9.0+ critical


def osv_high_findings(report):
    """['package version: ids (CVSS n)'] of the OSV-Scanner JSON report entries rated high or critical."""
    findings = []
    for result in (report or {}).get("results", []):
        for package in result.get("packages", []):
            info = package.get("package", {})
            for group in package.get("groups", []):
                try:
                    score = float(group.get("max_severity") or 0)
                except ValueError:
                    score = 0.0
                if score >= HIGH_SEVERITY:
                    ids = ", ".join(group.get("ids", []))
                    findings.append(f"{info.get('name')} {info.get('version')}: {ids} (CVSS {score})")
    return findings


CREATE_TABLE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)", re.I)
ENABLE_RLS = re.compile(r"alter\s+table\s+(?:only\s+)?([\w.\"]+)\s+enable\s+row\s+level\s+security", re.I)


def tables_without_rls(sql_texts):
    """Tables created in the migrations that never get ROW LEVEL SECURITY enabled (SEG-IA-01)."""
    def name(raw):
        return raw.replace('"', "").split(".")[-1].lower()
    created, protected = [], set()
    for text in sql_texts:
        created += [name(m) for m in CREATE_TABLE.findall(text)]
        protected |= {name(m) for m in ENABLE_RLS.findall(text)}
    return sorted(set(created) - protected)
