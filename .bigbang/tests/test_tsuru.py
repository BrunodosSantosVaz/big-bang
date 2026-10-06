"""Tsuru import/deploy verifies the exact source and a fresh successful migration execution (#178)."""
import importlib.util
from pathlib import Path
import unittest
import test_deploy_catalog
from unittest.mock import patch
from _raiz import RAIZ, exemplo_toml, importar_bb

importar_bb()
from bb import config

FILE = Path(RAIZ) / '.bigbang/esteira/perfis/deploy/alvos/tsuru/scripts/tsuru.py'
IMAGE = 'ghcr.io/dono/app@sha256:' + 'a' * 64


def load_adapter():
    spec = importlib.util.spec_from_file_location('tsuru_adapter', FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeAPI:
    def __init__(self, states=()):
        self.calls = []
        self.states = list(states)
        self.info = {'job': {'spec': {'manual': True, 'container': {'command': ['npm', 'run', 'migrate']}}},
                     'units': [{'ID': 'old', 'Status': 'succeeded'}]}
        self.triggered = False

    def json(self, path, method='GET', data=None):
        self.calls.append((method, path, data))
        if path.endswith('/trigger'):
            self.triggered = True
            return {'status': 'success'}
        if self.triggered:
            units = self.states.pop(0) if self.states else []
            return dict(self.info, units=units)
        return self.info

    def deploy(self, kind, name, image):
        self.calls.append(('deploy', kind, name, image))
        if kind == 'job': self.info['job']['spec']['container']['internalRegistryImage'] = 'registry.internal/imported:v1'
        return {'source': image, 'internal': 'registry.internal/imported:v1', 'event': 'b' * 24}


class Tsuru(unittest.TestCase):
    def setUp(self):
        self.module = load_adapter()
        self.cfg = config.parse(exemplo_toml())
        self.env = {'TSURU_APP': 'snake-hom', 'TSURU_JOB_MIGRAR': 'snake-hom-migrar'}

    def run_op(self, api, op='migrar', image=IMAGE):
        return self.module.execute(op, 'staging', image, self.cfg, api, self.env,
                                   attempts=2, interval=0)

    def test_migration_imports_new_image_and_waits_for_fresh_success(self):
        api = FakeAPI([[{'ID': 'old', 'Status': 'succeeded'}, {'ID': 'new', 'Status': 'started'}],
                       [{'ID': 'old', 'Status': 'succeeded'}, {'ID': 'new', 'Status': 'succeeded'}]])
        receipt = self.run_op(api)
        self.assertEqual(receipt['execution'], 'new')
        self.assertEqual(receipt['source'], IMAGE)
        self.assertIn(('deploy', 'job', 'snake-hom-migrar', IMAGE), api.calls)
        self.assertFalse(any(c[:2] == ('deploy', 'app') for c in api.calls))

    def test_trigger_ack_or_old_success_is_not_migration_completion(self):
        for units in ([], [{'ID': 'old', 'Status': 'succeeded'}]):
            with self.subTest(units=units):
                with self.assertRaises(self.module.DeployError):
                    self.run_op(FakeAPI([units, units]))

    def test_failed_or_ambiguous_new_execution_aborts(self):
        for units in ([{'ID': 'new', 'Status': 'error'}],
                      [{'ID': 'new', 'Status': 'succeeded'}, {'ID': 'other', 'Status': 'succeeded'}]):
            with self.subTest(units=units):
                with self.assertRaises(self.module.DeployError):
                    self.run_op(FakeAPI([units]))

    def test_nonmanual_or_running_job_is_rejected_before_import(self):
        for manual, units in ((False, []), (True, [{'ID': 'running', 'Status': 'started'}])):
            api = FakeAPI(); api.info['job']['spec']['manual'] = manual; api.info['units'] = units
            with self.assertRaises(self.module.DeployError): self.run_op(api)
            self.assertFalse(any(c[0] == 'deploy' for c in api.calls))

    def test_running_execution_appearing_during_import_blocks_trigger(self):
        api = FakeAPI()
        running = dict(api.info, units=[{'ID': 'concurrent', 'Status': 'started'}])
        with patch.object(api, 'json', side_effect=[api.info, running]) as call:
            with self.assertRaises(self.module.DeployError): self.run_op(api)
            self.assertFalse(any(c.args[0].endswith('/trigger') for c in call.call_args_list))

    def test_http_deploy_verifies_event_origin_and_never_accepts_only_log_success(self):
        api = self.module.API('https://tsuru.invalid', 'dummy-token')
        with patch.object(api, 'send', return_value=(b'OK', {})):
            with self.assertRaises(self.module.DeployError): api.deploy('app', 'snake-hom', IMAGE)
        valid = {'Running': False, 'Error': '', 'Target': {'Type': 'app', 'Value': 'snake-hom'},
                 'CustomData': {'Start': {'image': IMAGE}, 'End': {'image': 'registry.internal/app:v1'}}}
        with patch.object(api, 'send', return_value=(b'', {'X-Tsuru-Eventid': 'b' * 24})) as send:
            with patch.object(api, 'json', return_value=valid) as read_event:
                receipt = api.deploy('app', 'snake-hom', IMAGE)
                self.assertEqual(receipt['event'], 'b' * 24)
                self.assertEqual(read_event.call_args.args, ('/1.1/events/' + 'b' * 24,))
                self.assertEqual(send.call_args.args, ('/1.0/apps/snake-hom/deploy', 'POST', {'image': IMAGE}))
        with self.assertRaises(self.module.DeployError):
            self.module.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

    def test_first_publication_uses_same_digest_without_migrating_again(self):
        api = FakeAPI(); api.info = {'units': []}
        receipt = self.run_op(api, 'publicar')
        self.assertEqual(receipt['source'], IMAGE)
        self.assertEqual([c for c in api.calls if c[0] == 'deploy'], [('deploy', 'app', 'snake-hom', IMAGE)])

    def test_mutable_missing_duplicate_or_multiple_images_abort_before_api(self):
        for image in ('ghcr.io/dono/app:latest', '', 'app=' + IMAGE + ',app=' + IMAGE, 'other=' + IMAGE):
            api = FakeAPI()
            with self.assertRaises(self.module.DeployError): self.run_op(api, image=image)
            self.assertEqual(api.calls, [])

    def test_http_uses_tls_and_rejects_credential_bearing_or_insecure_target(self):
        for target in ('http://tsuru.invalid', 'https://user:secret@tsuru.invalid', 'https://tsuru.invalid/?token=x'):
            with self.assertRaises(self.module.DeployError): self.module.API(target, 'dummy-token')

    def test_event_verification_rejects_failed_running_or_another_image(self):
        api = self.module.API('https://tsuru.invalid', 'dummy-token')
        valid = {'Running': False, 'Error': '', 'Target': {'Type': 'app', 'Value': 'snake-hom'},
                 'CustomData': {'Start': {'Image': IMAGE}, 'End': {'image': 'registry.internal/app:v1'}}}
        self.assertEqual(api.verify_event(valid, 'app', 'snake-hom', IMAGE)['source'], IMAGE)
        for bad in (dict(valid, Error='database password must not reach logs'), dict(valid, Running=True),
                    dict(valid, CustomData={'Start': {'Image': 'other'}, 'End': {'image': 'x'}})):
            with self.assertRaises(self.module.DeployError) as error:
                api.verify_event(bad, 'app', 'snake-hom', IMAGE)
            self.assertNotIn('database password', str(error.exception))

    def test_wrong_environment_or_unsafe_names_abort_before_api(self):
        api = FakeAPI(); self.env['TSURU_APP'] = '../other'
        with self.assertRaises(self.module.DeployError): self.run_op(api)
        self.assertEqual(api.calls, [])

    def test_initialization_preflight_is_explicitly_pending_and_never_creates_job(self):
        self.env = {'TSURU_APP': 'snake-hom', 'TSURU_MIGRACAO': 'inicializacao'}
        api = FakeAPI(); api.info = {'name': 'snake-hom', 'units': []}
        receipt = self.run_op(api)
        self.assertEqual(receipt, {'source': IMAGE, 'strategy': 'inicializacao', 'migration': 'pending'})
        self.assertEqual(api.calls, [('GET', '/1.0/apps/snake-hom', None)])

    def test_initialization_publishes_exact_image_and_verifies_event(self):
        self.env['TSURU_MIGRACAO'] = 'inicializacao'
        api = FakeAPI(); api.info = {'name': 'snake-hom', 'units': [{'ID': 'current'}]}
        receipt = self.run_op(api, 'publicar')
        self.assertEqual(receipt['source'], IMAGE)
        self.assertEqual(receipt['strategy'], 'inicializacao')
        self.assertEqual([c for c in api.calls if c[0] == 'deploy'], [('deploy', 'app', 'snake-hom', IMAGE)])

    def test_initialization_refuses_scaled_or_unidentified_application(self):
        self.env['TSURU_MIGRACAO'] = 'inicializacao'
        for info in ({'name': 'other', 'units': []}, {'name': 'snake-hom', 'units': {}},
                     {'name': 'snake-hom'}, {'name': 'snake-hom', 'units': [{}, {}]}):
            for operation in ('migrar', 'publicar'):
                with self.subTest(info=info, operation=operation):
                    api = FakeAPI(); api.info = info
                    with self.assertRaises(self.module.DeployError): self.run_op(api, operation)
                    self.assertFalse(any(c[0] == 'deploy' for c in api.calls))

    def test_unknown_migration_strategy_aborts_before_api(self):
        for strategy in ('skip', 'none', 'initialization'):
            self.env['TSURU_MIGRACAO'] = strategy
            for operation in ('migrar', 'publicar'):
                api = FakeAPI()
                with self.assertRaises(self.module.DeployError): self.run_op(api, operation)
                self.assertEqual(api.calls, [])

    def test_initialization_deployment_failure_is_not_confirmed(self):
        self.env['TSURU_MIGRACAO'] = 'inicializacao'
        api = FakeAPI(); api.info = {'name': 'snake-hom', 'units': []}
        with patch.object(api, 'deploy', side_effect=self.module.DeployError('startup failed')):
            with self.assertRaises(self.module.DeployError): self.run_op(api, 'publicar')

    def test_initialization_refuses_partial_app_info_even_when_http_succeeds(self):
        self.env['TSURU_MIGRACAO'] = 'inicializacao'
        for partial_error in ('unable to list app units', {'reason': 'unknown'}, True):
            for operation in ('migrar', 'publicar'):
                api = FakeAPI(); api.info = {'name': 'snake-hom', 'units': [], 'error': partial_error}
                with self.subTest(error=partial_error, operation=operation):
                    with self.assertRaises(self.module.DeployError) as error:
                        self.run_op(api, operation)
                    self.assertNotIn('unable to list app units', str(error.exception))
                    self.assertFalse(any(c[0] == 'deploy' for c in api.calls))


class TsuruGeneration(unittest.TestCase):
    setUp = test_deploy_catalog.CatalogoDeploy.setUp
    tearDown = test_deploy_catalog.CatalogoDeploy.tearDown
    select = test_deploy_catalog.CatalogoDeploy.select

    def test_tsuru_generates_only_its_secrets_and_limits_to_one_service(self):
        from bb import generator
        from bb.errors import BbError
        self.select('tsuru')
        plan = generator.build_plan(self.root, install_pipeline=True)
        text = plan.expected['.github/workflows/bb-candidata.yml']
        self.assertIn('TSURU_TOKEN: ${{ secrets.TSURU_TOKEN }}', text)
        self.assertIn('TSURU_MIGRACAO: ${{ vars.TSURU_MIGRACAO }}', text)
        self.assertNotIn('VPS_HOST', text)
        p = self.root / 'bigbang.toml'
        p.write_text(p.read_text().replace('[deploy]', '[deploy]\nservicos = ["app=Dockerfile", "worker=Dockerfile"]'))
        with self.assertRaises(BbError): generator.build_plan(self.root, install_pipeline=True)
        self.assertFalse((self.root / '.github/workflows/bb-candidata.yml').exists())


if __name__ == '__main__': unittest.main()
