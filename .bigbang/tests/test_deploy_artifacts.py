"""Package and static deploy artifacts are immutable SHA-256 manifests (#179)."""
import json
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import unittest

import test_deploy_catalog
from bb import artifacts, generator
from bb.errors import BbError


class FormatosDeArtefato(unittest.TestCase):
    setUp = test_deploy_catalog.CatalogoDeploy.setUp
    tearDown = test_deploy_catalog.CatalogoDeploy.tearDown
    select = test_deploy_catalog.CatalogoDeploy.select

    def configure_custom(self, artifact):
        self.select("personalizado", artifact)
        target = self.root / ".bigbang/esteira/perfis/deploy/alvos/personalizado/alvo.toml"
        target.write_text(target.read_text(encoding="utf-8").replace(
            'artefatos = ["imagem"]', 'artefatos = ["imagem", "pacote", "estatico"]'), encoding="utf-8")
        lines = []
        for operation in ("publicar", "migrar", "saude", "voltar"):
            path = f"scripts/deploy/{operation}.sh"
            script = self.root / path
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            lines.append(f'script_{operation} = "{path}"')
        lines.append('variaveis_personalizado = ["CUSTOM_APP"]')
        config_path = self.root / "bigbang.toml"
        config_path.write_text(config_path.read_text(encoding="utf-8").replace(
            "[deploy]", "[deploy]\n" + "\n".join(lines) + "\n", 1), encoding="utf-8")

    def test_package_manifest_pins_payload_and_source_file_by_sha256(self):
        (self.root / "release").mkdir()
        payload = b"package-v1\n"
        (self.root / "release/app.zip").write_bytes(payload)
        result = artifacts.build(self.root, "pacote", ["release/app.zip"], self.root / "candidata")

        manifest = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual(manifest["formato"], "pacote")
        self.assertEqual(manifest["arquivos"], [{
            "caminho": "release/app.zip",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "tamanho": len(payload),
        }])
        self.assertEqual(manifest["artefato"]["sha256"], hashlib.sha256(
            (self.root / "candidata/artefato.tar.gz").read_bytes()).hexdigest())
        self.assertEqual(artifacts.verify(result)["formato"], "pacote")

    def test_static_manifest_contains_all_files_in_deterministic_order(self):
        (self.root / "dist/nested").mkdir(parents=True)
        (self.root / "dist/z.js").write_text("z\n", encoding="utf-8")
        (self.root / "dist/nested/a.css").write_text("a\n", encoding="utf-8")

        first = artifacts.build(self.root, "estatico", ["dist/**"], self.root / "candidate-a")
        second = artifacts.build(self.root, "estatico", ["dist/**"], self.root / "candidate-b")

        manifest = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual([entry["caminho"] for entry in manifest["arquivos"]],
                         ["dist/nested/a.css", "dist/z.js"])
        self.assertEqual((self.root / "candidate-a/artefato.tar.gz").read_bytes(),
                         (self.root / "candidate-b/artefato.tar.gz").read_bytes())
        self.assertEqual(artifacts.verify(second)["formato"], "estatico")

    def test_manifest_and_archive_tampering_are_rejected(self):
        (self.root / "release").mkdir()
        (self.root / "release/app.zip").write_bytes(b"package-v1")
        manifest_path = artifacts.build(self.root, "pacote", ["release/app.zip"], self.root / "candidata")
        archive = self.root / "candidata/artefato.tar.gz"
        archive.write_bytes(archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(BbError, "SHA-256"):
            artifacts.verify(manifest_path)

    def test_unsafe_paths_and_symlinks_are_rejected(self):
        (self.root / "release").mkdir()
        external = self.root.parent / "outside.bin"
        external.write_bytes(b"outside")
        (self.root / "release/link.bin").symlink_to(external)
        for pattern in ("../outside.bin", "release/link.bin"):
            with self.subTest(pattern=pattern), self.assertRaises(BbError):
                artifacts.build(self.root, "estatico", [pattern], self.root / "candidata")

    def test_manifest_and_archive_path_traversal_are_rejected(self):
        (self.root / "release").mkdir()
        (self.root / "release/app.zip").write_bytes(b"package")
        manifest_path = artifacts.build(self.root, "pacote", ["release/app.zip"], self.root / "candidata")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["arquivos"][0]["caminho"] = "../outside.zip"
        encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        manifest_path.write_bytes(encoded)
        (manifest_path.parent / "manifesto.sha256").write_text(
            f"{hashlib.sha256(encoded).hexdigest()}  manifesto.json\n", encoding="ascii")
        with self.assertRaisesRegex(BbError, "caminho inseguro"):
            artifacts.verify(manifest_path)

        manifest_path = artifacts.build(self.root, "pacote", ["release/app.zip"], self.root / "candidata")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive_path = manifest_path.parent / "artefato.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            payload = b"outside"
            member = tarfile.TarInfo("../outside.zip")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        manifest["artefato"]["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        manifest["artefato"]["tamanho"] = archive_path.stat().st_size
        encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        manifest_path.write_bytes(encoded)
        (manifest_path.parent / "manifesto.sha256").write_text(
            f"{hashlib.sha256(encoded).hexdigest()}  manifesto.json\n", encoding="ascii")
        with self.assertRaisesRegex(BbError, "caminho inseguro"):
            artifacts.verify(manifest_path)

    def test_custom_target_verifies_and_passes_package_manifest_without_secrets(self):
        self.configure_custom("estatico")
        (self.root / "dist").mkdir()
        (self.root / "dist/app.js").write_text("console.log('ok')\n", encoding="utf-8")
        manifest = artifacts.build(self.root, "estatico", ["dist/**"], self.root / "candidata")
        script = self.root / "scripts/deploy/publicar.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'token=%s secret=%s app=%s path=%s\\n' \"${GH_TOKEN-unset}\" "
            "\"${CUSTOM_TOKEN-unset}\" \"${CUSTOM_APP-unset}\" \"$2\" > result\n"
            "cat \"$2\" >> result\n", encoding="utf-8")
        env = dict(os.environ, BB=f"{sys.executable} .bigbang/bin/bb.py", GH_TOKEN="sentinel-gh",
                   GITHUB_TOKEN="sentinel-github", CUSTOM_TOKEN="sentinel-custom", CUSTOM_APP="app-public")
        result = subprocess.run(
            ["bash", ".bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh",
             "publicar", "staging", str(manifest)], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        recorded = (self.root / "result").read_text(encoding="utf-8")
        self.assertIn("token=unset secret=unset app=app-public", recorded)
        self.assertIn('"formato":"estatico"', recorded)

    def test_candidate_build_runs_project_command_without_any_secret_environment(self):
        self.configure_custom("pacote")
        config_path = self.root / "bigbang.toml"
        text = config_path.read_text(encoding="utf-8").replace(
            'caminhos_artefato = ["src/", "migrations/", "Dockerfile", "package.json", "package-lock.json"]',
            'caminhos_artefato = ["dist/*.zip"]')
        text = text.replace('build = "npm run build"',
                            'build = "env | sort > build-env; mkdir -p dist; printf package > dist/app.zip"')
        config_path.write_text(text, encoding="utf-8")
        env = dict(os.environ, BB=f"{sys.executable} .bigbang/bin/bb.py", GH_TOKEN="gh-secret",
                   GITHUB_TOKEN="github-secret", ACTIONS_RUNTIME_TOKEN="runtime-secret",
                   AWS_SECRET_ACCESS_KEY="aws-secret", CUSTOM_TOKEN="project-secret")
        result = subprocess.run(
            ["bash", ".bigbang/esteira/perfis/deploy/scripts/candidata-arquivos.sh"],
            cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        visible_environment = (self.root / "build-env").read_text(encoding="utf-8")
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "AWS_SECRET_ACCESS_KEY", "CUSTOM_TOKEN"):
            with self.subTest(variable=name):
                self.assertNotIn(f"{name}=", visible_environment)
        self.assertEqual(artifacts.verify(self.root / "candidata/manifesto.json")["formato"], "pacote")

    def test_hashed_format_build_command_can_create_its_selected_output(self):
        self.configure_custom("pacote")
        config_path = self.root / "bigbang.toml"
        text = config_path.read_text(encoding="utf-8").replace(
            'caminhos_artefato = ["src/", "migrations/", "Dockerfile", "package.json", "package-lock.json"]',
            'caminhos_artefato = ["dist/*.zip"]')
        text = text.replace('build = "npm run build"',
                            'build = "mkdir -p dist; printf package > dist/app.zip"')
        config_path.write_text(text, encoding="utf-8")
        result = subprocess.run(
            ["bash", ".bigbang/esteira/nucleo/scripts/comando.sh", "build"], cwd=self.root,
            env=dict(os.environ, BB=f"{sys.executable} .bigbang/bin/bb.py"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "dist/app.zip").read_bytes(), b"package")

    def test_staging_refuses_manifest_that_differs_from_candidate_identity(self):
        self.configure_custom("estatico")
        (self.root / "dist").mkdir()
        (self.root / "dist/app.js").write_text("console.log('ok')\n", encoding="utf-8")
        config_path = self.root / "bigbang.toml"
        config_path.write_text(config_path.read_text(encoding="utf-8").replace(
            'smoke = "npm run test:smoke"', 'smoke = "true"'), encoding="utf-8")
        artifacts.build(self.root, "estatico", ["dist/**"], self.root / "candidata")
        fake_docker = self.root / "fake-bin/docker"
        fake_docker.parent.mkdir(parents=True, exist_ok=True)
        fake_docker.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_docker.chmod(0o755)
        result = subprocess.run(
            ["bash", ".bigbang/esteira/perfis/deploy/scripts/staging.sh"], cwd=self.root,
            env=dict(os.environ, BB=f"{sys.executable} .bigbang/bin/bb.py", IMAGEM="sha256:" + "0" * 64,
                     PATH=f"{fake_docker.parent}:{os.environ['PATH']}"),
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("identidade da candidata diverge", result.stderr + result.stdout)
        self.assertFalse((self.root / "result").exists())

    def test_catalog_and_workflows_enable_package_and_static_for_custom_target(self):
        self.configure_custom("pacote")
        for name, description in (("pacote", "Pacote"), ("estatico", "Arquivos")):
            folder = self.root / f".bigbang/esteira/perfis/deploy/artefatos/{name}"
            (folder / "artefato.toml").write_text(
                f'descricao = "{description} imutável por SHA-256"\n'
                'situacao = "implementado"\nidentidade = "sha256"\n\n'
                '[scripts]\nconstruir = "esteira/perfis/deploy/scripts/candidata-arquivos.sh"\n'
                'candidata = "esteira/perfis/deploy/scripts/candidata-publicar.sh"\n'
                'promover = "esteira/perfis/deploy/scripts/publicar-personalizado.sh"\n', encoding="utf-8")
        plan = generator.build_plan(self.root, install_pipeline=True)
        candidate = plan.expected[".github/workflows/bb-candidata.yml"]
        self.assertIn("actions/upload-artifact@", candidate)
        self.assertIn("actions/download-artifact@", candidate)
        self.assertIn("candidata-arquivos.sh", candidate)
        test_step = candidate.split("Validar testes", 1)[1].split("\n      - name:", 1)[0]
        self.assertNotIn("GH_TOKEN", test_step)
        build_step = candidate.split("Construir", 1)[1].split("\n      - name:", 1)[0]
        self.assertNotIn("GH_TOKEN", build_step)
        production = plan.expected[".github/workflows/bb-publicar-producao.yml"]
        custom_step = production.split("Executar scripts personalizados sem credenciais", 1)[1].split(
            "- name: Finalizar publicação personalizada", 1)[0]
        self.assertNotIn("GH_TOKEN", custom_step)
        self.assertNotIn("GITHUB_TOKEN", custom_step)
        self.assertNotIn("secrets.", custom_step)
        self.assertIn("MANIFESTO: ${{ steps.preparar-publicacao.outputs.manifesto }}", custom_step)
        self.assertIn("publicar-personalizado.sh", custom_step)
        publish = candidate.split("Pre-release com os digests", 1)[1].split("homologar:", 1)[0]
        self.assertIn("IMAGEM: ${{ needs.imagem.outputs.imagem }}", publish)
        rollback = plan.expected[".github/workflows/bb-voltar-versao.yml"]
        rollback_script = rollback.split("Voltar versão pelo alvo personalizado sem credenciais", 1)[1].split(
            "- name:", 1)[0]
        self.assertNotIn("GH_TOKEN", rollback_script)
        self.assertNotIn("secrets.", rollback_script)


if __name__ == "__main__":
    unittest.main()
