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

    def test_green_same_sha_reuses_tests(self):
        self.estado['checks']['sha-atual'] = [{'name': 'check', 'status': 'completed', 'conclusion': 'success'}]
        self.gravar_estado()
        result = self.rodar('testes-candidata.sh', env={'BB': self.bb, 'GITHUB_SHA': 'sha-atual'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('reutilizada', result.stdout)

    def test_failed_same_sha_is_refused(self):
        self.estado['checks']['sha-atual'] = [{'name': 'check', 'status': 'completed', 'conclusion': 'failure'}]
        self.gravar_estado()
        result = self.rodar('testes-candidata.sh', env={'BB': self.bb, 'GITHUB_SHA': 'sha-atual'})
        self.assertNotEqual(result.returncode, 0)

    def test_success_another_sha_is_not_reused(self):
        self.estado['checks']['sha-antigo'] = [{'name': 'check', 'status': 'completed', 'conclusion': 'success'}]
        self.gravar_estado()
        result = self.rodar('testes-candidata.sh', env={'BB': self.bb, 'GITHUB_SHA': 'sha-atual',
                                                     'BB_CHECK_TENTATIVAS': '1'})
        self.assertNotEqual(result.returncode, 0)

    def test_workflows_force_complete_suite_before_production(self):
        path = '.bigbang/esteira/nucleo/arquivos/.github/workflows/bb-publicar-producao.yml.tmpl'
        text = ler(path)
        self.assertIn('bb.py testes --fase producao', text)
        self.assertIn('needs: [conferir, testes-producao]', text)
        self.assertIn('environment: producao', text)


if __name__ == '__main__':
    unittest.main()
