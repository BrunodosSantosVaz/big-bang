"""Candidates reuse successful CI of the same SHA, never green results from a different commit."""
import os
import subprocess
import unittest

from _raiz import ler
from test_kanban_mesclar import ComBb


class FlashCandidate(ComBb):
    def setUp(self):
        super().setUp()
        config = os.path.join(self.pasta, 'projeto', 'bigbang.toml')
        with open(config, encoding='utf-8') as handle:
            text = handle.read()
        with open(config, 'w', encoding='utf-8') as handle:
            handle.write(text.replace('modo = "padrao"', 'modo = "flash"'))
        self.estado['comandos'] = {'run list': ''}
        self.gravar_estado()

    def test_green_same_sha_reuses_tests(self):
        self.estado['comandos']['run list'] = '500\tcompleted\tsuccess\tsha-atual\n'
        self.gravar_estado()
        result = self.rodar('testes-candidata.sh', env={'BB': self.bb, 'GITHUB_SHA': 'sha-atual'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('reutilizada', result.stdout)
        command = next(c for c in self.chamadas() if c[:2] == ['run', 'list'])
        self.assertIn('bb-ci.yml', command)
        self.assertIn('--commit', command)
        self.assertIn('push', command)

    def test_failed_same_sha_is_refused(self):
        self.estado['comandos']['run list'] = '500\tcompleted\tfailure\tsha-atual\n'
        self.gravar_estado()
        result = self.rodar('testes-candidata.sh', env={'BB': self.bb, 'GITHUB_SHA': 'sha-atual'})
        self.assertNotEqual(result.returncode, 0)

    def test_success_another_sha_is_not_reused(self):
        self.estado['comandos']['run list'] = '500\tcompleted\tsuccess\tsha-antigo\n'
        self.gravar_estado()
        result = self.rodar('testes-candidata.sh', env={'BB': self.bb, 'GITHUB_SHA': 'sha-atual',
                                                     'BB_CHECK_TENTATIVAS': '1'})
        self.assertNotEqual(result.returncode, 0)

    def test_workflows_force_complete_suite_before_production(self):
        path = '.bigbang/esteira/nucleo/arquivos/.github/workflows/bb-publicar-producao.yml.tmpl'
        text = ler(path)
        self.assertIn('scripts/testes-producao.sh', text)
        self.assertIn('testes --fase producao', ler('.bigbang/esteira/nucleo/scripts/testes-producao.sh'))
        script = ler('.bigbang/esteira/nucleo/scripts/testes-producao.sh')
        self.assertNotIn('git fetch', script)
        self.assertIn('refs/remotes/origin/release/', script)
        self.assertIn('needs: [conferir, testes-producao]', text)
        self.assertIn('environment: producao', text)
        self.assertIn('BB_SHA_TESTADO: ${{ needs.testes-producao.outputs.sha }}', text)

    def test_completed_release_can_resume_without_deleted_release_branch(self):
        self.estado['releases'] = ['v1.4.2']
        self.gravar_estado()
        output = os.path.join(self.pasta, 'output')
        result = self.rodar('testes-producao.sh', env={'BB': self.bb, 'VERSAO': '1.4.2',
                                                     'GITHUB_OUTPUT': output})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('retomada', result.stdout)
        with open(output, encoding='utf-8') as handle:
            self.assertEqual(handle.read(), 'sha=retomada\n')


if __name__ == '__main__':
    unittest.main()
