"""E4 / #251: own pipeline, stable updater assets and template isolation."""
import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _raiz import RAIZ, importar_bb, ignorar_para_copia
importar_bb()
from bb import cli, config, generator, init, package, verify
from bb.errors import BbError
from test_launcher import JOB_HEADER, guarded

ORIGIN = 'BrunodosSantosVaz/big-bang'


class FrameworkPipeline(unittest.TestCase):
    def setUp(self):
        identity = patch.dict(os.environ, {"GITHUB_REPOSITORY": ""})
        identity.start()
        self.addCleanup(identity.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, 'repo')
        shutil.copytree(RAIZ, self.root, ignore=ignorar_para_copia())
        shutil.copy2(os.path.join(RAIZ, '.bigbang-framework.toml'), self.root)
        subprocess.run(['git', 'init', '-q', self.root], check=True)
        subprocess.run(['git', '-C', self.root, 'remote', 'add', 'origin', f'https://github.com/{ORIGIN}.git'], check=True)

    def read(self, path):
        with open(os.path.join(self.root, path), encoding='utf-8') as handle:
            return handle.read()

    def test_framework_config_is_v3_grouping_flash_and_universal(self):
        loaded = config.load(self.root)
        self.assertEqual(loaded['_dialect'], 'v3')
        for key, value in [('delivery.profile', 'compiled'), ('compiled.systems', ['universal']),
                           ('workflow.model', 'grouping'), ('project.mode', 'flash')]:
            self.assertEqual(config.get(loaded, key), value)
        self.assertEqual(config.get(loaded, 'compiled.build_universal'),
                         'python .bigbang/bin/bb.py package --output $BB_OUTPUT')
        self.assertFalse(os.path.exists(os.path.join(self.root, 'bigbang.toml')))

    def test_generate_framework_is_idempotent_guarded_and_preserves_legacy(self):
        before = {name: self.read('.github/workflows/' + name) for name in
                  ('bb-framework-ci.yml', 'bb-framework-release.yml', 'bb-framework-faxina.yml')}
        plan = generator.build_plan(self.root, framework=True)
        workflows = {path: body for path, body in plan.expected.items() if path.startswith('.github/')}
        self.assertGreaterEqual(len(workflows), 13)
        for path, body in workflows.items():
            self.assertTrue(path.startswith('.github/workflows/bb-framework-'), path)
            section = body.split('\njobs:\n', 1)[1]
            marks = list(JOB_HEADER.finditer(section))
            for mark, following in zip(marks, marks[1:] + [None]):
                self.assertTrue(guarded(section[mark.end():following.start() if following else len(section)]),
                                (path, mark.group(1)))
        generator.apply(plan, self.root)
        self.assertFalse(generator.pipeline_installed(self.root))
        self.assertEqual(generator.changes(generator.build_plan(self.root, framework=True), self.root), [])
        for name, body in before.items():
            self.assertEqual(self.read('.github/workflows/' + name), body)
        gate = self.read('.github/workflows/bb-framework-gate.yml')
        for job in ('shellcheck:', 'gitleaks:', 'alvo-docker:', 'gate:'):
            self.assertIn(job, gate)
        self.assertIn('--remote-visibility', gate)

    def test_foreign_repository_refuses_the_framework_configuration(self):
        subprocess.run(['git', '-C', self.root, 'remote', 'set-url', 'origin',
                        'https://github.com/another/system.git'], check=True)
        with self.assertRaises(BbError):
            generator.build_plan(self.root, framework=True)
        self.assertTrue(any('.bigbang-framework.toml' in problem for problem in verify.run(self.root)))

    def test_init_removes_framework_file_and_f5_removes_its_workflows(self):
        options = dict(nome='Sistema', slug='sistema', dono='another', repositorio='another/system',
                       visibilidade='privado', licenca='', modo='flash')
        init.run(self.root, options, with_github=False)
        self.assertFalse(os.path.exists(os.path.join(self.root, '.bigbang-framework.toml')))
        generator.apply(generator.build_plan(self.root, install_pipeline=True), self.root)
        self.assertFalse(any(name.startswith('bb-framework-') for name in
                             os.listdir(os.path.join(self.root, '.github/workflows'))))

    def test_prepare_version_rewrites_version_checksums_and_expected(self):
        from bb import framework
        framework.prepare(self.root, '3.0.0')
        self.assertEqual(self.read('.bigbang/VERSION').strip(), '3.0.0')
        self.assertEqual(config.get(config.load(self.root), 'bigbang.version'), '3.0.0')
        from bb import checksums
        self.assertEqual(checksums.problems(self.root), [])
        self.assertIn('v3.0.0', self.read('.bigbang/tests/esperado/compilado-windows-linux/AGENTS.md'))
        first, digest = package.build(self.root, os.path.join(self.tmp.name, 'a'))
        second, other = package.build(self.root, os.path.join(self.tmp.name, 'b'))
        self.assertEqual(os.path.basename(first), 'bigbang-v3.0.0.tar.gz')
        self.assertEqual(digest, other)
        with open(first, 'rb') as a, open(second, 'rb') as b:
            self.assertEqual(a.read(), b.read())
        with self.assertRaises(BbError):
            framework.prepare(self.root, '3.0.0-rc.1')

    def test_candidate_and_promotion_keep_updater_names(self):
        from bb import framework
        from bb import checksums
        checksums.write(self.root)
        assets = os.path.join(self.tmp.name, 'assets')
        tar, _ = framework.candidate(self.root, assets)
        calls = []
        def gh(*args):
            calls.append(args)
            if args[:3] == ('release', 'view', 'v2.0.1'):
                raise BbError('not found', 6)
            if args[:2] == ('release', 'download'):
                destination = args[args.index('--dir') + 1]
                for name in os.listdir(assets):
                    shutil.copy2(os.path.join(assets, name), destination)
            return ''
        with patch('bb.framework.github.run', side_effect=gh):
            framework.promote(self.root, 'v2.0.1-rc.1', 'v2.0.1', 'a' * 40)
        creation = next(args for args in calls if args[:2] == ('release', 'create'))
        names = [os.path.basename(arg) for arg in creation]
        self.assertIn('bigbang-v2.0.1.tar.gz', names)
        self.assertIn('bigbang-v2.0.1.tar.gz.sha256', names)
        self.assertFalse(any('-rc.' in name for name in names))
        # A tampered candidate must fail before creation.
        with open(tar, 'ab') as handle:
            handle.write(b'corrupt')
        calls.clear()
        with patch('bb.framework.github.run', side_effect=gh), self.assertRaises(BbError):
            framework.promote(self.root, 'v2.0.1-rc.1', 'v2.0.1', 'a' * 40)
        self.assertFalse(any(args[:2] == ('release', 'create') for args in calls))

    def test_framework_community_keeps_auditing_the_existing_boards(self):
        from types import SimpleNamespace
        from bb import pipeline_cli
        args = SimpleNamespace(raiz=RAIZ, dados=None, visibilidade_remota=False,
                               publicada=False, comunidade=True)
        own = config.load(self.root)
        with patch.object(pipeline_cli.docs_check, 'problems', return_value=[]), \
                patch.object(pipeline_cli.config_module, 'load', return_value=own), \
                patch.object(pipeline_cli.community_public, 'verify', return_value=[]) as audit:
            self.assertEqual(pipeline_cli._docs(args), 0)
        self.assertEqual(audit.call_args.args[1]['paineis']['planejamento'], 28)

    def test_cli_framework_and_pipeline_are_exclusive(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(cli.main(['--root', self.root, 'generate', '--framework', '--dry-run']), 0)
            self.assertNotEqual(cli.main(['--root', self.root, 'generate', '--framework', '--pipeline']), 0)


if __name__ == '__main__':
    unittest.main()
