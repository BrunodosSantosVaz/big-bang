"""regras-pr.sh (job `regras`): each rule refuses the wrong case and accepts the right one."""
import os
import shutil
import subprocess
import sys
import unittest

from _raiz import BIGBANG, exemplo_toml
from _scripts import CasoDeScript

BB = os.path.join(BIGBANG, "bin", "bb.py")
CORPO = "## O que muda\nx\n\n## Issue\nRefs #12\n"


class _Base(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.projeto = os.path.join(self.pasta, "projeto")
        os.makedirs(os.path.join(self.projeto, ".bigbang"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(self.projeto, ".bigbang", "VERSION"))
        with open(os.path.join(self.projeto, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(exemplo_toml())
        self.issue(12, "Tarefa", labels=["task"])

    def regras(self, head="feature/12-tarefa", base="epico/7-estoque", titulo="feat(pedidos): bloqueia pedido",
               corpo=CORPO, arquivos="src/pedidos.py\n", labels="", sha="", diff_texto="", dados=""):
        env = {"HEAD_REF": head, "BASE_REF": base, "PR_TITLE": titulo, "PR_BODY": corpo, "PR_NUMBER": "30",
               "PR_LABELS": labels, "DIFF_ARQUIVOS": arquivos, "PR_HEAD_SHA": sha, "DIFF_TEXTO": diff_texto,
               "DADOS_PR": dados,
               "BB": f"{sys.executable} {BB} --raiz {self.projeto}"}
        return self.rodar("regras-pr.sh", env=env, cwd=self.projeto)

    def labels_pr(self):
        return self.ler_estado().get("prs", {}).get("30", {}).get("labels", [])


class RegrasPr(_Base):
    def test_pr_com_mais_de_300_arquivos_pela_api(self):
        # gh pr diff refuses PRs over 300 files (a framework update has more): the files API is paginated
        self.estado["pr_files"] = {"30": [{"filename": f".bigbang/arquivo-{n}.md", "patch": "+x"} for n in range(330)]}
        self.gravar_estado()
        r = self.regras(head="framework/v0.10.1", base="develop", titulo="chore(framework): atualizar o Big Bang",
                        corpo="## O que muda\nx\n", arquivos="", labels="revisao-humana")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_aceite_sem_patch_falha_fechado(self):
        self.estado["pr_files"] = {"30": [{"filename": "tests/aceite/test_rn.py", "status": "modified"}]}
        self.gravar_estado()
        r = self.regras(arquivos="", diff_texto="")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("grande demais", r.stdout + r.stderr)

    def test_aceite_pela_api_aplica_a_trava(self):
        patch = "@@ -1,2 +1,2 @@\n-def test_a():\n+def test_b():"
        self.estado["pr_files"] = {"30": [{"filename": "tests/aceite/test_rn.py", "patch": patch}]}
        self.gravar_estado()
        r = self.regras(arquivos="", diff_texto="")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("tests/aceite/test_rn.py", r.stdout + r.stderr)

    def test_pr_certo(self):
        r = self.regras()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("dentro das regras", r.stdout)

    def test_recusa_nome_destino_titulo_e_refs(self):
        casos = {
            "destino": dict(base="develop"),
            "nome": dict(head="minha-branch"),
            "título": dict(titulo="Bloqueia pedido"),
            "sem Refs": dict(corpo="sem referência"),
            "Refs de outra issue": dict(corpo="Refs #99"),
            "Closes": dict(corpo="Refs #12\nCloses #12"),
        }
        for nome, args in casos.items():
            with self.subTest(caso=nome):
                self.assertEqual(self.regras(**args).returncode, 1)

    def test_zona_sensivel_troca_para_revisao_humana(self):
        self.regras(arquivos="src/app/auth/login.py\n", labels="revisao-ia")
        self.assertIn("revisao-humana", self.labels_pr())

    def test_dono_revisao_ia_prevalece(self):
        self.regras(arquivos="src/app/auth/login.py\n", labels="revisao-ia,dono:revisao-ia")
        self.assertNotIn("revisao-humana", self.labels_pr())
        self.issue(12, "Tarefa", labels=["task", "dono:revisao-ia"])
        self.regras(arquivos=".github/workflows/x.yml\n", labels="revisao-ia")
        self.assertNotIn("revisao-humana", self.labels_pr())

    def test_pr_de_teste_pode_tocar_tests_aceite(self):
        self.issue(13, "Testes", labels=["teste-aceite"])
        r = self.regras(head="teste/13-testes", corpo="Refs #13", arquivos="tests/aceite/7-estoque/test_a.py\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("revisao-humana", self.labels_pr())
        self.regras(arquivos="tests/aceite/7-estoque/test_a.py\n")  # a task PR touching it: human review
        self.assertIn("revisao-humana", self.labels_pr())

    def test_tarefa_que_so_libera_as_proprias_marcas_continua_com_a_ia(self):
        diff = ("diff --git a/tests/aceite/7-e/test_a.py b/tests/aceite/7-e/test_a.py\n--- a/x\n+++ b/x\n@@ -1 +0,0 @@\n"
                "-    @unittest.expectedFailure  # pendente da tarefa #12\n")
        toml = os.path.join(self.projeto, "bigbang.toml")
        with open(toml, encoding="utf-8") as arquivo:
            texto = arquivo.read().replace('marca_pendente = "test.failing"', 'marca_pendente = "expectedFailure"')
        with open(toml, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        r = self.regras(arquivos="src/a.py\ntests/aceite/7-e/test_a.py\n", labels="revisao-ia", diff_texto=diff)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("revisao-humana", self.labels_pr())
        r = self.regras(arquivos="src/a.py\ntests/aceite/7-e/test_a.py\n", labels="revisao-ia",
                        diff_texto=diff.replace("#12", "#99"))
        self.assertIn("revisao-humana", self.labels_pr())

    def test_sem_release_sincronizado(self):
        self.regras(arquivos="docs/guia.md\n")
        self.assertIn("sem-release", self.labels_pr())
        self.assertIn("sem-release", self.estado["issues"]["12"]["labels"])
        self.regras(arquivos="src/a.py\n", labels="sem-release")
        self.assertNotIn("sem-release", self.labels_pr())

    def test_epico_sem_release_com_artefato_reprova(self):
        self.issue(12, "Tarefa", labels=["task", "sem-release"])
        r = self.regras(arquivos="src/a.py\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sem-release", r.stdout)


class TravaEPendentes(_Base):
    ENFRAQUECE = ("diff --git a/tests/aceite/7-e/test_a.py b/tests/aceite/7-e/test_a.py\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n"
                  "-        self.assertEqual(total, 100)\n+        self.assertTrue(total)\n")

    def test_trava_reprova_e_teste_alterado_aprovado_libera(self):
        r = self.regras(arquivos="tests/aceite/7-e/test_a.py\n", diff_texto=self.ENFRAQUECE)
        self.assertEqual(r.returncode, 1)
        self.assertIn("teste-alterado-aprovado", r.stdout)
        r = self.regras(arquivos="tests/aceite/7-e/test_a.py\n", diff_texto=self.ENFRAQUECE,
                        labels="teste-alterado-aprovado")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_pendente_de_tarefa_ja_mesclada_reprova(self):
        dados = os.path.join(self.pasta, "head")
        os.makedirs(os.path.join(dados, "tests", "aceite", "7-e"))
        with open(os.path.join(dados, "tests", "aceite", "7-e", "a.test.js"), "w", encoding="utf-8") as arquivo:
            arquivo.write('test.failing("RN-0042 x", () => {  // pendente da tarefa #15\n')
        self.issue(15, "Outra tarefa", labels=["task"])
        self.assertEqual(self.regras(dados=dados).returncode, 0)  # #15 still open and not merged
        self.estado["pulls"] = [{"head": {"ref": "feature/15-outra-tarefa"}, "merged_at": "2026-10-04T00:00:00Z"}]
        self.gravar_estado()
        self.assertEqual(self.regras(dados=dados).returncode, 1)  # merged into the epic, issue still open
        self.estado["pulls"] = []
        self.gravar_estado()
        self.estado["api"] = {}
        self.issue(15, "Outra tarefa", labels=["task"], state="closed")
        r = self.regras(dados=dados)
        self.assertEqual(r.returncode, 1)
        self.assertIn("tests/aceite/7-e/a.test.js:1: teste ainda marcado como pendente da #15", r.stdout)


class PrDaRelease(_Base):
    """release/* -> main only carries epics already judged PR by PR (pilot ScreenFakeCam v0.1.0, PR #30)."""

    def dados_kotlin(self):
        dados = os.path.join(self.pasta, "release")
        os.makedirs(os.path.join(dados, "tests", "aceite", "1-e"))
        os.makedirs(os.path.join(dados, "docs", "negocio", "regras"))
        with open(os.path.join(dados, "tests", "aceite", "1-e", "ATest.kt"), "w", encoding="utf-8") as arquivo:
            arquivo.write("    @Test\n    fun `RN-0001 CA-1 faz algo`() {\n")
        with open(os.path.join(dados, "docs", "negocio", "regras", "RN-0001-x.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write("id: RN-0001\ntitulo: x\nsituacao: vigente\n")
        with open(os.path.join(dados, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write('[testes]\npadrao_teste = "fun `"\n')
        return dados

    def release(self, **extra):
        return self.regras(head="release/0.1.0", base="main", titulo="chore(release): v0.1.0", corpo="Release",
                           **extra)

    def test_trava_de_aceite_nao_se_aplica(self):
        r = self.release(arquivos="tests/aceite/7-e/test_a.py\n", diff_texto=TravaEPendentes.ENFRAQUECE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_rastreabilidade_com_o_padrao_que_vem_na_release(self):
        dados = self.dados_kotlin()
        r = self.release(arquivos="tests/aceite/1-e/ATest.kt\nbigbang.toml\n", dados=dados)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # the same content in a task PR is judged by the target's pattern
        r = self.regras(arquivos="tests/aceite/1-e/ATest.kt\n", dados=dados)
        self.assertIn("rastreabilidade", r.stdout)


class RastreioEGuardaNoPr(_Base):
    def test_dependencia_nova_sem_stack_reprova_e_com_a_linha_passa(self):
        dados = os.path.join(self.pasta, "head")
        os.makedirs(dados)
        with open(os.path.join(dados, "package.json"), "w", encoding="utf-8") as arquivo:
            arquivo.write('{"dependencies": {"left-pad": "1"}}')
        stack = ("# Stack\n<!-- bb:dependencias:inicio -->\n| Pacote | Ecossistema | Faixa de versão | Para quê | ADR |\n"
                 "| --- | --- | --- | --- | --- |\n<!-- bb:dependencias:fim -->\n")
        with open(os.path.join(dados, "STACK.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write(stack)
        r = self.regras(dados=dados)
        self.assertEqual(r.returncode, 1)
        self.assertIn("guarda da stack: package.json: left-pad (npm)", r.stdout)
        with open(os.path.join(dados, "STACK.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write(stack.replace("<!-- bb:dependencias:fim -->", "| left-pad | npm | 1 | x | ADR-0002 |\n"
                                                                          "<!-- bb:dependencias:fim -->"))
        self.assertEqual(self.regras(dados=dados).returncode, 0)


class InvarianteDaDevelop(_Base):
    """A PR into develop may not leave artifact code there that main (production) does not have."""

    def git(self, *args):
        subprocess.run(["git", "-C", self.projeto, *args], check=True, capture_output=True)

    def commit(self, caminho, texto):
        destino = os.path.join(self.projeto, caminho)
        os.makedirs(os.path.dirname(destino) or self.projeto, exist_ok=True)
        with open(destino, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        self.git("add", "-A")
        self.git("commit", "-qm", f"change {caminho}")
        return subprocess.run(["git", "-C", self.projeto, "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()

    def setUp(self):
        super().setUp()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "teste@example.com")
        self.git("config", "user.name", "Teste")
        self.commit("src/app.py", "v1\n")
        self.git("remote", "add", "origin", self.projeto)
        self.git("checkout", "-q", "-b", "fundacao/3-f2")

    def test_aceita_sem_artefato(self):
        sha = self.commit("docs/a.md", "# A\n")
        r = self.regras(head="fundacao/3-f2", base="develop", corpo="Refs #3", arquivos="docs/a.md\n", sha=sha)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_recusa_artefato_nao_publicado(self):
        sha = self.commit("src/app.py", "v2\n")
        r = self.regras(head="fundacao/3-f2", base="develop", corpo="Refs #3", arquivos="src/app.py\n", sha=sha)
        self.assertEqual(r.returncode, 1)
        self.assertIn("invariante", r.stdout)


class ComandoSh(CasoDeScript):
    def test_roda_pula_e_falha(self):
        projeto = os.path.join(self.pasta, "p")
        os.makedirs(os.path.join(projeto, ".bigbang"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(projeto, ".bigbang", "VERSION"))
        toml = exemplo_toml().replace('lint = "npm run lint"', 'lint = "echo lint-ok"').replace(
            'tipos = "npm run typecheck"', 'tipos = ""').replace('build = "npm run build"', 'build = "exit 3"')
        with open(os.path.join(projeto, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(toml)
        env = {"BB": f"{sys.executable} {BB} --raiz {projeto}"}
        # no artifact path yet (Foundation F5, before the walking skeleton): every command is skipped
        sem_artefato = self.rodar("comando.sh", "build", env=env)
        self.assertEqual(sem_artefato.returncode, 0, sem_artefato.stdout + sem_artefato.stderr)
        self.assertIn("nenhum caminho do artefato", sem_artefato.stdout)
        os.makedirs(os.path.join(self.pasta, "src"))  # first artifact path: the commands run from now on
        r = self.rodar("comando.sh", "lint", env=env)
        self.assertIn("lint-ok", r.stdout)
        self.assertIn("etapa pulada", self.rodar("comando.sh", "tipos", env=env).stdout)
        self.assertEqual(self.rodar("comando.sh", "build", env=env).returncode, 3)


    def test_comandos_da_stack_so_pelo_comando_sh(self):
        # seguranca.sh ran the build directly and failed before the artifact existed (pilot F5): every script runs
        # the stack commands through comando.sh, which skips them while no artifact path exists. regressao.sh only
        # runs on bug PRs (the artifact exists) and reads the test commands to run them on chosen commits.
        permitidos = {"comando.sh", "regressao.sh"}
        for pasta, _, nomes in os.walk(os.path.join(BIGBANG, "esteira")):
            for nome in nomes:
                if not nome.endswith(".sh") or nome in permitidos:
                    continue
                with open(os.path.join(pasta, nome), encoding="utf-8") as arquivo:
                    texto = arquivo.read()
                with self.subTest(script=nome):
                    self.assertNotRegex(texto, r"config get \"?comandos\.")


if __name__ == "__main__":
    unittest.main()
