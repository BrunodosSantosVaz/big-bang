"""Conservative test execution policy. Flash changes scheduling, never test authorship or security gates."""
import fnmatch
import json
import os
import re
import subprocess
import tempfile

from . import config as config_module
from .errors import EXIT_EXTERNAL_COMMAND, EXIT_USAGE, BbError

STRUCTURAL = ('.bigbang/**', '.github/**', '.bigbang-docs.json', '.bigbang-producao.json', 'bigbang.toml', 'STACK.md', 'PRODUTO.md', 'DESIGN.md',
              'flags.toml', '*lock*', 'package.json', 'pyproject.toml', 'requirements*.txt', 'go.mod', 'go.sum',
              'Cargo.toml', '*.csproj', '*.sln', 'pom.xml', '*gradle*', '*Dockerfile*',
              'Gemfile', 'Pipfile', 'composer.json', '.python-version', '.node-version',
              '.dependency-cruiser*', '.eslint*',
              'docker-compose*', 'compose.y*ml', 'deploy/**', 'packaging/**', 'migrations/**',
              '*config.*', 'config/**', 'infra/**', 'infrastructure/**')
SEMVER = re.compile(r'v?(\d+)\.(\d+)\.(\d+)\Z')


def plan(config, paths, *, base_known, phase='tarefa', version=None, previous=None, full=False):
    """Return a visible decision, including why selection is or isn't safe."""
    reason = ''
    patterns = STRUCTURAL + tuple(config_module.get(config, 'testes.caminhos_estruturais'))
    if full or phase == 'producao':
        reason = 'produção ou suíte completa solicitada'
    elif config_module.get(config, 'projeto.modo') != 'flash':
        reason = 'modo padrão'
    elif not base_known:
        reason = 'base de comparação ausente ou desconhecida'
    elif phase == 'candidata' and not version:
        reason = 'versão de entrega não informada'
    elif any(fnmatch.fnmatchcase('/'.join(path.split('/')[start:]), pattern)
             for path in paths for start in range(len(path.split('/'))) for pattern in patterns):
        reason = 'mudança estrutural'
    elif version:
        current, old = SEMVER.fullmatch(version), SEMVER.fullmatch(previous or '')
        if not current or not old or current.groups()[:2] != old.groups()[:2]:
            reason = 'versão major/minor ou primeira entrega sem versão anterior confiável'
    if not reason and not config_module.get(config, 'comandos.testes_alterados'):
        reason = 'stack ainda não tem seletor de testes afetados'
    return {'full': bool(reason), 'reason': reason or 'Flash: testes afetados após concluir o código',
            'commands': ['testes', 'testes_aceite', 'cobertura'] if reason else ['testes_alterados']}


def _git(root, *args):
    return subprocess.run(['git', '-C', root, *args], capture_output=True, check=False)


def changes(root, base):
    """Include additions, deletions, both rename paths, local edits and untracked files without shell expansion."""
    if not base:
        return None, [], None
    resolved = _git(root, 'rev-parse', '--verify', '--end-of-options', base + '^{commit}')
    if resolved.returncode:
        return None, [], None
    sha = resolved.stdout.decode().strip()
    diff = _git(root, 'diff', '--no-renames', '--name-only', '-z', sha, '--')
    untracked = _git(root, 'ls-files', '--others', '--exclude-standard', '-z')
    if diff.returncode or untracked.returncode:
        return None, [], None
    paths = sorted(set(p.decode('utf-8', 'surrogateescape') for p in
                       (diff.stdout + untracked.stdout).split(b'\0') if p))
    tag = _git(root, 'describe', '--tags', '--abbrev=0', '--match', 'v[0-9]*', sha)
    previous = tag.stdout.decode().strip() if tag.returncode == 0 else None
    return sha, paths, previous


def run(root, config, *, base=None, phase='tarefa', version=None, full=False, simulate=False):
    if version and not SEMVER.fullmatch(version):
        raise BbError('versão de testes deve ser X.Y.Z', EXIT_USAGE)
    sha, paths, previous = changes(root, base)
    decision = plan(config, paths, base_known=sha is not None, phase=phase,
                    version=version, previous=previous, full=full)
    print(f"Testes: {'completos' if decision['full'] else 'afetados'} — {decision['reason']}", flush=True)
    print('Comandos: ' + ', '.join(decision['commands']), flush=True)
    if simulate:
        return decision
    if not any(os.path.exists(os.path.join(root, p.rstrip('/'))) for p in config['entrega']['caminhos_artefato']):
        print('Código do artefato ainda não existe (Fundação); nenhum teste executável.', flush=True)
        return decision
    with tempfile.TemporaryDirectory(prefix='bb-testes-') as temp:
        manifest = os.path.join(temp, 'alterados.json')
        with open(manifest, 'w', encoding='utf-8') as handle:
            json.dump(paths, handle, ensure_ascii=True)
        env = {**os.environ, 'BB_BASE_TESTES': sha or '', 'BB_ARQUIVOS_ALTERADOS': manifest}
        for key in decision['commands']:
            command = config_module.get(config, 'comandos.' + key)
            if not command:
                print(f'comandos.{key} vazio (defina em F2).', flush=True)
                continue
            print('+ ' + command, flush=True)
            result = subprocess.run(['bash', '-c', command], cwd=root, env=env, check=False)
            if result.returncode:
                raise BbError(f'comandos.{key} falhou (código {result.returncode})', EXIT_EXTERNAL_COMMAND)
    return decision
