"""Deploy profile scripts: the candidate pre-release records the digest; production promotes that same digest,
migrating before the switch; a failed health check is an alert, not a stop."""
import os
import shutil
import stat
import sys
import unittest

from _raiz import BIGBANG, exemplo_toml
from _scripts import CasoDeScript

DEPLOY = os.path.join(BIGBANG, "esteira", "perfis", "deploy", "scripts")
BB = os.path.join(BIGBANG, "bin", "bb.py")
IMAGEM = "ghcr.io/brunodossantosvaz/meu-sistema@sha256:" + "b" * 64
SSH_FALSO = """#!/usr/bin/env bash
printf '%s\\n' "$(basename "$0") $*" >> "$SSH_LOG"
[ "$(basename "$0")" = ssh ] && cat >> "$SSH_LOG"
exit 0
"""


class Deploy(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.projeto = os.path.join(self.pasta, "projeto")
        os.makedirs(os.path.join(self.projeto, ".bigbang", "esteira", "perfis", "deploy"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(self.projeto, ".bigbang", "VERSION"))
        shutil.copytree(os.path.join(BIGBANG, "esteira", "perfis", "deploy", "alvos"),
                        os.path.join(self.projeto, ".bigbang", "esteira", "perfis", "deploy", "alvos"))
        with open(os.path.join(self.projeto, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(exemplo_toml())
        os.makedirs(os.path.join(self.projeto, "deploy"))
        with open(os.path.join(self.projeto, "deploy", "compose.yaml"), "w", encoding="utf-8") as arquivo:
            arquivo.write("services: {}\n")
        for nome in ("ssh", "scp"):
            caminho = os.path.join(self.bin, nome)
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write(SSH_FALSO)
            os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IXUSR)
        self.ssh_log = os.path.join(self.pasta, "ssh.log")
        self.env = {"BB": f"{sys.executable} {BB} --raiz {self.projeto}", "SSH_LOG": self.ssh_log,
                    "VPS_HOST": "vps.exemplo", "VPS_USUARIO": "deploy", "VPS_CHAVE_SSH": "CHAVE",
                    "VPS_KNOWN_HOSTS": "vps.exemplo ssh-ed25519 AAAA", "SAUDE_URL": "http://127.0.0.1:9",
                    "SAUDE_TENTATIVAS": "1", "SAUDE_INTERVALO": "0"}

    def deploy(self, script, **env):
        return self.rodar(script, env={**self.env, **env}, pasta=DEPLOY, cwd=self.projeto)

    def ssh(self):
        with open(self.ssh_log, encoding="utf-8") as arquivo:
            return arquivo.read()

    def test_pre_release_registra_o_digest(self):
        os.makedirs(os.path.join(self.projeto, "candidata"))
        with open(os.path.join(self.projeto, "candidata", "imagem.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(IMAGEM + "\n")
        r = self.deploy("candidata-publicar.sh", TAG="v1.0.0-rc.1", IMAGEM=IMAGEM, GITHUB_SHA="abc")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.estado["release_assets"]["v1.0.0-rc.1"], ["imagem.txt"])
        self.assertTrue(self.estado["release_info"]["v1.0.0-rc.1"]["prerelease"])

    def test_pre_release_recusa_tag_sem_digest(self):
        os.makedirs(os.path.join(self.projeto, "candidata"))
        r = self.deploy("candidata-publicar.sh", TAG="v1.0.0-rc.1", IMAGEM="ghcr.io/x/y:latest", GITHUB_SHA="abc")
        self.assertEqual(r.returncode, 1)

    def test_promove_o_mesmo_digest_migrando_antes(self):
        rc = os.path.join(self.pasta, "rc")
        os.makedirs(rc)
        with open(os.path.join(rc, "imagem.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(IMAGEM + "\n")
        self.estado["release_dirs"] = {"v1.0.0-rc.2": rc}
        self.gravar_estado()
        r = self.deploy("promover.sh", RC_TAG="v1.0.0-rc.2", TAG="v1.0.0", TARGET_SHA="abc")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = self.ssh()
        self.assertIn(f"BB_IMAGEM_APP={IMAGEM}", log)
        migracao = log.index("--profile migrar run --rm -T migrar")
        publicacao = log.index("up -d --remove-orphans app")
        self.assertLess(migracao, publicacao)  # migration with the new image before the switch
        self.assertIn("produção não respondeu ao health check", r.stderr + r.stdout)  # alert, not a stop
        self.assertEqual(self.estado["release_assets"]["v1.0.0"], ["imagem.txt"])
        self.assertTrue(self.estado["release_info"]["v1.0.0"]["latest"])
        with open(os.path.join(self.estado["release_dirs"]["v1.0.0"], "imagem.txt"), encoding="utf-8") as arquivo:
            self.assertEqual(arquivo.read().strip(), IMAGEM)  # Voltar versão finds this digest later

    def test_candidata_sem_digest_nao_publica(self):
        rc = os.path.join(self.pasta, "rc")
        os.makedirs(rc)
        with open(os.path.join(rc, "imagem.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write("ghcr.io/x/y:1.0\n")
        self.estado["release_dirs"] = {"v1.0.0-rc.2": rc}
        self.gravar_estado()
        r = self.deploy("promover.sh", RC_TAG="v1.0.0-rc.2", TAG="v1.0.0", TARGET_SHA="abc")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("v1.0.0", self.estado.get("releases", []))


if __name__ == "__main__":
    unittest.main()
