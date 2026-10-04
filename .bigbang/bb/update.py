"""`bb atualizar [versão]` (spec 5.7, ADR-0014): replace only the framework layer, on a framework/vX.Y.Z branch.

1. Read bigbang.versao and bigbang.origem.
2. Download bigbang-vX.Y.Z.tar.gz and .sha256 from the origin's Release; refuse on hash or attestation mismatch.
3. Show MIGRACAO.md between both versions; manual steps need the owner's confirmation (--confirmo-migracao).
4. Branch framework/vX.Y.Z from develop, swap .bigbang/, set bigbang.versao, run the NEW bb gerar and bb verificar.
5. Push and open the PR to develop with revisao-humana. The project layer is never touched.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

from . import checksums, github, package
from . import config as config_module
from .errors import EXIT_EXTERNAL_COMMAND, EXIT_INVALID_STATE, EXIT_USAGE, EXIT_VERIFICATION_FAILED, BbError
from .init import set_value
from .paths import FRAMEWORK_DIR, config_path, framework_dir, read_text, write_text

PR_LABEL = "revisao-humana"
PR_LABEL_COLOR, PR_LABEL_DESCRIPTION = "FBCA04", "PRs revisados pelo dono"  # as in .bigbang/scripts/criar-labels.sh


def _git(root, *args, check=True):
    result = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=False)
    if check and result.returncode:
        raise BbError(f"git {' '.join(args[:2])} falhou: {result.stderr.strip()}", EXIT_EXTERNAL_COMMAND)
    return result


def _bb(root, *args):
    """Run the bb of the (new) framework in the project: the running process still has the old code loaded."""
    command = [sys.executable, os.path.join(framework_dir(root), "bin", "bb.py"), "--raiz", root, *args]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def latest_version(origin):
    tag = json.loads(github.run("release", "view", "--repo", origin, "--json", "tagName"))["tagName"]
    return tag.lstrip("v")


def download(origin, version, folder, attestation=True):
    """Return the verified tarball path: SHA-256 from the Release's .sha256 and, by default, the build attestation."""
    name = package.package_name(version)
    github.run("release", "download", f"v{version}", "--repo", origin, "--dir", folder,
               "--pattern", name, "--pattern", name + ".sha256")
    tarball, sums = os.path.join(folder, name), os.path.join(folder, name + ".sha256")
    if not (os.path.exists(tarball) and os.path.exists(sums)):
        raise BbError(f"a Release v{version} de {origin} não tem {name} e {name}.sha256", EXIT_INVALID_STATE)
    expected = read_text(sums).split()[0].lower()
    with open(tarball, "rb") as handle:
        actual = hashlib.sha256(handle.read()).hexdigest()
    if actual != expected:
        raise BbError(f"SHA-256 de {name} não confere ({actual} ≠ {expected}): pacote recusado",
                      EXIT_VERIFICATION_FAILED)
    if attestation:
        try:
            github.run("attestation", "verify", tarball, "--repo", origin)
        except BbError as exc:
            raise BbError(f"a atestação de origem de {name} não confere com {origin}: pacote recusado\n{exc.message}",
                          EXIT_VERIFICATION_FAILED) from exc
    return tarball


def extract(tarball, folder, version):
    """Unpack into folder/.bigbang and check it is whole: CHECKSUMS and VERSION of the target version."""
    with tarfile.open(tarball, "r:gz") as tar:
        package.tarball_members_ok(tar)
        if hasattr(tarfile, "data_filter"):
            tar.extractall(folder, filter="data")
        else:  # Python 3.11 before 3.11.4; the entries were already checked above
            tar.extractall(folder)
    problems = checksums.problems(folder)
    if problems:
        raise BbError("o pacote não confere com o próprio CHECKSUMS: recusado\n" +
                      "\n".join(f"  - {p}" for p in problems), EXIT_VERIFICATION_FAILED)
    found = read_text(os.path.join(folder, FRAMEWORK_DIR, "VERSION")).strip()
    if found != version:
        raise BbError(f"o pacote diz ser a versão {found}, não {version}: recusado", EXIT_VERIFICATION_FAILED)
    return os.path.join(folder, FRAMEWORK_DIR)


def migration(new_framework, current, target):
    path = os.path.join(new_framework, "MIGRACAO.md")
    sections = package.migration_between(read_text(path), current, target) if os.path.exists(path) else []
    manual = [(s.splitlines()[0].lstrip("# "), package.manual_steps(s)) for s in sections]
    return sections, [(title, steps) for title, steps in manual if steps]


def swap(root, new_framework):
    """Replace .bigbang/ entirely, keeping only what bb init moved in (the framework README and LICENSE)."""
    current = framework_dir(root)
    kept = {}
    for name in checksums.ADDED_BY_INIT:
        path = os.path.join(current, name)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                kept[name] = handle.read()
    shutil.rmtree(current)
    shutil.copytree(new_framework, current)
    for name, data in kept.items():
        if not os.path.exists(os.path.join(current, name)):
            with open(os.path.join(current, name), "wb") as handle:
                handle.write(data)


