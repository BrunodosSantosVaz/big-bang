"""The real Tsuru shell adapter preserves staging gates, bounded health and rollback without migration."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
import test_deploy_catalog

IMAGE = 'ghcr.io/dono/app@sha256:' + 'a' * 64


class TsuruScripts(unittest.TestCase):
    setUp = test_deploy_catalog.CatalogoDeploy.setUp
    tearDown = test_deploy_catalog.CatalogoDeploy.tearDown
    select = test_deploy_catalog.CatalogoDeploy.select

    def setup_commands(self):
        self.select('tsuru')
        p = self.root / 'bigbang.toml'
        p.write_text(p.read_text().replace('npm run test:smoke', 'true'))
        folder = self.root / 'fake-bin'; folder.mkdir()
        commands = {
            'python3': 'echo "$2" >> "$LOG"\n[ "$2" != migrar ] || [ "${FAIL_MIGRATION:-0}" != 1 ]',
            'gh': 'printf "%s\\n" "$IMAGE"',
            'curl': 'echo health >> "$LOG"\n[ "${FAIL_HEALTH:-0}" != 1 ]',
            'docker': 'echo scanner >> "$LOG"',
        }
        for name, text in commands.items():
            f = folder / name; f.write_text('#!/usr/bin/env bash\n' + text + '\n'); f.chmod(0o755)
        self.log = self.root / 'calls'
        return dict(os.environ, PATH=str(folder) + os.pathsep + os.environ['PATH'],
                    LOG=str(self.log), IMAGE=IMAGE, IMAGEM=IMAGE, GITHUB_REPOSITORY='dono/app',
                    BB=f'{sys.executable} .bigbang/bin/bb.py', SAUDE_TENTATIVAS='2', SAUDE_INTERVALO='0')

    def run_script(self, path, *args, env):
        return subprocess.run(['bash', '.bigbang/esteira/perfis/deploy/' + path, *args],
                              cwd=self.root, env=env, capture_output=True, text=True)

    def test_staging_failure_does_not_publish_or_scan(self):
        env = self.setup_commands(); env['FAIL_MIGRATION'] = '1'
        result = self.run_script('scripts/staging.sh', env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.log.read_text().splitlines(), ['migrar'])

    def test_staging_success_keeps_migration_publication_health_scanner_order(self):
        result = self.run_script('scripts/staging.sh', env=self.setup_commands())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['migrar', 'publicar', 'health', 'scanner'])

    def test_rollback_reimports_release_without_migration(self):
        result = self.run_script('alvos/tsuru/scripts/alvo.sh', 'voltar', 'producao', 'v1.0.0', env=self.setup_commands())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['publicar'])

    def test_health_failure_is_bounded(self):
        env = self.setup_commands(); env['FAIL_HEALTH'] = '1'
        result = self.run_script('alvos/tsuru/scripts/alvo.sh', 'saude', 'staging', env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.log.read_text().splitlines(), ['health', 'health'])


if __name__ == '__main__': unittest.main()
