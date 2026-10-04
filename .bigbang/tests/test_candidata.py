"""Compiled profile candidate (spec 14.3): prepare, build, publish and homologation."""
import os
import subprocess
import sys
import unittest

from _raiz import BIGBANG
from _scripts import SCRIPTS, CasoDeScript
from test_integrar_publicar import ComGit

BB = os.path.join(BIGBANG, "bin", "bb.py")
COMPILADO = os.path.join(BIGBANG, "esteira", "perfis", "compilado", "scripts")


class BaseCompilado(ComGit):
    def setUp(self):
        super().setUp()
        toml = os.path.join(self.trabalho, "bigbang.toml")
        with open(toml, encoding="utf-8") as arquivo:
            texto = arquivo.read()
        texto = (texto.replace('perfil = "deploy"', 'perfil = "compilado"').replace('alvo = "vps-docker"', 'alvo = ""')
                 .replace('build_linux-x64 = "bash packaging/linux/build.sh"',
                          'build_linux-x64 = "printf binario-$BB_VERSAO-rc$BB_RC > $BB_SAIDA/app"'))
        with open(toml, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        self.commit("chore: compiled profile")
        self.git("push", "-q", "origin", "main")
        self.git("push", "-q", "origin", "main:develop")

    def compilado(self, script, **env):
        pasta = SCRIPTS if script == "candidata-preparar.sh" else COMPILADO
        return self.rodar(script, env={"BB": self.bb, **{k: str(v) for k, v in env.items()}}, pasta=pasta,
                          cwd=self.trabalho)

    def release(self, versao="0.2.0", changelog=True):
        self.git("checkout", "-q", "-b", f"release/{versao}")
        self.escrever("package.json", f'{{\n  "name": "x",\n  "version": "{versao}"\n}}\n')
        if changelog:
            self.escrever("CHANGELOG.md", f"# Changelog\n\n## [Não publicado]\n\n## [{versao}] - 2026-10-04\n\n- x\n")
        self.commit("chore(release): v" + versao)
        self.git("push", "-q", "origin", f"release/{versao}")



class ProjetoCompilado(BaseCompilado):
    def test_preparar_numera_as_candidatas(self):
        self.release()
        r = self.compilado("candidata-preparar.sh", GITHUB_REF_NAME="release/0.2.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("tag=v0.2.0-rc.1", r.stdout)
        self.git("tag", "v0.2.0-rc.1")
        self.git("push", "-q", "origin", "v0.2.0-rc.1")
        self.assertIn("tag=v0.2.0-rc.2", self.compilado("candidata-preparar.sh", GITHUB_REF_NAME="release/0.2.0").stdout)

    def test_preparar_pula_ou_recusa(self):
        self.release(changelog=False)
        self.assertIn("pular=true", self.compilado("candidata-preparar.sh", GITHUB_REF_NAME="release/0.2.0").stdout)
        self.git("tag", "v0.2.0")
        self.git("push", "-q", "origin", "v0.2.0")
        self.assertEqual(self.compilado("candidata-preparar.sh", GITHUB_REF_NAME="release/0.2.0").returncode, 1)

    def test_build_renomeia_e_soma(self):
        r = self.compilado("candidata-build.sh", BB_SISTEMA="linux-x64", BB_VERSAO="0.2.0", BB_RC="3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pasta = os.path.join(self.trabalho, "candidata")
        self.assertEqual(sorted(os.listdir(pasta)), ["SHA256SUMS-linux-x64.txt", "meu-sistema-v0.2.0-rc.3-linux-x64"])
        self.assertEqual(subprocess.run(["sha256sum", "-c", "SHA256SUMS-linux-x64.txt"], cwd=pasta,
                                        capture_output=True).returncode, 0)

    def test_build_com_dois_arquivos_falha(self):
        toml = os.path.join(self.trabalho, "bigbang.toml")
        with open(toml, encoding="utf-8") as arquivo:
            texto = arquivo.read().replace('> $BB_SAIDA/app"', '> $BB_SAIDA/app; touch $BB_SAIDA/extra"')
        with open(toml, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        r = self.compilado("candidata-build.sh", BB_SISTEMA="linux-x64", BB_VERSAO="0.2.0", BB_RC="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("exatamente um arquivo", r.stdout)

    def test_publicar_cria_pre_release(self):
        self.compilado("candidata-build.sh", BB_SISTEMA="linux-x64", BB_VERSAO="0.2.0", BB_RC="1")
        r = self.compilado("candidata-publicar.sh", TAG="v0.2.0-rc.1", GITHUB_SHA="abc123")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(self.estado["release_assets"]["v0.2.0-rc.1"]),
                         ["SHA256SUMS-linux-x64.txt", "meu-sistema-v0.2.0-rc.1-linux-x64"])
        self.assertEqual(self.estado["release_info"]["v0.2.0-rc.1"], {"prerelease": True, "latest": False,
                                                                      "target": "abc123"})


class Homologar(CasoDeScript):
    def test_epico_em_homologacao_e_pr_da_release(self):
        self.estado["milestones"] = [{"number": 1, "title": "v0.2.0", "state": "open"}]
        self.gravar_estado()
        self.issue(7, "Estoque", labels=["epic", "reprovado"], milestone="v0.2.0",
                   corpo="### Critérios de aceite\n\n- CA-1: Dado x, quando y, então z.")
        self.issue(12, "Regra", labels=["task"], milestone="v0.2.0")
        self.cartao(1, 7, "Em desenvolvimento")
        env = {"BRANCH": "release/0.2.0", "RC_TAG": "v0.2.0-rc.2"}
        r = self.rodar("homologar.sh", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status(1, 7), "Homologação")
        self.assertNotIn("reprovado", self.estado["issues"]["7"]["labels"])
        prs = [p for p in self.estado["prs"].values() if p["head"] == "release/0.2.0"]
        self.assertEqual([(p["base"], p["title"]) for p in prs], [("main", "chore(release): v0.2.0")])
        self.rodar("homologar.sh", env=env)  # idempotent: one PR only
        self.assertEqual(len([p for p in self.estado["prs"].values() if p["head"] == "release/0.2.0"]), 1)


if __name__ == "__main__":
    unittest.main()
