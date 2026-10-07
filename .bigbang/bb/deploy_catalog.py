"""Installed deploy contracts (ADR-0016): syntax belongs to config; capabilities to the installed framework.

Discovery is read-only. A delivery must resolve before the generator plans or writes any file. Reserved entries
document future integrations without claiming support. No provider names are hardcoded in the CLI or generator.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

from .errors import BbError, EXIT_INVALID_CONFIG
from .paths import framework_dir

NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
REQUIRED_OPERATIONS = {"publicar", "migrar", "saude", "voltar"}
STATES = {"implementado", "reservado"}
MAX_CONTRACT_BYTES = 65536


@dataclass(frozen=True)
class Target:
    name: str
    description: str
    state: str
    artifacts: tuple
    operations: tuple
    variables: tuple
    secrets: tuple
    folder: Path
    max_services: int | None = None


@dataclass(frozen=True)
class Artifact:
    name: str
    description: str
    state: str
    identity: str
    scripts: dict
    folder: Path


def _fail(message):
    raise BbError(message, EXIT_INVALID_CONFIG)


def _inside(path, parent):
    if not path.resolve().is_relative_to(parent.resolve()):
        _fail(f"{path}: aponta para fora de {parent}")
    return path


def _base(root, collection):
    return Path(framework_dir(root)) / 'esteira/perfis/deploy' / collection


def _read(root, collection, name, filename, keys, optional=frozenset()):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        _fail(f"nome de {collection} inválido: {name!r}")
    base = _base(root, collection)
    folder = _inside(base / name, base)
    path = _inside(folder / filename, folder)
    if not path.is_file():
        _fail(f"{collection}: '{name}' não tem contrato instalado ({filename}); consulte bb alvos")
    if path.stat().st_size > MAX_CONTRACT_BYTES:
        _fail(f"{path}: contrato excede {MAX_CONTRACT_BYTES} bytes")
    try:
        with path.open('rb') as handle:
            data = tomllib.load(handle)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        _fail(f"{path}: contrato TOML inválido ({exc})")
    missing, extra = keys - set(data), set(data) - keys - optional
    if missing or extra:
        _fail(f"{path}: chaves ausentes {sorted(missing)}; desconhecidas {sorted(extra)}")
    if not isinstance(data['descricao'], str) or not data['descricao'].strip():
        _fail(f"{path}: descricao deve ser texto não vazio")
    if not isinstance(data['situacao'], str) or data['situacao'] not in STATES:
        _fail(f"{path}: situacao deve ser implementado ou reservado")
    return folder, data


def _names(data, key, pattern=NAME, non_empty=True):
    value = data[key]
    if not isinstance(value, list) or (non_empty and not value) or any(
            not isinstance(item, str) or not pattern.fullmatch(item) for item in value):
        _fail(f"{key}: deve ser uma lista de nomes válidos" + (" não vazia" if non_empty else ""))
    if len(value) != len(set(value)):
        _fail(f"{key}: nomes repetidos")
    return tuple(value)


def _file(path, parent):
    _inside(path, parent)
    if not path.is_file() or path.stat().st_size == 0:
        _fail(f"{path}: script obrigatório ausente ou vazio")


def read_target(root, name):
    folder, data = _read(root, 'alvos', name, 'alvo.toml', {
        'descricao', 'situacao', 'artefatos', 'operacoes', 'variaveis', 'segredos'}, optional={'servicos_maximos'})
    maximum = data.get('servicos_maximos')
    if maximum is not None and (type(maximum) is not int or maximum < 1):
        _fail(f'{name}: servicos_maximos deve ser inteiro positivo')
    artifacts = _names(data, 'artefatos')
    operations = _names(data, 'operacoes')
    if not REQUIRED_OPERATIONS <= set(operations) or set(operations) - REQUIRED_OPERATIONS - {'checar'}:
        _fail(f"{name}: operacoes exige publicar, migrar, saude e voltar (checar é opcional)")
    variables = _names(data, 'variaveis', ENV_NAME, non_empty=False)
    secrets = _names(data, 'segredos', ENV_NAME, non_empty=False)
    reserved = {'GH_TOKEN', 'IMAGEM', 'VERSAO', 'SIMULAR', 'RC_TAG', 'TAG', 'TARGET_SHA',
                'BB', 'PATH', 'HOME', 'PYTHONPATH', 'PYTHONHOME', 'NODE_OPTIONS', 'BASH_ENV', 'ENV'}
    if any(name in reserved or name.startswith(('BB_', 'GITHUB_', 'RUNNER_', 'INPUT_', 'LD_'))
           for name in variables + secrets):
        _fail(f"{name}: nome de ambiente reservado ao processo/esteira")
    if set(variables) & set(secrets):
        _fail(f"{name}: variaveis e segredos não podem repetir o mesmo nome")
    if data['situacao'] == 'implementado':
        _file(folder / 'scripts/alvo.sh', folder)
    return Target(name, data['descricao'], data['situacao'], artifacts, operations, variables, secrets, folder, maximum)


def read_artifact(root, name):
    folder, data = _read(root, 'artefatos', name, 'artefato.toml', {
        'descricao', 'situacao', 'identidade', 'scripts'})
    if not isinstance(data['identidade'], str) or data['identidade'] not in ('digest', 'sha256'):
        _fail(f"{name}: identidade deve ser digest ou sha256")
    scripts = data['scripts']
    if not isinstance(scripts, dict) or set(scripts) - {'construir', 'candidata', 'promover'}:
        _fail(f"{name}: scripts deve conter construir, candidata e promover")
    if data['situacao'] == 'implementado' and set(scripts) != {'construir', 'candidata', 'promover'}:
        _fail(f"{name}: scripts exige construir, candidata e promover")
    framework = Path(framework_dir(root))
    for operation, relative in scripts.items():
        # Paths are portable framework-relative names, never shell commands or paths outside the package.
        if not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+\.sh", relative) or any(
                part in ('', '.', '..') for part in relative.split('/')):
            _fail(f"{name}: scripts.{operation} deve ser caminho relativo seguro de um script .sh")
        _file(framework / relative, framework)
    return Artifact(name, data['descricao'], data['situacao'], data['identidade'], dict(scripts), folder)


def resolve(root, config):
    """Return a compatible implemented target/artifact pair, or a configuration error before any write."""
    target = read_target(root, config['entrega']['alvo'])
    if target.state != 'implementado':
        _fail(f"entrega.alvo: '{target.name}' é reservado, sem implementação; consulte bb alvos")
    if target.max_services is not None and len(config['deploy'].get('servicos', ['app=Dockerfile'])) > target.max_services:
        _fail(f'{target.name}: aceita no máximo {target.max_services} serviço por aplicação')
    if config['deploy'].get('servico_checar') and 'checar' not in target.operations:
        _fail(f'{target.name}: não implementa a pré-checagem configurada')
    artifact = read_artifact(root, config['deploy'].get('artefato', 'imagem'))
    if artifact.state != 'implementado':
        _fail(f"deploy.artefato: '{artifact.name}' é reservado, sem implementação; consulte bb alvos")
    if artifact.identity != 'digest':
        _fail(f"deploy.artefato: '{artifact.name}' exige entrega por hashes, ainda não implementada no perfil deploy")
    if artifact.name not in target.artifacts:
        _fail(f"entrega.alvo: '{target.name}' não aceita o artefato '{artifact.name}'")
    return target, artifact


def entries(root, collection):
    """List each installed entry independently; a broken adapter is visible and never reported as ready."""
    base = _base(root, collection)
    reader = read_target if collection == 'alvos' else read_artifact
    if not base.is_dir():
        return []
    result = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or folder.name.startswith('.') or folder.name == '__pycache__':
            continue
        try:
            result.append((folder.name, reader(root, folder.name), None))
        except BbError as exc:
            result.append((folder.name, None, exc.message))
    return result


def problems(root):
    return [error for collection in ('alvos', 'artefatos')
            for _, _, error in entries(root, collection) if error]
