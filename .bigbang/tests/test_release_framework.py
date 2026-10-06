"""Framework release gates use checkout refs without requiring persisted Git credentials."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from _raiz import ler


class FrameworkReleaseGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Release test')
        self.git('config', 'user.email', 'release@example.invalid')
        (self.root / '.bigbang').mkdir()
        (self.root / '.bigbang/VERSION').write_text('1.5.0\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'release')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', self.sha)
        # Checkout fetched all refs, then removed credentials. Any later fetch must fail here.
        self.git('remote', 'add', 'origin', str(self.root / 'unavailable-remote.git'))

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True,
                              text=True, check=True).stdout.strip()

    def gate(self, sha=None, tag='v1.5.0'):
        workflow = ler('.github/workflows/bb-framework-release.yml')
        step = workflow.split('      - name: A tag esta na main e bate com .bigbang/VERSION\n', 1)[1]
        block = step.split('        run: |\n', 1)[1].split('      - name:', 1)[0]
        commands = '\n'.join(line[10:] for line in block.splitlines() if line.startswith('          '))
        return subprocess.run(['bash', '-euo', 'pipefail', '-c', commands], cwd=self.root,
                              env={**os.environ, 'GITHUB_SHA': sha or self.sha, 'TAG': tag},
                              capture_output=True, text=True)

    def test_uses_checkout_refs_with_git_remote_unavailable(self):
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_refuses_tag_version_different_from_framework(self):
        result = self.gate(tag='v1.4.0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('nao bate com .bigbang/VERSION', result.stdout)

    def test_refuses_commit_outside_main(self):
        self.git('checkout', '-qb', 'outside-main')
        (self.root / 'outside').write_text('outside\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'outside main')
        result = self.gate(sha=self.git('rev-parse', 'HEAD'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('nao esta na main', result.stdout)


if __name__ == '__main__':
    unittest.main()
