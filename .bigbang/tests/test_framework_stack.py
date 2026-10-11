"""#251: trusted framework gates keep dependency checks without a system Foundation document."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from _raiz import RAIZ, importar_bb

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
        Path(self.root, name).parent.mkdir(parents=True, exist_ok=True)
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
        system = dict(self.trusted)
        system.pop('_framework')
        with self.assertRaises(BbError) as error:
            self.problems(system)
        self.assertIn('documento sem destino na Wiki: STACK.md', error.exception.message)

    def test_a_declared_stack_page_is_required_even_for_the_framework(self):
        self.manifest['paginas']['STACK.md'] = 'Stack'
        self.write_manifest()
        from unittest.mock import patch
        with patch('bb.documentation.checkout', return_value=Path(self.root)):
            with self.assertRaises(BbError) as error:
                self.problems()
        self.assertIn('documento obrigatório ausente: STACK.md', error.exception.message)

    def test_a_declared_stack_keeps_the_normal_approved_package_table(self):
        self.manifest['paginas']['STACK.md'] = 'Stack'
        self.write_manifest()
        self.write('Stack.md', '<!-- bb:dependencias:inicio -->\n'
                   '| approved-package | npm |\n<!-- bb:dependencias:fim -->\n')
        self.write('package.json', json.dumps({'dependencies': {'approved-package': '1.0.0'}}))
        from unittest.mock import patch
        with patch('bb.documentation.checkout', return_value=Path(self.root)):
            self.assertEqual(self.problems(), [])
            self.write('package.json', json.dumps({'dependencies': {'unapproved-package': '1.0.0'}}))
            self.assertTrue(any('não está na tabela' in problem for problem in self.problems()))

    def test_standalone_framework_stack_guard_uses_the_same_checks(self):
        args = SimpleNamespace(raiz=RAIZ, dados=self.root)
        self.assertEqual(pipeline_cli._stack_guard(args), 0)
        self.write('requirements.txt', 'unapproved-package==1.0.0\n')
        self.assertNotEqual(pipeline_cli._stack_guard(args), 0)

    def test_framework_runtime_manifests_inside_bigbang_are_refused_by_both_gates(self):
        manifests = {
            '.bigbang/requirements.txt': 'unapproved-package==1.0.0\n',
            '.bigbang/pyproject.toml': '[project]\ndependencies = ["unapproved-package==1.0.0"]\n',
            '.bigbang/bb/package.json': json.dumps({'dependencies': {'unapproved-package': '1.0.0'}}),
        }
        args = SimpleNamespace(raiz=RAIZ, dados=self.root)
        for path, body in manifests.items():
            with self.subTest(path=path):
                self.write(path, body)
                self.assertTrue(any('dependências de execução' in p for p in self.problems()))
                self.assertNotEqual(pipeline_cli._stack_guard(args), 0)
                Path(self.root, path).unlink()

    def test_framework_unsupported_ecosystem_inside_bigbang_is_refused(self):
        self.write('.bigbang/pubspec.yaml', 'name: framework_example\n')
        self.assertTrue(any('não suportado' in p for p in self.problems()))
        self.assertNotEqual(pipeline_cli._stack_guard(SimpleNamespace(raiz=RAIZ, dados=self.root)), 0)

    def test_framework_test_fixtures_are_not_runtime_dependency_declarations(self):
        self.write('.bigbang/tests/fixture/requirements.txt', 'fixture-only-package==1.0.0\n')
        self.write('.bigbang/tests/fixture/pubspec.yaml', 'name: fixture_example\n')
        self.assertEqual(self.problems(), [])
        self.assertEqual(pipeline_cli._stack_guard(SimpleNamespace(raiz=RAIZ, dados=self.root)), 0)

    def test_a_declared_stack_checks_approved_and_unapproved_framework_packages(self):
        self.manifest['paginas']['STACK.md'] = 'Stack'
        self.write_manifest()
        self.write('Stack.md', '<!-- bb:dependencias:inicio -->\n'
                   '| approved-package | pypi |\n<!-- bb:dependencias:fim -->\n')
        self.write('.bigbang/requirements.txt', 'approved-package==1.0.0\n')
        from unittest.mock import patch
        with patch('bb.documentation.checkout', return_value=Path(self.root)):
            self.assertEqual(self.problems(), [])
            self.write('.bigbang/requirements.txt', 'unapproved-package==1.0.0\n')
            self.assertTrue(any('não está na tabela' in p for p in self.problems()))

    def test_normal_system_stack_guard_keeps_ignoring_the_inherited_framework(self):
        self.write('.bigbang/requirements.txt', 'framework-only-package==1.0.0\n')
        self.write('bigbang.toml', '[projeto]\nvisibilidade = "privado"\n')
        self.assertEqual(self.problems({k: v for k, v in self.trusted.items() if k != '_framework'}), [])

    def test_packaged_framework_directories_are_not_skipped_as_system_build_outputs(self):
        for folder in ('bin', 'build', 'dist', 'vendor', 'node_modules', 'target', 'obj'):
            with self.subTest(folder=folder):
                name = '.bigbang/' + folder + '/requirements.txt'
                self.write(name, 'unapproved-package==1.0.0\n')
                self.assertTrue(any('dependências de execução' in p for p in self.problems()))
                Path(self.root, name).unlink()
