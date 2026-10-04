"""integrar-release.sh, devolver-main.sh, publicar-sem-release.sh, encerrar.sh and ver-paineis.sh with real git
repositories (a bare `origin` and a clone) and the fake GitHub."""
import os
import shutil
import subprocess
import sys
import unittest

from _raiz import BIGBANG, exemplo_toml
from _scripts import CasoDeScript

BB = os.path.join(BIGBANG, "bin", "bb.py")
VERDE = [{"name": "check", "status": "completed", "conclusion": "success"}]


class ComGit(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.pasta, "origin.git")
        self.trabalho = os.path.join(self.pasta, "trabalho")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.origin], check=True)
        subprocess.run(["git", "clone", "-q", self.origin, self.trabalho], check=True, capture_output=True)
        self.git("config", "user.email", "teste@example.com")
        self.git("config", "user.name", "Teste")
        os.makedirs(os.path.join(self.trabalho, ".bigbang"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(self.trabalho, ".bigbang", "VERSION"))
        self.escrever("bigbang.toml", exemplo_toml())
        self.escrever("package.json", '{\n  "name": "x",\n  "version": "0.1.0"\n}\n')
        self.escrever("src/app.js", "v1\n")
        self.escrever("CHANGELOG.md", "# Changelog\n\n## [Não publicado]\n\n## [0.1.0] - 2026-09-01\n\n- início\n")
        self.commit("chore: initial commit")
        self.git("tag", "v0.1.0")
        self.git("push", "-q", "origin", "main", "--tags")
        self.git("push", "-q", "origin", "main:develop")
        self.bb = f"{sys.executable} {BB} --raiz {self.trabalho}"

    def git(self, *args, saida=False):
        r = subprocess.run(["git", "-C", self.trabalho, *args], check=True, capture_output=True, text=True)
        return r.stdout.strip() if saida else None

    def git_origin(self, *args):
        return subprocess.run(["git", "--git-dir", self.origin, *args], capture_output=True, text=True).stdout.strip()

    def escrever(self, caminho, texto):
        destino = os.path.join(self.trabalho, caminho)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    def commit(self, mensagem):
        self.git("add", "-A")
        self.git("commit", "-qm", mensagem)

    def branch(self, nome, de, caminho, texto):
        self.git("checkout", "-q", "-B", nome, f"origin/{de}" if de != "main" else "origin/main")
        self.escrever(caminho, texto)
        self.commit(f"change {caminho}")
        self.git("push", "-q", "origin", nome)
        self.git("checkout", "-q", "main")

    def script(self, nome, **env):
        self.git("fetch", "-q", "origin")
        return self.rodar(nome, env={"BB": self.bb, **{k: str(v) for k, v in env.items()}}, cwd=self.trabalho)

    def epico(self, labels=("epic",), corpo="### Problema ou oportunidade\n\nx"):
        self.issue(7, "Estoque", labels=list(labels), corpo=corpo, sub=[11, 12, 13])
        self.issue(11, "Testes", labels=["teste-aceite"], parent=7)
        self.issue(12, "Regra de estoque", labels=["task"], parent=7)
        self.issue(13, "Documentação", labels=["documentacao"], parent=7)

    def mesclados(self, *heads, base="epico/7-estoque", titulos=None):
        prs = self.estado.setdefault("prs", {})
        for i, head in enumerate(heads):
            prs[str(300 + len(prs))] = {"head": head, "base": base, "state": "MERGED",
                                        "title": (titulos or {}).get(head, "test: testes de aceite"), "labels": []}
        self.gravar_estado()


class IntegrarRelease(ComGit):
    def preparar(self, labels=("epic",), caminho="src/app.js", texto="v2\n"):
        self.git("fetch", "-q", "origin")
        self.branch("epico/7-estoque", "develop", caminho, texto)
        self.epico(labels)
        self.mesclados("teste/11-testes", "feature/12-regra", "docs/13-documentacao",
                       titulos={"feature/12-regra": "feat(estoque): bloqueia pedido sem estoque",
                                "docs/13-documentacao": "docs: documenta o estoque"})

    def test_epico_vira_release_a_partir_da_main(self):
        self.preparar()
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("v0.2.0", r.stdout)
        arquivos = self.git_origin("show", "release/0.2.0:package.json")
        self.assertIn('"version": "0.2.0"', arquivos)
        changelog = self.git_origin("show", "release/0.2.0:CHANGELOG.md")
        self.assertIn("## [0.2.0] - ", changelog)
        self.assertIn("- Bloqueia pedido sem estoque (#", changelog)
        self.assertEqual(self.git_origin("show", "release/0.2.0:src/app.js"), "v2")
        self.assertIn("Merge épico #7", self.git_origin("log", "--format=%s", "release/0.2.0"))
        self.assertEqual(self.estado["milestones"][0]["title"], "v0.2.0")
        for n in ("7", "11", "12", "13"):
            self.assertEqual(self.estado["issues"][n]["milestone"], "v0.2.0")
        self.assertEqual(self.estado["boards"]["1"]["items"]["7"]["Versão"], "v0.2.0")
        self.assertEqual(self.git_origin("rev-parse", "develop"), self.git_origin("rev-parse", "main"))  # untouched

    def test_primeira_release_sem_nenhuma_tag(self):
        self.git("push", "-q", "origin", ":refs/tags/v0.1.0")
        self.git("tag", "-d", "v0.1.0")
        self.preparar()
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("v0.1.0 (atual: v0.0.0)", r.stdout)

    def test_versao_informada_diferente_exige_confirmacao(self):
        self.preparar()
        r = self.script("integrar-release.sh", EPICO=7, VERSAO="0.1.1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("confirmar_versao", r.stdout)
        r = self.script("integrar-release.sh", EPICO=7, VERSAO="0.1.1", CONFIRMAR_VERSAO="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.git_origin("rev-parse", "--verify", "release/0.1.1"))

    def test_epico_incompleto(self):
        self.preparar()
        self.estado["prs"] = {}
        self.mesclados("teste/11-testes")
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 1)
        self.assertIn("#12", r.stdout)

    def test_dependencia_nao_publicada(self):
        self.preparar()
        self.estado["issues"]["7"]["body"] = "### Depende de outro épico ainda não publicado?\n\n#5"
        self.issue(5, "Base", labels=["epic"])
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 1)
        self.assertIn("#5", r.stdout)
        self.issue(5, "Base", labels=["epic"], state="closed")
        self.assertEqual(self.script("integrar-release.sh", EPICO=7).returncode, 0)

    def test_epico_sem_release_vai_para_a_develop(self):
        self.preparar(labels=("epic", "sem-release"), caminho="docs/guia.md", texto="# Guia\n")
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git_origin("show", "develop:docs/guia.md"), "# Guia")
        self.assertFalse(self.git_origin("branch", "--list", "release/*"))

    def test_sem_release_que_muda_o_artefato_e_recusado(self):
        self.preparar(labels=("epic", "sem-release"))
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 1)
        self.assertIn("muda o artefato", r.stdout)

    def test_conflito_marca_o_epico(self):
        self.preparar()
        self.git("fetch", "-q", "origin")
        self.escrever("src/app.js", "versão da main\n")
        self.commit("fix: hotfix na main")
        self.git("push", "-q", "origin", "main")
        r = self.script("integrar-release.sh", EPICO=7)
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflito", self.estado["issues"]["7"]["labels"])
        self.assertFalse(self.git_origin("branch", "--list", "release/*"))

    def test_bug_sobe_o_ultimo_numero(self):
        self.git("fetch", "-q", "origin")
        self.branch("bugfix/20-total", "main", "src/app.js", "corrigido\n")
        self.issue(20, "Total errado", labels=["bug"])
        self.estado["prs"] = {"40": {"head": "bugfix/20-total", "base": "main", "state": "OPEN",
                                     "title": "fix: corrige o total", "labels": []}}
        self.gravar_estado()
        r = self.script("integrar-release.sh", BUG=20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("v0.1.1", r.stdout)
        self.assertIn("### Corrigido\n\n- Corrige o total (#40)", self.git_origin("show", "release/0.1.1:CHANGELOG.md"))

    def test_simular_nao_envia(self):
        self.preparar()
        r = self.script("integrar-release.sh", EPICO=7, SIMULAR="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[simulado]", r.stdout)
        self.assertFalse(self.git_origin("branch", "--list", "release/*"))


class DevolverMain(ComGit):
    def test_devolve_para_develop_e_epicos_e_marca_conflito(self):
        self.git("fetch", "-q", "origin")
        self.branch("epico/7-estoque", "develop", "docs/a.md", "# A\n")
        self.branch("epico/8-conflito", "develop", "src/app.js", "do épico\n")
        self.issue(7, "Estoque", labels=["epic"])
        self.issue(8, "Conflito", labels=["epic"])
        self.escrever("src/app.js", "publicado\n")
        self.commit("feat: release")
        self.git("push", "-q", "origin", "main")
        r = self.script("devolver-main.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        main = self.git_origin("rev-parse", "main")
        for branch in ("develop", "epico/7-estoque"):
            self.assertEqual(subprocess.run(["git", "--git-dir", self.origin, "merge-base", "--is-ancestor", main,
                                             branch]).returncode, 0, branch)
        self.assertIn("conflito", self.estado["issues"]["8"]["labels"])
        self.assertNotIn("conflito", self.estado["issues"]["7"]["labels"])


class DevolverDepoisDaLimpeza(ComGit):
    def test_branch_apagada_depois_do_ultimo_fetch_e_ignorada(self):
        self.git("fetch", "-q", "origin")
        self.branch("epico/7-estoque", "develop", "docs/a.md", "# A\n")
        self.git("fetch", "-q", "origin")  # the local clone still knows epico/7-estoque…
        subprocess.run(["git", "--git-dir", self.origin, "branch", "-D", "epico/7-estoque"], check=True,
                       capture_output=True)  # …that the cleanup deleted on origin
        self.escrever("src/app.js", "publicado\n")
        self.commit("feat: release")
        self.git("push", "-q", "origin", "main")
        r = self.rodar("devolver-main.sh", env={"BB": self.bb}, cwd=self.trabalho)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PublicarSemRelease(ComGit):
    def preparar(self):
        self.git("fetch", "-q", "origin")
        self.branch("epico/7-estoque", "develop", "docs/guia.md", "# Guia\n")
        self.git("fetch", "-q", "origin")
        self.git("push", "-q", "origin", "origin/epico/7-estoque:refs/heads/develop")
        self.git("fetch", "-q", "origin")
        self.epico(labels=("epic", "sem-release"))
        self.estado["checks"][self.git_origin("rev-parse", "develop")] = VERDE
        self.estado["refs"]["heads/epico/7-estoque"] = "x"
        self.mesclados("teste/11-testes")
        for n in (11, 12, 13):
            self.cartao(2, n, "Pronto")

    def test_avanca_a_main_e_conclui_o_epico(self):
        self.preparar()
        r = self.script("publicar-sem-release.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git_origin("rev-parse", "main"), self.git_origin("rev-parse", "develop"))
        for n in ("7", "11", "12", "13"):
            self.assertEqual(self.estado["issues"][n]["state"], "closed")
        self.assertEqual(self.status(1, 7), "Concluída")
        self.assertEqual(self.status(2, 12), "Concluído")
        self.assertIn("epico/7-estoque", self.estado.get("apagadas", []))

    def test_recusa_com_artefato_ou_ci_vermelha(self):
        self.preparar()
        self.estado["checks"] = {}
        self.gravar_estado()
        r = self.script("publicar-sem-release.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("check", r.stdout)
        self.git("fetch", "-q", "origin")
        self.branch("develop", "develop", "src/app.js", "não publicado\n")
        self.estado["checks"][self.git_origin("rev-parse", "develop")] = VERDE
        self.gravar_estado()
        r = self.script("publicar-sem-release.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("exige release", r.stdout)
        self.assertNotEqual(self.git_origin("rev-parse", "main"), self.git_origin("rev-parse", "develop"))

    def test_simular(self):
        self.preparar()
        r = self.script("publicar-sem-release.sh", SIMULAR="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.git_origin("rev-parse", "main"), self.git_origin("rev-parse", "develop"))


class EncerrarEVerPaineis(CasoDeScript):
    def test_encerrar_sprint_mantem_os_cartoes(self):
        self.issue(5, "Tarefa")
        self.rodar("projeto.sh", "sprint-criar", "2", "Sprint 1 · 2026-10-05")
        self.rodar("projeto.sh", "sprint-criar", "1", "Sprint 1 · 2026-10-05")
        self.rodar("projeto.sh", "sprint", "2", "5", "Sprint 1 · 2026-10-05")
        r = self.rodar("encerrar.sh", env={"SPRINT": "true", "HOJE": "2026-10-19"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rodar("projeto.sh", "sprint-de", "2", "5").stdout.strip(),
                         "Sprint 1 · 2026-10-05 → 2026-10-19")

    def test_encerrar_versao_exige_publicacao(self):
        r = self.rodar("encerrar.sh", env={"VERSAO": "1.0.0"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("não foi publicada", r.stdout)

    def test_encerrar_versao_limpa_com_travas(self):
        self.estado["refs"] = {"tags/v1.0.0": "t", "heads/release/1.0.0": "r", "heads/feature/12-regra": "f",
                               "heads/epico/7-estoque": "e"}
        self.estado["releases"] = ["v1.0.0"]
        self.estado["milestones"] = [{"number": 1, "title": "v1.0.0", "state": "open"}]
        self.estado["compare"] = {"v1.0.0...epico/7-estoque": 2}  # a commit outside the tag: kept
        self.gravar_estado()
        self.issue(7, "Estoque", labels=["epic"], milestone="v1.0.0")
        self.issue(12, "Regra", labels=["task"], milestone="v1.0.0")
        r = self.rodar("encerrar.sh", env={"VERSAO": "1.0.0"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.estado["issues"]["12"]["state"], "closed")
        self.assertEqual(self.status(1, 7), "Concluída")
        self.assertEqual(self.estado["milestones"][0]["state"], "closed")
        self.assertIn("feature/12-regra", self.estado["apagadas"])
        self.assertIn("release/1.0.0", self.estado["apagadas"])
        self.assertNotIn("epico/7-estoque", self.estado["apagadas"])
        self.assertIn("tags/v1.0.0", self.estado["refs"])  # tags are never deleted

    def test_ver_paineis(self):
        self.issue(7, "Estoque")
        self.issue(12, "Regra")
        self.cartao(1, 7, "Homologação")
        self.cartao(2, 12, "Validar PR", Sprint="Sprint 1 · 2026-10-05")
        r = self.rodar("ver-paineis.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Homologar o épico #7 Estoque", r.stdout)
        self.assertIn("- Revisar o PR da #12 Regra", r.stdout)
        self.assertIn("### Validar PR\n\n- #12 Regra (Sprint 1 · 2026-10-05)", r.stdout)


if __name__ == "__main__":
    unittest.main()
