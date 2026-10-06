"""Flash keeps test-first and selects execution conservatively after implementation."""
import copy
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _raiz import exemplo_toml, importar_bb

importar_bb()
from bb import config, decisions, generator, init, test_runs
from bb.errors import BbError


class Flash(unittest.TestCase):
    def setUp(self):
        self.config = config.parse(exemplo_toml())
        self.config['projeto']['modo'] = 'flash'
        self.config['comandos']['testes_alterados'] = 'npm run test:changed'

    def test_old_projects_default_to_standard(self):
        del self.config['projeto']['modo']
        self.assertEqual(config.validate(self.config), [])
        self.assertEqual(config.get(self.config, 'projeto.modo'), 'padrao')

    def test_invalid_mode_is_refused(self):
        self.config['projeto']['modo'] = 'flahs'
        self.assertTrue(any('projeto.modo' in e for e in config.validate(self.config)))

    def test_init_can_select_flash(self):
        options = init.resolve_options('.', 'Jogo', dono='dono', repositorio='dono/jogo', modo='flash')
        self.assertEqual(options['modo'], 'flash')
        self.assertIn('flash', '\n'.join(init.plan_steps(options, False)))

    def test_generated_policy_keeps_test_first(self):
        policy = generator.with_computed(self.config)['gerado']['modo_trabalho']
        self.assertIn('Flash', policy)
        self.assertIn('antes', policy)
        self.assertIn('produção', policy)

    def test_ordinary_change_selects_affected_tests(self):
        plan = test_runs.plan(self.config, ['src/dominio/jogo.ts'], base_known=True)
        self.assertEqual(plan['commands'], ['testes_alterados'])
        self.assertFalse(plan['full'])

    def test_standard_always_runs_complete_suite(self):
        self.config['projeto']['modo'] = 'padrao'
        self.assertTrue(test_runs.plan(self.config, ['src/jogo.ts'], base_known=True)['full'])

    def test_structural_changes_run_complete_suite(self):
        for path in ['.github/workflows/ci.yml', '.bigbang/bb/config.py', 'bigbang.toml',
                     'package-lock.json', 'migrations/0002.sql', 'Dockerfile', 'STACK.md',
                     'vite.config.ts', 'src/tsconfig.build.json', 'deploy/compose.yaml']:
            with self.subTest(path=path):
                self.assertTrue(test_runs.plan(self.config, [path], base_known=True)['full'])

    def test_nested_structural_paths_also_require_complete_suite(self):
        for path in ['apps/api/package.json', 'backend/migrations/0002.sql', 'apps/api/deploy/compose.yaml',
                     'apps/frontend/package-lock.json', 'packages/web/vite.config.ts']:
            with self.subTest(path=path):
                self.assertTrue(test_runs.plan(self.config, [path], base_known=True)['full'])

    def test_production_and_minor_major_versions_run_complete_suite(self):
        for args in [{'phase': 'producao'}, {'version': '1.5.0', 'previous': '1.4.2'},
                     {'version': '2.0.0', 'previous': '1.4.2'}, {'version': '0.1.0', 'previous': '0.0.0'}]:
            with self.subTest(args=args):
                self.assertTrue(test_runs.plan(self.config, ['src/jogo.ts'], base_known=True, **args)['full'])

    def test_patch_selects_affected_tests(self):
        plan = test_runs.plan(self.config, ['src/jogo.ts'], base_known=True,
                              version='1.4.3', previous='1.4.2')
        self.assertFalse(plan['full'])

    def test_unknown_base_or_missing_selector_never_silently_passes(self):
        self.assertTrue(test_runs.plan(self.config, ['src/jogo.ts'], base_known=False)['full'])
        no_selector = copy.deepcopy(self.config)
        no_selector['comandos']['testes_alterados'] = ''
        self.assertTrue(test_runs.plan(no_selector, ['src/jogo.ts'], base_known=True)['full'])

    def test_uncertain_release_baseline_runs_full(self):
        self.assertTrue(test_runs.plan(self.config, ['src/jogo.ts'], base_known=True,
                                      version='1.4.3')['full'])
        self.assertTrue(test_runs.plan(self.config, ['src/jogo.ts'], base_known=True,
                                      phase='candidata')['full'])

    def test_custom_structural_paths_extend_defaults(self):
        self.config['testes']['caminhos_estruturais'] = ['src/bootstrap/**']
        self.assertTrue(test_runs.plan(self.config, ['src/bootstrap/server.ts'], base_known=True)['full'])

    def test_flash_uses_ai_review_but_respects_explicit_human_review(self):
        args = ('feature/42-jogo', ['bigbang.toml'], '', [], 'test.fails')
        self.assertEqual(decisions.review_blockers(set(), set(), *args, mode='flash'), [])
        self.assertTrue(decisions.review_blockers({'revisao-humana'}, set(), *args, mode='flash'))
        self.assertTrue(decisions.review_blockers(set(), {'revisao-humana'}, *args, mode='flash'))
        self.assertTrue(decisions.review_blockers(set(), set(), *args, mode='padrao'))


class GitSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.config = config.parse(exemplo_toml())
        self.config['projeto']['modo'] = 'flash'
        self.config['comandos']['testes_alterados'] = 'selector'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Teste')
        self.git('config', 'user.email', 'teste@example.invalid')
        self.write('src/velho.ts', 'old')
        self.git('add', '.')
        self.git('commit', '-qm', 'initial')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.run(['git', '-C', self.root, *args], capture_output=True,
                              text=True, check=True).stdout.strip()

    def write(self, path, text):
        target = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w', encoding='utf-8') as handle:
            handle.write(text)

    def test_manifest_includes_deleted_renamed_and_untracked_paths_as_data(self):
        os.rename(os.path.join(self.root, 'src/velho.ts'), os.path.join(self.root, 'src/novo.ts'))
        special = 'src/nome com espaço; $(echo proibido).ts'
        self.write(special, 'new')
        sha, paths, _ = test_runs.changes(self.root, self.base)
        self.assertEqual(sha, self.base)
        self.assertEqual(paths, sorted(['src/velho.ts', 'src/novo.ts', special]))
        real_run = subprocess.run
        captured = []

        def execute(args, **kwargs):
            if args[0] == 'git':
                return real_run(args, **kwargs)
            self.assertEqual(args, ['bash', '-c', 'selector'])
            with open(kwargs['env']['BB_ARQUIVOS_ALTERADOS'], encoding='utf-8') as handle:
                captured.append(json.load(handle))
            self.assertEqual(kwargs['env']['BB_BASE_TESTES'], self.base)
            return subprocess.CompletedProcess(args, 0)

        with patch('bb.test_runs.subprocess.run', side_effect=execute):
            test_runs.run(self.root, self.config, base=self.base)
        self.assertEqual(captured, [paths])

    def test_selector_failure_does_not_pass(self):
        real_run = subprocess.run

        def execute(args, **kwargs):
            return real_run(args, **kwargs) if args[0] == 'git' else subprocess.CompletedProcess(args, 7)

        with patch('bb.test_runs.subprocess.run', side_effect=execute):
            with self.assertRaises(BbError):
                test_runs.run(self.root, self.config, base=self.base)

    def test_option_injection_cannot_be_a_git_base(self):
        sha, _, _ = test_runs.changes(self.root, '--help')
        self.assertIsNone(sha)


if __name__ == '__main__':
    unittest.main()
