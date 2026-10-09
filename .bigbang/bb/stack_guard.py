"""Stack guard (spec 11.13, COD-13): every DIRECT RUNTIME dependency must be in the STACK.md table.
Development dependencies are free. An ecosystem the guard cannot read fails explicitly, never silently."""
import json
import os
import re
import tomllib
import xml.etree.ElementTree as ElementTree

from .paths import read_text, to_posix
from . import documentation

TABLE_START = "<!-- bb:dependencias:inicio -->"
TABLE_END = "<!-- bb:dependencias:fim -->"
SKIPPED_FOLDERS = {".git", "node_modules", ".venv", "venv", "vendor", ".bigbang", "dist", "build", "__pycache__",
                   "target", "bin", "obj"}
DEV_REQUIREMENTS = re.compile(r"(dev|test|lint|doc|build|ci)", re.I)
UNSUPPORTED = {"Gemfile": "rubygems", "mix.exs": "hex", "pubspec.yaml": "pub", "Package.swift": "swift",
               "deps.edn": "clojure", "build.sbt": "sbt", "stack.yaml": "haskell", "cpanfile": "cpan"}
ALIASES = {"npm": "npm", "node": "npm", "javascript": "npm", "typescript": "npm", "pypi": "pypi", "pip": "pypi",
           "python": "pypi", "go": "go", "golang": "go", "cargo": "cargo", "rust": "cargo", "crates": "cargo",
           "maven": "maven", "gradle": "maven", "java": "maven", "kotlin": "maven", "composer": "composer",
           "php": "composer", "nuget": "nuget", "dotnet": "nuget", ".net": "nuget"}
PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(ecosystem, name):
    name = name.strip().lower()
    if ecosystem == "pypi":
        name = re.sub(r"[-_.]+", "-", name)
    return name


def allowed(root):
    """{(ecosystem, name)} from the STACK.md table, or None when STACK.md (or its table) does not exist yet."""
    path = os.path.join(root, "STACK.md")
    if not documentation.is_public(root) and not os.path.exists(path):
        return None
    text = documentation.read(root, "STACK.md")
    if TABLE_START not in text or TABLE_END not in text:
        return None
    table = text.split(TABLE_START, 1)[1].split(TABLE_END, 1)[0]
    result = set()
    for line in table.splitlines():
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0] or cells[0] == "Pacote" or set(cells[0]) <= {"-", " "}:
            continue
        ecosystem = ALIASES.get(cells[1].lower(), cells[1].lower())
        result.add((ecosystem, normalize(ecosystem, cells[0])))
    return result


def _package_json(text):
    return [("npm", name) for name in json.loads(text).get("dependencies", {})]


def _pyproject(text):
    data = tomllib.loads(text)
    names = [PEP508_NAME.match(spec).group(1) for spec in data.get("project", {}).get("dependencies", [])
             if PEP508_NAME.match(spec)]
    poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    names += [name for name in poetry if name.lower() != "python"]
    return [("pypi", name) for name in names]


def _requirements(text):
    names = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = PEP508_NAME.match(line)
        if match:
            names.append(("pypi", match.group(1)))
    return names


def _go_mod(text):
    deps, block = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            block = True
            continue
        if block and stripped == ")":
            block = False
            continue
        single = stripped[len("require "):] if stripped.startswith("require ") else (stripped if block else "")
        if single and "// indirect" not in single:
            deps.append(("go", single.split()[0]))
    return deps


def _cargo(text):
    data = tomllib.loads(text)
    names = list(data.get("dependencies", {}))
    for target in data.get("target", {}).values():
        names += list(target.get("dependencies", {}))
    return [("cargo", name) for name in names]


def _composer(text):
    return [("composer", name) for name in json.loads(text).get("require", {})
            if name != "php" and not name.startswith("ext-")]


def _csproj(text):
    return [("nuget", name) for name in re.findall(r'<PackageReference\s+Include="([^"]+)"', text)]


def _pom(text):
    deps = []
    root = ElementTree.fromstring(text)
    namespace = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    for dep in root.iter(f"{namespace}dependency"):
        scope = (dep.findtext(f"{namespace}scope") or "compile").strip()
        if scope in ("test", "provided"):
            continue
        deps.append(("maven", f"{dep.findtext(f'{namespace}groupId')}:{dep.findtext(f'{namespace}artifactId')}"))
    return deps


GRADLE_RUNTIME = re.compile(r"^\s*(implementation|api|runtimeOnly|compileOnly)\b\s*(.*)$")
GRADLE_COORDINATE = re.compile(r"^\(?\s*(?:platform|enforcedPlatform)?\s*\(?\s*[\"']([^:\"'\s]+):([^:\"'\s]+)")
GRADLE_CATALOG = re.compile(r"^\(?\s*(?:platform|enforcedPlatform)?\s*\(?\s*libs\.([A-Za-z0-9_.]+)")
GRADLE_LOCAL = re.compile(r"^\(?\s*(project|files|fileTree)\s*\(")


def _alias(name):
    return re.sub(r"[-_.]+", ".", name.lower())


