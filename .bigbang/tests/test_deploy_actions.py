"""Workflows expose only the selected target's credentials and runner (#176)."""
import os
import subprocess
import unittest
import test_deploy_catalog
from bb import config, generator


class DeployActions(unittest.TestCase):
    setUp = test_deploy_catalog.CatalogoDeploy.setUp
    tearDown = test_deploy_catalog.CatalogoDeploy.tearDown
    target = test_deploy_catalog.CatalogoDeploy.target
    select = test_deploy_catalog.CatalogoDeploy.select

    def workflows(self):
        plan = generator.build_plan(self.root, install_pipeline=True)
        return {name: plan.expected['.github/workflows/' + name] for name in
                ('bb-candidata.yml', 'bb-publicar-producao.yml', 'bb-voltar-versao.yml')}

    def test_target_credentials_do_not_leak_between_providers(self):
        self.target(); self.select('novo-provedor')
        for text in self.workflows().values():
            self.assertIn('TESTE_APP: ${{ vars.TESTE_APP }}', text)
            self.assertIn('TESTE_TOKEN: ${{ secrets.TESTE_TOKEN }}', text)
            self.assertNotIn('VPS_HOST', text)
            self.assertNotIn('VPS_CHAVE_SSH', text)
            self.assertNotIn('REGISTRY_TOKEN', text)

    def test_vps_current_credentials_and_human_environment_preserved(self):
        for text in self.workflows().values():
            self.assertIn('VPS_CHAVE_SSH: ${{ secrets.VPS_CHAVE_SSH }}', text)
            self.assertNotIn('TESTE_TOKEN', text)
        self.assertIn('environment: producao', self.workflows()['bb-publicar-producao.yml'])
        self.assertIn('environment: producao', self.workflows()['bb-voltar-versao.yml'])

    def test_deployment_runner_is_configurable_without_changing_build_runner(self):
        p = self.root / 'bigbang.toml'
        p.write_text(p.read_text().replace('[deploy]', '[deploy]\nrunner = ["self-hosted", "tsuru-rede"]'))
        for text in self.workflows().values():
            self.assertIn('runs-on: ["self-hosted", "tsuru-rede"]', text)
            self.assertIn('runs-on: ubuntu-24.04', text)

    def test_unsafe_runner_labels_rejected(self):
        cfg = config.load(self.root)
        cfg['deploy']['runner'] = ['${{ secrets.TOKEN }}']
        self.assertTrue(config.validate(cfg))

    def test_network_preparation_is_only_in_real_deployment_steps(self):
        for name, text in self.workflows().items():
            self.assertIn('scripts/preparar-alvo.sh', text)
            if name != 'bb-candidata.yml':
                self.assertIn('!inputs.simular', text)

    def test_network_preparation_executes_once_and_failure_stops_target_setup(self):
        p = self.root / 'bigbang.toml'
        log = self.root / 'network.log'
        text = p.read_text()
        p.write_text(text.replace('[deploy]', '[deploy]\npreparar_rede = "echo network >> network.log"'))
        setup = self.targets / 'vps-docker/scripts/preparar.sh'
        setup.write_text('echo target >> network.log\n')
        result = subprocess.run(['bash', '.bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh'],
                                cwd=self.root, env=dict(os.environ, BB='python3.11 .bigbang/bin/bb.py'),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text(), 'network\ntarget\n')
        p.write_text(text.replace('[deploy]', '[deploy]\npreparar_rede = "exit 7"'))
        result = subprocess.run(['bash', '.bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh'],
                                cwd=self.root, env=dict(os.environ, BB='python3.11 .bigbang/bin/bb.py'))
        self.assertEqual(result.returncode, 7)
        self.assertEqual(log.read_text(), 'network\ntarget\n')

    def test_target_cannot_override_runtime_credentials_or_process_controls(self):
        for name in ('GH_TOKEN', 'IMAGEM', 'GITHUB_OUTPUT', 'PATH', 'BB', 'PYTHONPATH'):
            with self.subTest(name=name):
                self.target(text=test_deploy_catalog.TARGET.replace('TESTE_APP', name))
                self.select('novo-provedor')
                with self.assertRaises(Exception):
                    self.workflows()

    def test_artifact_build_and_candidate_scripts_come_from_contract(self):
        p = self.artifacts / 'imagem/artefato.toml'
        f = self.root / '.bigbang/custom-build.sh'
        f.write_text('#!/usr/bin/env bash\nexit 0\n')
        p.write_text(p.read_text().replace('esteira/perfis/deploy/scripts/candidata-imagem.sh', 'custom-build.sh'))
        self.assertIn('bash .bigbang/custom-build.sh', self.workflows()['bb-candidata.yml'])


if __name__ == '__main__':
    unittest.main()
