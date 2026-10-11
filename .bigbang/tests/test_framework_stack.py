"""#251: trusted framework gates keep dependency checks without a system Foundation document."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from _raiz import RAIZ, importar_bb
from test_grouping_v3 import cfg

importar_bb()
from bb import config, flow_cli, pipeline_cli
from bb.errors import BbError


class FrameworkStack(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = self.temporary.name
        self.manifest = json.loads(Path(RAIZ, '.bigbang-docs.json').read_text())
        self.manifest['paginas'].pop('STACK.md', None)
        self.write_manifest()
        self.trusted = config.load(RAIZ)
        self.assertTrue(self.trusted['_framework'])

    def write(self, name, text):
        Path(self.root, name).write_text(text, encoding='utf-8')

    def write_manifest(self):
        self.write('.bigbang-docs.json', json.dumps(self.manifest))

    def problems(self, trusted=None):
        return flow_cli._content_problems(None, self.trusted if trusted is None else trusted,
                                          self.root, [], 'feature/251-framework-pipeline')

    def test_public_framework_without_runtime_packages_passes_the_content_gate(self):
        self.assertEqual(self.problems(), [])

    def test_framework_runtime_package_without_an_approved_table_is_refused(self):
        self.write('package.json', json.dumps({'dependencies': {'unapproved-package': '1.0.0'}}))
        found = self.problems()
        self.assertTrue(any('dependências de execução' in problem for problem in found), found)

    def test_framework_unreadable_dependency_ecosystem_is_still_refused(self):
        self.write('pubspec.yaml', 'name: framework_example\n')
        found = self.problems()
        self.assertTrue(any('não suportado' in problem for problem in found), found)

    def test_pr_content_cannot_select_the_framework_policy_for_a_system_base(self):
        self.write('.bigbang-framework.toml', '[project]\nrepository = "BrunodosSantosVaz/big-bang"\n')
        with self.assertRaises(BbError) as error:
            self.problems(cfg())
        self.assertIn('documento sem destino na Wiki: STACK.md', error.exception.message)

    def test_a_declared_stack_page_is_required_even_for_the_framework(self):
        self.manifest['paginas']['STACK.md'] = 'Stack'
        self.write_manifest()
        from unittest.mock import patch
        with patch('bb.documentation.checkout', return_value=Path(self.root)):
            with self.assertRaises(BbError) as error:
                self.problems()
        self.assertIn('documento obrigatório ausente: STACK.md', error.exception.message)

    def test_standalone_framework_stack_guard_uses_the_same_checks(self):
        args = SimpleNamespace(raiz=RAIZ, dados=self.root)
        self.assertEqual(pipeline_cli._stack_guard(args), 0)
        self.write('requirements.txt', 'unapproved-package==1.0.0\n')
        self.assertNotEqual(pipeline_cli._stack_guard(args), 0)
