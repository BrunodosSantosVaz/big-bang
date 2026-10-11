"""The framework's own grouping pipeline. Dormant in templates; never a Foundation marker."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

from . import github
from .errors import BbError, EXIT_INVALID_CONFIG, EXIT_INVALID_STATE
from .paths import framework_version, read_text, write_text

CONFIG = '.bigbang-framework.toml'
ORIGIN = 'BrunodosSantosVaz/big-bang'


def repository(root):
    """Use the runner identity first; otherwise the actual origin, never the inherited manifest."""
    if os.environ.get('GITHUB_REPOSITORY'):
        return os.environ['GITHUB_REPOSITORY']
    result = subprocess.run(['git', '-C', root, 'config', '--get', 'remote.origin.url'],
                            capture_output=True, text=True, check=False)
    match = re.fullmatch(r'(?:https://github.com/|git@github.com:)([^/]+/[^/]+?)(?:\.git)?/?',
                         result.stdout.strip())
    return match[1] if match else None


def load(root, *, required=False, bootstrap=False):
    from . import config
    path = os.path.join(root, CONFIG)
    if bootstrap and not os.path.isfile(path) and repository(root) == ORIGIN:
        # The trusted base must validate the activation PR before the exclusive root file exists.
        # Optional template reads and explicit generation never use this bootstrap fixture.
        path = os.path.join(root, '.bigbang/pipeline/framework/config.toml')
    if not os.path.isfile(path):
        if required:
            raise BbError(f'falta {CONFIG}', EXIT_INVALID_CONFIG)
        return None
    actual = repository(root)
    if actual != ORIGIN:
        if required:
            raise BbError(f'{CONFIG}: permitido somente em {ORIGIN}; rode bb init no sistema novo',
                          EXIT_INVALID_CONFIG)
        return None  # A template without a remote is still unfounded.
    raw = config.parse(read_text(path), CONFIG)
    errors = config.validate(raw, framework_version(root))
    if raw.get('project', {}).get('repository') != ORIGIN or raw.get('bigbang', {}).get('origin') != ORIGIN:
        errors.append('project.repository e bigbang.origin devem ser a origem do framework')
    if raw.get('delivery', {}).get('profile') != 'compiled' or raw.get('compiled', {}).get('systems') != ['universal']:
        errors.append('o framework exige compiled com systems = ["universal"]')
    if raw.get('workflow', {}).get('model') != 'grouping':
        errors.append('o framework exige workflow.model = "grouping"')
    if errors:
        raise BbError(f'{CONFIG} inválido:\n' + '\n'.join(errors), EXIT_INVALID_CONFIG)
    result = config.views(raw)
    result['_framework'] = True
    return result


def problems(root):
    if not os.path.isfile(os.path.join(root, CONFIG)):
        return []
    actual = repository(root)
    from .paths import config_path
    # A plain template without a repository identity is allowed to remain dormant before init.
    if (actual and actual != ORIGIN) or os.path.exists(config_path(root)):
        return [f'{CONFIG}: arquivo exclusivo de {ORIGIN}; remova-o com bb init']
    try:
        if actual == ORIGIN:
            load(root, required=True)
    except BbError as error:
        return [error.message]
    return []


def prepare(root, version):
    """After write-version: regenerate the version, client snapshots, own workflows and integrity manifest."""
    from . import checksums, generator, init
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise BbError('versão inválida: use x.y.z', EXIT_INVALID_STATE)
    load(root, required=True)
    import hashlib
    import json
    manifest = os.path.join(root, ".bigbang-docs.json")
    data = None
    if os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as handle:
            data = json.load(handle)
        for feature in data["funcionalidades"]:
            for source in feature["fontes"]:
                with open(os.path.join(root, source), "rb") as handle:
                    digest = "sha256:" + hashlib.sha256(handle.read()).hexdigest()
                if feature["hashes"].get(source) != digest:
                    raise BbError("documentação desatualizada antes do corte: " + source, EXIT_INVALID_STATE)
    write_text(os.path.join(root, '.bigbang/VERSION'), version + '\n')
    path = os.path.join(root, CONFIG)
    write_text(path, init.set_value(read_text(path), 'bigbang', 'version', version))
    example = os.path.join(root, '.bigbang/modelos/bigbang.toml.exemplo')
    write_text(example, init.set_value(read_text(example), 'bigbang', 'versao', version))
    fixture = os.path.join(root, '.bigbang/pipeline/framework/config.toml')
    if os.path.isfile(fixture):
        write_text(fixture, init.set_value(read_text(fixture), 'bigbang', 'version', version))
    # Launch the script from this checkout: its helpers must never copy the main checkout or its worktrees.
    subprocess.run([sys.executable, os.path.join(root, '.bigbang/tests/atualizar_esperado.py')],
                   cwd=root, check=True)
    generator.apply(generator.build_plan(root, framework=True), root)
    if data is not None:
        for feature in data["funcionalidades"]:
            for source in feature["fontes"]:
                with open(os.path.join(root, source), "rb") as handle:
                    feature["hashes"][source] = "sha256:" + hashlib.sha256(handle.read()).hexdigest()
        write_text(manifest, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    checksums.write(root)


def candidate(root, output):
    """The updater's reproducible tarball and its .sha256 are the candidate assets (no rc in filenames)."""
    from . import package
    load(root, required=True)
    return package.build(root, output)