def ensure_label():
    """The PR needs revisao-humana, which only exists after Foundation F4: create it when missing, before any push."""
    try:
        github.run("label", "create", PR_LABEL, "--color", PR_LABEL_COLOR, "--description", PR_LABEL_DESCRIPTION)
    except BbError as exc:
        if "already exists" not in exc.message:
            raise


def _pr_body(current, target, sections, manual, generated):
    lines = ["## O que muda", "", f"Atualiza o Big Bang de v{current} para v{target} (`bb atualizar`).",
             "Só a camada do framework (`.bigbang/`) e a camada gerada mudam; a camada do projeto não é tocada.", "",
             "## Migração (MIGRACAO.md)", ""]
    lines += [s + "\n" for s in sections] or ["Sem notas de migração entre as versões.", ""]
    if manual:
        lines += ["## Passos manuais (confirmados pelo dono antes da atualização)", ""]
        lines += [f"- [ ] {title}: {steps}" for title, steps in manual] + [""]
    lines += ["## Camada gerada (bb gerar)", "", "```", generated or "nada a mudar", "```", "",
              "## Verificação", "", "`bb verificar`: tudo certo.", "",
              "Revisão humana: o PR toca `.github/` e o framework. Revise o diff antes de mesclar."]
    return "\n".join(lines)


def update(root, target=None, simulate=False, confirmed=False, attestation=True):
    config = config_module.load(root)
    current, origin = config["bigbang"]["versao"], config["bigbang"]["origem"]
    target = (target or latest_version(origin)).lstrip("v")
    package._key(target)
    if package._key(target) <= package._key(current):
        print(f"O Big Bang já está na v{current}; nada a atualizar para v{target}.")
        return None
    branch = f"framework/v{target}"
    print(f"Atualizar o Big Bang: v{current} → v{target} (origem {origin}).")
    if not simulate:
        dirty = _git(root, "status", "--porcelain").stdout.strip()
        if dirty:
            raise BbError("há mudanças não commitadas; guarde-as antes de atualizar o framework", EXIT_INVALID_STATE)
        if _git(root, "ls-remote", "--exit-code", "--heads", "origin", branch, check=False).returncode == 0:
            raise BbError(f"a branch {branch} já existe no GitHub (atualização em andamento?)", EXIT_INVALID_STATE)
    work = tempfile.mkdtemp(prefix="bb-atualizar-")
    try:
        tarball = download(origin, target, work, attestation)
        print(f"Pacote conferido: {os.path.basename(tarball)} (SHA-256" + (" e atestação)." if attestation else ")."))
        new_framework = extract(tarball, os.path.join(work, "pacote"), target)
        sections, manual = migration(new_framework, current, target)
        for section in sections:
            print("\n" + section)
        sys.stdout.flush()  # the sections above come before the error, also when piped
        if manual and not confirmed:
            raise BbError("a migração tem passos manuais (acima). Mostre-os ao dono e, com a confirmação dele, rode "
                          "de novo com --confirmo-migracao", EXIT_INVALID_STATE)
        if simulate:
            print(f"\nSimulação: criaria {branch} da develop, trocaria .bigbang/, rodaria bb gerar e bb verificar e "
                  f"abriria o PR para a develop com {PR_LABEL}. Nada foi gravado.")
            return None
        _git(root, "fetch", "-q", "origin", "develop")
        _git(root, "switch", "-q", "-c", branch, "origin/develop")
        swap(root, new_framework)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    write_text(config_path(root), set_value(read_text(config_path(root)), "bigbang", "versao", target))
    code, generated = _bb(root, "gerar")
    if code:
        raise BbError(f"bb gerar da v{target} falhou na branch {branch}:\n{generated}", EXIT_INVALID_STATE)
    code, verified = _bb(root, "verificar")
    if code:
        raise BbError(f"bb verificar falhou na branch local {branch} (nada foi enviado; revise e corrija, ou volte "
                      f"com git switch develop e apague a branch):\n{verified}",
                      EXIT_VERIFICATION_FAILED)
    ensure_label()
    _git(root, "add", "-A")  # the tree was clean: everything here came from the swap, bigbang.versao and bb gerar
    _git(root, "commit", "-q", "-m", f"chore(framework): update Big Bang to v{target}\n\n"
         f"bb atualizar: .bigbang/ replaced by the verified v{target} package, bigbang.versao updated and the "
         f"generated layer regenerated.")
    _git(root, "push", "-q", "-u", "origin", branch)
    url = github.run("pr", "create", "--base", "develop", "--head", branch, "--label", PR_LABEL,
                     "--title", f"chore(framework): atualizar o Big Bang para v{target}",
                     "--body", _pr_body(current, target, sections, manual, generated))
    print(f"\nPR aberto: {url}")
    return url


def check_args(target):
    if target and not package.SEMVER.match(target.lstrip("v")):
        raise BbError(f"versão inválida: {target} (use X.Y.Z)", EXIT_USAGE)
