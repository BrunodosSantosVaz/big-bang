"""Tsuru API v1.32 adapter. Secrets and server logs never enter output; import provenance is verified via events."""
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

NAME = re.compile(r'[a-z][a-z0-9-]{0,62}\Z')
DIGEST = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}\Z')


class DeployError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeployError('Tsuru redirecionou a API; credencial não foi reenviada.')


class API:
    def __init__(self, target, token):
        parsed = urllib.parse.urlsplit(target)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise DeployError('TSURU_TARGET exige origem HTTPS sem credencial, caminho, query ou fragmento.')
        if not token or '\n' in token or '\r' in token:
            raise DeployError('Defina TSURU_TOKEN no ambiente protegido.')
        self.target = target.rstrip('/')
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def send(self, path, method='GET', data=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        request = urllib.request.Request(self.target + path, data=body, method=method,
                    headers={'Authorization': 'bearer ' + self.token, 'User-Agent': 'tsuru-client/1.37.0',
                             'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with self.opener.open(request, timeout=600 if path.endswith('/deploy') else 30) as response:
                content = response.read(8 * 1024 * 1024 + 1)
                if len(content) > 8 * 1024 * 1024:
                    raise DeployError('Resposta Tsuru excedeu o limite; operação não confirmada.')
                return content, response.headers
        except urllib.error.HTTPError as error:
            raise DeployError(f'Tsuru recusou operação (HTTP {error.code}); consulte o evento no servidor.') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise DeployError('Tsuru indisponível ou timeout; operação não confirmada.') from None

    def json(self, path, method='GET', data=None):
        content, _ = self.send(path, method, data)
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict): raise DeployError('Objeto JSON Tsuru inválido.')
            return parsed
        except (ValueError, UnicodeError):
            raise DeployError('Resposta JSON Tsuru inválida; operação não confirmada.') from None

    def verify_event(self, event, kind, name, image):
        if not isinstance(event, dict): raise DeployError('Evento Tsuru inválido.')
        target = event.get('Target', {})
        custom = event.get('CustomData', {})
        if not isinstance(custom, dict): raise DeployError('Proveniência Tsuru inválida.')
        start, end = custom.get('Start') or {}, custom.get('End') or {}
        if (event.get('Running') is not False or event.get('Error') != ''
                or target != {'Type': kind, 'Value': name}
                or not isinstance(start, dict) or not isinstance(end, dict)
                or start.get('image', start.get('Image')) != image
                or not isinstance(end.get('image'), str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]*(?:@sha256:[0-9a-f]{64})?', end['image'])):
            raise DeployError('Evento Tsuru não confirma sucesso e origem exata da imagem.')
        return {'source': image, 'internal': end['image']}

    def deploy(self, kind, name, image):
        path = f'/1.23/jobs/{name}/deploy' if kind == 'job' else f'/1.0/apps/{name}/deploy'
        _, headers = self.send(path, 'POST', {'image': image})
        event_id = headers.get('X-Tsuru-Eventid', '')
        if not re.fullmatch(r'[0-9a-f]{24}', event_id):
            raise DeployError('Tsuru não forneceu evento verificável; publicação não confirmada.')
        for attempt in range(20):
            event = self.json('/1.1/events/' + event_id)
            if event.get('Running') is False:
                return dict(self.verify_event(event, kind, name, image), event=event_id)
            if attempt < 19: time.sleep(1)
        raise DeployError('Evento Tsuru não concluiu no prazo; publicação não confirmada.')


def image_ref(images, cfg):
    services = [item.split('=', 1)[0] for item in cfg.get('deploy', {}).get('servicos', ['app=Dockerfile'])]
    if len(services) != 1 or ',' in images:
        raise DeployError('O alvo Tsuru aceita um serviço por aplicação; informe exatamente uma imagem.')
    if '=' in images:
        name, image = images.split('=', 1)
        if name != services[0]: raise DeployError('Serviço da imagem não corresponde à configuração.')
    else: image = images
    if not DIGEST.fullmatch(image): raise DeployError('Imagem exige digest sha256 imutável; tag recusada.')
    return image


def job_units(info):
    units = info.get('units') or []
    if not isinstance(units, list) or any(not isinstance(u, dict) or not u.get('ID') or not u.get('Status') for u in units):
        raise DeployError('Unidades Tsuru sem identidade/estado confiável.')
    if len({u['ID'] for u in units}) != len(units): raise DeployError('Unidades Tsuru duplicadas.')
    return units


def execute(operation, environment, images, cfg, api, env, attempts=120, interval=5):
    if environment not in ('staging', 'producao'): raise DeployError('Ambiente inválido.')
    app = env.get('TSURU_APP', '')
    if not NAME.fullmatch(app): raise DeployError('Defina TSURU_APP com nome seguro da aplicação existente.')
    image = image_ref(images, cfg)
    strategy = env.get('TSURU_MIGRACAO') or 'job'
    if strategy not in ('job', 'inicializacao'):
        raise DeployError('TSURU_MIGRACAO aceita job (padrão) ou inicializacao.')
    if operation not in ('migrar', 'publicar'): raise DeployError('Operação inválida.')
    if strategy == 'inicializacao':
        info = api.json(f'/1.0/apps/{app}')
        units = info.get('units')
        if (info.get('name') != app or info.get('error') not in (None, '')
                or not isinstance(units, list) or len(units) > 1
                or any(not isinstance(unit, dict) for unit in units)):
            raise DeployError('Migração na inicialização exige aplicação identificada com no máximo uma unidade.')
        if operation == 'migrar':
            # A separate job cannot access an application's SQLite PVC. The immutable image must migrate the
            # mounted file before listening. This preflight is deliberately not a successful migration receipt.
            return {'source': image, 'strategy': strategy, 'migration': 'pending'}
        return dict(api.deploy('app', app, image), strategy=strategy)
    if operation == 'publicar':
        api.json(f'/1.0/apps/{app}')  # existing app may have zero units on its first deployment
        return api.deploy('app', app, image)
    job = env.get('TSURU_JOB_MIGRAR', '')
    if not NAME.fullmatch(job): raise DeployError('Defina TSURU_JOB_MIGRAR com nome do job manual existente.')
    path = '/1.13/jobs/' + job
    info = api.json(path)
    spec = info.get('job', {}).get('spec', {})
    if spec.get('manual') is not True or not spec.get('container', {}).get('command'):
        raise DeployError('Migração exige job manual com comando revisado e configurado.')
    if any(u['Status'] not in ('succeeded', 'error') for u in job_units(info)):
        raise DeployError('Já há migração em curso; aguarde antes de importar nova imagem.')
    receipt = api.deploy('job', job, image)
    imported = api.json(path)
    after_spec = imported.get('job', {}).get('spec', {})
    if (after_spec.get('manual') is not True
            or after_spec.get('container', {}).get('command') != spec['container']['command']
            or after_spec.get('container', {}).get('internalRegistryImage') != receipt['internal']
            or any(u['Status'] not in ('succeeded', 'error') for u in job_units(imported))):
        raise DeployError('Job mudou ou iniciou durante a importação; execução não disparada.')
    before = {u['ID'] for u in job_units(imported)}
    api.json(path + '/trigger', 'POST', {})
    execution = None
    for attempt in range(attempts):
        current = api.json(path)
        if current.get('job', {}).get('spec', {}).get('container', {}).get('internalRegistryImage') != receipt['internal']:
            raise DeployError('Imagem do job mudou durante a execução; migração não confirmada.')
        new = [u for u in job_units(current) if u['ID'] not in before]
        if len(new) > 1: raise DeployError('Execução concorrente inesperada; migração não confirmada.')
        if new:
            unit = new[0]
            if execution is not None and execution != unit['ID']:
                raise DeployError('Identidade da execução mudou; migração não confirmada.')
            execution = unit['ID']
            if unit['Status'] == 'error': raise DeployError('Migração falhou; aplicação não foi trocada.')
            if unit['Status'] == 'succeeded': return dict(receipt, execution=execution)
        if attempt < attempts - 1: time.sleep(interval)
    raise DeployError('Migração não concluiu no prazo; aplicação não foi trocada.')


def main(argv=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
    from bb.config import load
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 3: raise DeployError('Uso: tsuru.py migrar|publicar staging|producao imagem@sha256:…')
        cfg = load(Path.cwd())
        api = API(os.environ.get('TSURU_TARGET', ''), os.environ.get('TSURU_TOKEN', ''))
        receipt = execute(*args, cfg, api, os.environ)
        print('Tsuru confirmou: ' + json.dumps(receipt, ensure_ascii=False))
    except (DeployError, ValueError, KeyError, TypeError) as error:
        # Do not relay API bodies, logs, envs or exception details containing secrets.
        print('::error::' + (str(error) if isinstance(error, DeployError) else 'Dados Tsuru inválidos.'), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