def promote(root, rc_tag, tag, target_sha):
    """Promote verified candidate bytes without rebuilding or renaming updater assets."""
    from . import package
    load(root, required=True)
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag) or not re.fullmatch(re.escape(tag) + r'-rc\.[1-9]\d*', rc_tag):
        raise BbError('tags de candidata e publicação incompatíveis', EXIT_INVALID_STATE)
    if not re.fullmatch(r'[a-f0-9]{40}', target_sha):
        raise BbError('SHA de publicação inválido', EXIT_INVALID_STATE)
    try:
        github.run('release', 'view', tag, '--repo', ORIGIN)
        return
    except BbError as error:
        if 'not found' not in error.message.lower() and '404' not in error.message:
            raise
    with tempfile.TemporaryDirectory(prefix='bb-framework-promote-') as folder:
        github.run('release', 'download', rc_tag, '--repo', ORIGIN, '--dir', folder)
        name = package.package_name(tag[1:])
        archive = os.path.join(folder, name)
        checksum = archive + '.sha256'
        if not os.path.isfile(archive) or not os.path.isfile(checksum):
            raise BbError('candidata sem pacote ou .sha256 do atualizador', EXIT_INVALID_STATE)
        expected = read_text(checksum).strip().split()
        with open(archive, 'rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if expected != [digest, name]:
            raise BbError('SHA-256 da candidata não confere; nada foi publicado', EXIT_INVALID_STATE)
        notes = os.path.join(folder, 'notes.md')
        write_text(notes, f'Os mesmos bytes de `{rc_tag}`. SHA-256: `{digest}`.\n\n' +
                   package.release_notes(root, tag[1:]))
        assets = [archive, checksum]
        sbom = os.path.join(folder, 'sbom-cyclonedx.json')
        if os.path.isfile(sbom):
            assets.append(sbom)
        github.run('release', 'create', tag, *assets, '--repo', ORIGIN, '--target', target_sha,
                   '--latest', '--title', f'Big Bang {tag}', '--notes-file', notes)


def register(commands):
    parent = commands.add_parser('framework', help='manutenção da esteira própria (somente na origem)')
    sub = parent.add_subparsers(dest='framework_command')
    prepare_parser = sub.add_parser('prepare')
    prepare_parser.add_argument('version')
    prepare_parser.set_defaults(handler=_prepare)
    candidate_parser = sub.add_parser('candidate')
    candidate_parser.add_argument('--output', required=True)
    candidate_parser.set_defaults(handler=_candidate)


def _prepare(args):
    prepare(args.raiz, args.version)
    return 0


def _candidate(args):
    archive, digest = candidate(args.raiz, args.output)
    print(f'{archive}: {digest}')
    return 0
