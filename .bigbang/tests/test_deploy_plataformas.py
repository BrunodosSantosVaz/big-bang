"""Bug #195: scan every service/platform at the immutable index digest, regardless of runner architecture."""
import json
from pathlib import Path
import sys
import unittest

from _scripts import CasoDeScript
from test_deploy import DEPLOY, IMAGEM


class Plataformas(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.projeto = Path(self.pasta) / "projeto"
        self.projeto.mkdir()
        (self.projeto / "Dockerfile").write_text("FROM scratch\n")
        self.scan_log = Path(self.pasta) / "trivy.jsonl"
        ferramentas = Path(self.pasta) / "bb-trivy"
        ferramentas.mkdir()
        self.executavel(ferramentas / "trivy", '''import json, os, sys
a = sys.argv[1:]
with open(os.environ['SCAN_LOG'], 'a') as f: f.write(json.dumps(a) + '\\n')
p = a[a.index('--platform') + 1] if '--platform' in a else 'linux/amd64'
if p not in os.environ['PLATFORMS'].splitlines() or p == os.environ.get('FAIL_PLATFORM'): sys.exit(7)
if '--output' in a:
    with open(a[a.index('--output') + 1], 'w') as f: json.dump({'platform': p, 'image': a[-1]}, f)
''')
        self.executavel(Path(self.bin) / "config", '''import os, sys
k = sys.argv[-1]
if k == os.environ.get('FAIL_CONFIG'): sys.exit(9)
print({'deploy.imagem': 'ghcr.io/dono/app', 'deploy.servicos': os.environ['SERVICES'],
       'deploy.plataformas': os.environ['PLATFORMS']}[k])
''')
        self.executavel(Path(self.bin) / "docker", '''import json, sys
a = sys.argv[1:]
with open(a[a.index('--metadata-file') + 1], 'w') as f:
    json.dump({'containerimage.digest': 'sha256:' + 'b' * 64}, f)
''')
        self.env = {"BB": str(Path(self.bin) / "config"), "RUNNER_TEMP": self.pasta,
                    "SCAN_LOG": str(self.scan_log), "PLATFORMS": "linux/arm64", "SERVICES": "app=Dockerfile",
                    "TAG": "v1.0.0-rc.1", "IMAGEM": IMAGEM}

    def executavel(self, path, body):
        path.write_text(f"#!{sys.executable}\n" + body)
        path.chmod(0o755)

    def rodar_deploy(self, script, **env):
        return self.rodar(script, pasta=DEPLOY, cwd=self.projeto, env={**self.env, **env})

    def scans(self):
        return [json.loads(line) for line in self.scan_log.read_text().splitlines()] if self.scan_log.exists() else []

    def assert_scans(self, expected):
        actual = [(a[-1], a[a.index('--platform') + 1] if '--platform' in a else None) for a in self.scans()]
        self.assertEqual(actual, expected)

    def test_sbom_arm64_no_runner_amd64_preserva_digest(self):
        r = self.rodar_deploy("candidata-sbom.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_scans([(IMAGEM, "linux/arm64")])
        self.assertEqual((self.projeto / "candidata/imagem.txt").read_text(), IMAGEM + "\n")
        self.assertEqual((self.projeto / "candidata/imagens.sha256").read_text(), "b" * 64 + "  " + IMAGEM.split('@')[0] + "\n")
        self.assertEqual(json.loads((self.projeto / "candidata/sbom-app.json").read_text())["platform"], "linux/arm64")

    def test_sbom_matriz_sem_colisao_com_nome_de_servico(self):
        refs = {s: f"ghcr.io/dono/{s}@sha256:" + "b" * 64 for s in ("api", "api-linux-arm64")}
        r = self.rodar_deploy("candidata-sbom.sh", IMAGEM=','.join(f"{s}={ref}" for s, ref in refs.items()),
                             PLATFORMS="linux/amd64\nlinux/arm64")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_scans([(ref, p) for ref in refs.values() for p in ("linux/amd64", "linux/arm64")])
        for s, ref in refs.items():
            for p in ("linux-amd64", "linux-arm64"):
                self.assertEqual(json.loads((self.projeto / f"candidata/sbom-{s}.{p}.json").read_text())["image"], ref)
            self.assertEqual(json.loads((self.projeto / f"candidata/sbom-{s}.json").read_text())["platform"], "linux/amd64")
        self.assertEqual((self.projeto / "candidata/imagem.txt").read_text().splitlines(),
                         [f"{s}={ref}" for s, ref in refs.items()])

    def test_vulnerabilidades_cada_servico_e_plataforma(self):
        r = self.rodar_deploy("candidata-imagem.sh", SERVICES="api=Dockerfile\nworker=Dockerfile",
                             PLATFORMS="linux/amd64\nlinux/arm64")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        expected = [(f"ghcr.io/dono/app-{s}@sha256:" + "b" * 64, p)
                    for s in ("api", "worker") for p in ("linux/amd64", "linux/arm64")]
        self.assert_scans(expected)
        for a in self.scans():
            self.assertEqual(a[a.index('--severity') + 1], "HIGH,CRITICAL")
            self.assertEqual(a[a.index('--exit-code') + 1], "1")
            self.assertEqual(a[a.index('--scanners') + 1], "vuln")
        self.assertEqual((self.projeto / "imagem.txt").read_text().splitlines(),
                         [f"{s}=ghcr.io/dono/app-{s}@sha256:" + "b" * 64 for s in ("api", "worker")])

    def test_segunda_plataforma_falha_fecha_ambas_etapas(self):
        for script in ("candidata-imagem.sh", "candidata-sbom.sh"):
            with self.subTest(script=script):
                self.scan_log.unlink(missing_ok=True)
                r = self.rodar_deploy(script, PLATFORMS="linux/amd64\nlinux/arm64", FAIL_PLATFORM="linux/arm64")
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(len(self.scans()), 2)

    def test_config_inacessivel_nao_pula_varreduras(self):
        for script in ("candidata-imagem.sh", "candidata-sbom.sh"):
            with self.subTest(script=script):
                r = self.rodar_deploy(script, FAIL_CONFIG="deploy.plataformas")
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.scans(), [])

    def test_lista_vazia_nao_pula_varreduras(self):
        for script in ("candidata-imagem.sh", "candidata-sbom.sh"):
            with self.subTest(script=script):
                r = self.rodar_deploy(script, PLATFORMS="")
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.scans(), [])


if __name__ == "__main__":
    unittest.main()
