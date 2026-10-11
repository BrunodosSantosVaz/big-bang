"""Project-owned deployment scripts receive only the immutable artifact manifest."""
import os
import subprocess
import sys
import unittest

import test_deploy_catalog
from bb import generator
from bb.errors import BbError


IMAGE = "ghcr.io/owner/app@sha256:" + "a" * 64
MANIFEST = "app=" + IMAGE
SCRIPT_KEYS = {
    "publicar": "script_publicar",
    "migrar": "script_migrar",
    "saude": "script_saude",
    "voltar": "script_voltar",
}


class AlvoPersonalizado(unittest.TestCase):
    setUp = test_deploy_catalog.CatalogoDeploy.setUp
    tearDown = test_deploy_catalog.CatalogoDeploy.tearDown
    select = test_deploy_catalog.CatalogoDeploy.select

    def configure_custom(self, missing=None):
        self.select("personalizado")
        lines = []
        for operation, key in SCRIPT_KEYS.items():
            path = f"scripts/deploy/{operation}.sh"
            if operation != missing:
                script = self.root / path
                script.parent.mkdir(parents=True, exist_ok=True)
                script.write_text(
                    "#!/usr/bin/env bash\n"
                    "set -euo pipefail\n"
                    f"printf '{operation}:%s\\n' \"$1\" >> \"$LOG\"\n"
                    "if [ \"$#\" -gt 1 ]; then cat \"$2\" >> \"$MANIFEST_LOG\"; fi\n"
                    f"[ \"${{FAIL_OPERATION:-}}\" != {operation} ]\n",
                    encoding="utf-8",
                )
            lines.append(f'{key} = "{path}"')
        lines.extend([
            'variaveis_personalizado = ["CUSTOM_APP"]',
            'segredos_personalizado = ["CUSTOM_TOKEN"]',
        ])
        path = self.root / "bigbang.toml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("[deploy]", "[deploy]\n" + "\n".join(lines) + "\n", 1),
                        encoding="utf-8")

    def runner_environment(self, **extra):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        docker = fake_bin / "docker"
        docker.write_text('#!/usr/bin/env bash\necho zap >> "$LOG"\n', encoding="utf-8")
        docker.chmod(0o755)
        values = {
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "BB": f"{sys.executable} .bigbang/bin/bb.py",
            "GITHUB_REPOSITORY": "owner/repo",
            "IMAGEM": MANIFEST,
            "LOG": str(self.root / "calls"),
            "MANIFEST_LOG": str(self.root / "manifests"),
        }
        values.update(extra)
        return dict(os.environ, **values)

    def run_deploy_script(self, path, *args, env):
        return subprocess.run(
            ["bash", ".bigbang/esteira/perfis/deploy/" + path, *args],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_custom_scripts_are_required_before_generation(self):
        self.configure_custom(missing="voltar")
        with self.assertRaisesRegex(BbError, "voltar"):
            generator.build_plan(self.root, install_pipeline=True)

    def test_custom_script_paths_cannot_escape_project_or_enter_bigbang(self):
        for invalid in ("../outside.sh", ".bigbang/bin/bb.py"):
            with self.subTest(path=invalid):
                self.configure_custom()
                path = self.root / "bigbang.toml"
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace("scripts/deploy/voltar.sh", invalid), encoding="utf-8")
                with self.assertRaisesRegex(BbError, "script|caminho|arquivo|fora"):
                    generator.build_plan(self.root, install_pipeline=True)

    def test_custom_script_symlink_cannot_escape_project(self):
        self.configure_custom()
        script = self.root / "scripts/deploy/voltar.sh"
        script.unlink()
        external = self.root.parent / "outside.sh"
        external.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.symlink_to(external)
        with self.assertRaisesRegex(BbError, "fora dos scripts do projeto"):
            generator.build_plan(self.root, install_pipeline=True)

    def test_custom_target_is_generated_with_only_declared_credentials(self):
        self.configure_custom()
        plan = generator.build_plan(self.root, install_pipeline=True)
        workflows = "\n".join(
            plan.expected[f".github/workflows/{name}"]
            for name in ("bb-candidata.yml", "bb-publicar-producao.yml", "bb-voltar-versao.yml")
        )
        self.assertIn("CUSTOM_APP: ${{ vars.CUSTOM_APP }}", workflows)
        self.assertIn("CUSTOM_TOKEN: ${{ secrets.CUSTOM_TOKEN }}", workflows)
        self.assertNotIn("VPS_HOST", workflows)
        self.assertNotIn("VPS_CHAVE_SSH", workflows)

    def test_staging_runs_migration_before_publish_and_health(self):
        self.configure_custom()
        path = self.root / "bigbang.toml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('smoke = "npm run test:smoke"',
                                     'smoke = "echo smoke >> \\"$LOG\\""'), encoding="utf-8")
        result = self.run_deploy_script("scripts/staging.sh", env=self.runner_environment())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / "calls").read_text(encoding="utf-8").splitlines(),
            ["migrar:staging", "publicar:staging", "saude:staging", "smoke", "zap"],
        )
        self.assertEqual((self.root / "manifests").read_text(encoding="utf-8"), (MANIFEST + "\n") * 2)

    def test_migration_failure_stops_staging_before_publish(self):
        self.configure_custom()
        result = self.run_deploy_script(
            "scripts/staging.sh", env=self.runner_environment(FAIL_OPERATION="migrar")
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / "calls").read_text(encoding="utf-8").splitlines(), ["migrar:staging"])

    def test_mutable_image_reference_is_rejected_before_script_execution(self):
        self.configure_custom()
        result = self.run_deploy_script(
            "alvos/personalizado/scripts/alvo.sh",
            "migrar",
            "staging",
            "app=ghcr.io/owner/app:latest",
            env=self.runner_environment(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "calls").exists())

    def test_rollback_uses_release_manifest_and_never_runs_migration(self):
        self.configure_custom()
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        gh = fake_bin / "gh"
        gh.write_text(
            "#!/usr/bin/env bash\n"
            "output=''\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = --output ]; then output=\"$2\"; shift 2; else shift; fi\n"
            "done\n"
            "printf '%s\\n' 'app=" + IMAGE + "' > \"$output\"\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = self.runner_environment()
        path = ".bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh"
        rollback = subprocess.run(
            ["bash", path, "voltar", "producao", "v1.2.3"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        health = subprocess.run(["bash", path, "saude", "producao"], cwd=self.root, env=env,
                                capture_output=True, text=True)
        self.assertEqual(health.returncode, 0, health.stderr)
        self.assertEqual((self.root / "calls").read_text(encoding="utf-8").splitlines(),
                         ["voltar:producao", "saude:producao"])
        self.assertEqual((self.root / "manifests").read_text(encoding="utf-8"), MANIFEST + "\n")


if __name__ == "__main__":
    unittest.main()