def gradle_catalog(text):
    """{accessor: [group:artifact]} of a gradle/libs.versions.toml (libraries and bundles)."""
    data = tomllib.loads(text)
    libraries = {}
    for name, value in data.get("libraries", {}).items():
        if isinstance(value, str):
            module = ":".join(value.split(":")[:2])
        elif "module" in value:
            module = value["module"]
        else:
            module = f"{value.get('group', '')}:{value.get('name', '')}"
        libraries[_alias(name)] = [module]
    for name, members in data.get("bundles", {}).items():
        libraries["bundles." + _alias(name)] = [m for member in members for m in libraries.get(_alias(member), [])]
    return libraries


def _gradle(text, catalog=None):
    """Runtime dependencies of build.gradle(.kts): coordinates, platform() BOMs and version-catalog accessors.
    A runtime line the guard cannot read is a problem, never skipped (local projects and files are not packages)."""
    deps, problems = [], []
    for number, line in enumerate(text.splitlines(), start=1):
        match = GRADLE_RUNTIME.match(line)
        if not match or not match.group(2) or match.group(2).startswith(("{", ".", "=")):
            continue  # not a dependency declaration (configurations { implementation { … } }, accessors)
        rest = match.group(2)
        coordinate, accessor = GRADLE_COORDINATE.match(rest), GRADLE_CATALOG.match(rest)
        if coordinate:
            deps.append(("maven", f"{coordinate.group(1)}:{coordinate.group(2)}"))
        elif accessor and catalog is not None and _alias(accessor.group(1)) in catalog:
            deps += [("maven", module) for module in catalog[_alias(accessor.group(1))]]
        elif GRADLE_LOCAL.match(rest):
            continue
        else:
            where = "sem gradle/libs.versions.toml" if accessor and catalog is None else "formato não reconhecido"
            problems.append(f"linha {number}: dependência de execução que a guarda não consegue ler ({where}): "
                            f"{line.strip()}")
    return deps, problems


def _find_catalog(path, root):
    folder = os.path.dirname(path)
    while True:
        candidate = os.path.join(folder, "gradle", "libs.versions.toml")
        if os.path.exists(candidate):
            return candidate
        if os.path.abspath(folder) == os.path.abspath(root) or os.path.dirname(folder) == folder:
            return None
        folder = os.path.dirname(folder)


PARSERS = {"package.json": _package_json, "pyproject.toml": _pyproject, "go.mod": _go_mod, "Cargo.toml": _cargo,
           "composer.json": _composer, "pom.xml": _pom}
GRADLE_FILES = ("build.gradle", "build.gradle.kts")


def dependency_files(root):
    for current, folders, names in os.walk(root):
        folders[:] = sorted(f for f in folders if f not in SKIPPED_FOLDERS)
        for name in sorted(names):
            yield os.path.join(current, name), name


def direct_runtime_dependencies(root):
    """([(ecosystem, name, file)], [problems of unreadable or unsupported files])."""
    deps, problems = [], []
    for path, name in dependency_files(root):
        relative = to_posix(os.path.relpath(path, root))
        parser = PARSERS.get(name)
        if parser is None and name.endswith(".csproj"):
            parser = _csproj
        if parser is None and re.match(r"^requirements.*\.txt$", name) and not DEV_REQUIREMENTS.search(name[12:]):
            parser = _requirements
        if name in UNSUPPORTED or name.endswith(".gemspec"):
            problems.append(f"{relative}: ecossistema {UNSUPPORTED.get(name, 'rubygems')} não suportado pela guarda "
                            "da stack; peça o suporte numa issue do Big Bang")
            continue
        if name in GRADLE_FILES:
            try:
                catalog_path = _find_catalog(path, root)
                catalog = gradle_catalog(read_text(catalog_path)) if catalog_path else None
                found, unreadable = _gradle(read_text(path), catalog)
            except (ValueError, tomllib.TOMLDecodeError) as exc:
                problems.append(f"{relative}: não consegui ler o catálogo de versões do Gradle ({exc})")
                continue
            deps += [(ecosystem, dep, relative) for ecosystem, dep in found]
            problems += [f"{relative}: {problem}" for problem in unreadable]
            continue
        if parser is None:
            continue
        try:
            deps += [(ecosystem, dep, relative) for ecosystem, dep in parser(read_text(path))]
        except (ValueError, ElementTree.ParseError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"{relative}: não consegui ler as dependências ({exc})")
    return deps, problems


def problems(root):
    approved = allowed(root)
    deps, result = direct_runtime_dependencies(root)
    if approved is None:
        if deps:
            result.append("há dependências de execução, mas o STACK.md (com a tabela de dependências) ainda não "
                          "existe: a stack é escolhida na Fundação F2")
        return result
    for ecosystem, name, path in deps:
        if (ecosystem, normalize(ecosystem, name)) not in approved:
            result.append(f"{path}: {name} ({ecosystem}) não está na tabela de dependências do STACK.md; "
                          "use bb-nova-tecnologia (ADR + linha nova no mesmo PR, com revisão do dono)")
    return result
