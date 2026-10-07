"""bb decisao, bb revisao aprovar and the regression order of bug PRs."""
import contextlib
import io
import os
import shutil
import sys
import unittest

from _raiz import BIGBANG, exemplo_toml
from _scripts import CasoDeScript
from test_integrar_publicar import ComGit

BB = os.path.join(BIGBANG, "bin", "bb.py")
sys.path.insert(0, BIGBANG)
from bb import cli  # noqa: E402
from unittest.mock import patch
from bb.errors import EXIT_OK, EXIT_USAGE, EXIT_VERIFICATION_FAILED  # noqa: E402

DIFF_SRC = "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n"
DIFF_AUTH = DIFF_SRC.replace("src/a.py", "src/app/auth/login.py")


class ComCli(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.projeto = os.path.join(self.pasta, "projeto")
        os.makedirs(os.path.join(self.projeto, ".bigbang"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(self.projeto, ".bigbang", "VERSION"))
        toml = exemplo_toml().replace("BrunodosSantosVaz/meu-sistema", "dono/repo").replace(
            'dono = "BrunodosSantosVaz"', 'dono = "dono"')
        with open(os.path.join(self.projeto, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(toml)
        self.antigo = {k: os.environ.get(k) for k in ("BB_GH", "FAKE_GH_STATE", "FAKE_GH_LOG", "GITHUB_REPOSITORY")}
        os.environ.update({"BB_GH": os.path.join(self.bin, "gh"), "FAKE_GH_STATE": self.estado_arquivo,
                           "FAKE_GH_LOG": self.log, "GITHUB_REPOSITORY": "dono/repo"})

    def tearDown(self):
        for chave, valor in self.antigo.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor

    def bb(self, *argv):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            codigo = cli.main(["--raiz", self.projeto, *argv])
        self.ler_estado()
        return codigo, saida.getvalue()


class Decisao(ComCli):
    def test_comenta_a_frase_e_depois_poe_a_label(self):
        self.issue(7, "Épico", labels=["epic", "homologado"])
        codigo, _ = self.bb("decisao", "reprovado", "7", "--frase", "A vírgula está errada.", "--ia", "claude-1")
        self.assertEqual(codigo, EXIT_OK)
        comentario = self.estado["comments"]["7"][0]
        self.assertIn("**Decisão do dono:** `reprovado`", comentario)
        self.assertIn("> A vírgula está errada.", comentario)
        self.assertIn("`claude-1`", comentario)
        self.assertEqual(self.estado["issues"]["7"]["labels"], ["epic", "reprovado"])  # homologado removed
        chamadas = [c for c in self.chamadas() if c[0] == "api"]
        def posicao(sufixo):
            return next(i for i, c in enumerate(chamadas) if c[3].endswith(sufixo))
        self.assertLess(posicao("/comments"), posicao("/labels"))  # the phrase comes before the label

    def test_recusa_label_que_nao_e_decisao_e_frase_vazia(self):
        self.issue(7, "Épico")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.bb("decisao", "epic", "7", "--frase", "x")[0], EXIT_USAGE)
        self.assertEqual(self.bb("decisao", "homologado", "7", "--frase", "  ")[0], EXIT_USAGE)
        self.assertNotIn("comments", self.estado)


class RevisaoAprovar(ComCli):
    def pr(self, head="feature/12-tarefa", labels=(), diff=DIFF_SRC):
        self.estado.setdefault("prs", {})["30"] = {"head": head, "base": "epico/7-x", "labels": list(labels),
                                                   "state": "OPEN", "diff": diff}
        self.gravar_estado()

    def test_aprova_pr_comum(self):
        self.issue(12, "Tarefa", labels=["task"])
        self.pr()
        codigo, saida = self.bb("revisao", "aprovar", "30", "--ia", "claude-2")
        self.assertEqual(codigo, EXIT_OK, saida)
        self.assertIn("pr-aprovado", self.estado["prs"]["30"]["labels"])
        self.assertIn("Revisão da IA: aprovado", self.estado["comments"]["30"][0])

    def test_recusa_quando_a_revisao_e_do_dono(self):
        casos = {"revisao-humana": dict(labels=["revisao-humana"]), "zona sensível": dict(diff=DIFF_AUTH)}
        for nome, args in casos.items():
            with self.subTest(caso=nome):
                self.issue(12, "Tarefa", labels=["task"])
                self.pr(**args)
                codigo, saida = self.bb("revisao", "aprovar", "30")
                self.assertEqual(codigo, EXIT_VERIFICATION_FAILED)
                self.assertIn("recusado", saida)
                self.assertNotIn("pr-aprovado", self.estado["prs"]["30"]["labels"])

    def test_dono_revisao_ia_prevalece(self):
        self.issue(12, "Tarefa", labels=["task", "dono:revisao-ia"])
        self.pr(labels=["revisao-humana"], diff=DIFF_AUTH)
        self.assertEqual(self.bb("revisao", "aprovar", "30")[0], EXIT_OK)

    def test_local_flash_cannot_change_target_review_policy(self):
        path = os.path.join(self.projeto, 'bigbang.toml')
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text.replace('modo = "padrao"', 'modo = "flash"'))
        self.issue(12, 'Tarefa', labels=['task'])
        self.pr(diff=DIFF_AUTH)
        with patch('bb.decisions._target_mode', return_value='padrao'):
            self.assertEqual(self.bb('revisao', 'aprovar', '30')[0], EXIT_VERIFICATION_FAILED)

    def test_target_flash_is_used_even_when_local_config_is_standard(self):
        self.issue(12, 'Tarefa', labels=['task'])
        self.pr(diff=DIFF_AUTH)
        with patch('bb.decisions._target_mode', return_value='flash') as target:
            self.assertEqual(self.bb('revisao', 'aprovar', '30')[0], EXIT_OK)
        target.assert_called_once_with('dono/repo', 'epico/7-x')

    def test_destination_config_is_fetched_from_github(self):
        self.estado['repository_files'] = {'epico/7-x': {'bigbang.toml':
            '[projeto]\nmodo="flash"\n'}}
        self.issue(12, 'Tarefa', labels=['task'])
        self.pr(diff=DIFF_AUTH)
        self.assertEqual(self.bb('revisao', 'aprovar', '30')[0], EXIT_OK)
        self.estado['repository_files']['epico/7-x']['bigbang.toml'] = '[projeto]\nmodo="padrao"\n'
        self.pr(diff=DIFF_AUTH)
        self.assertEqual(self.bb('revisao', 'aprovar', '30')[0], EXIT_VERIFICATION_FAILED)

    def test_testes_com_revisao_humana(self):
        self.issue(11, "Testes", labels=["teste-aceite", "testes-revisao-humana"])
        self.pr(head="teste/11-testes")
        self.assertEqual(self.bb("revisao", "aprovar", "30")[0], EXIT_VERIFICATION_FAILED)
        self.issue(11, "Testes", labels=["teste-aceite", "testes-revisao-ia"])
        self.assertEqual(self.bb("revisao", "aprovar", "30")[0], EXIT_OK)


class Regressao(ComGit):
    def setUp(self):
        super().setUp()
        toml = os.path.join(self.trabalho, "bigbang.toml")
        with open(toml, encoding="utf-8") as arquivo:
            texto = arquivo.read().replace('testes = "npm test"', 'testes = "python3 -m unittest discover -s tests -t ."')
            texto = texto.replace('testes_aceite = "npm run test:acceptance"', 'testes_aceite = ""')
        with open(toml, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        self.escrever("src/__init__.py", "")
        self.escrever("src/conta.py", "def total(a, b):\n    return a - b\n")
        self.escrever("tests/__init__.py", "")
        self.commit("feat: conta")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-b", "bugfix/20-total")

    def teste_de_regressao(self):
        self.escrever("tests/test_conta.py", "import unittest\nfrom src.conta import total\n\n\n"
                                             "class T(unittest.TestCase):\n    def test_soma(self):\n"
                                             "        self.assertEqual(total(2, 3), 5)\n")

    def correcao(self):
        self.escrever("src/conta.py", "def total(a, b):\n    return a + b\n")

    def regressao(self):
        head = self.git("rev-parse", "HEAD", saida=True)
        return self.script("regressao.sh", BASE_REF="main", PR_HEAD_SHA=head)

    def test_teste_primeiro_depois_a_correcao(self):
        self.teste_de_regressao()
        self.commit("test: total soma")
        self.correcao()
        self.commit("fix: total soma")
        r = self.regressao()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_recusa_correcao_junto_com_o_teste(self):
        self.teste_de_regressao()
        self.correcao()
        self.commit("fix: tudo junto")
        self.escrever("docs/a.md", "# a\n")
        self.commit("docs: nota")
        r = self.regressao()
        self.assertEqual(r.returncode, 1)
        self.assertIn("só o teste de regressão", r.stdout)

    def test_recusa_teste_que_nao_falha(self):
        self.escrever("tests/test_conta.py", "import unittest\n\n\nclass T(unittest.TestCase):\n"
                                             "    def test_nada(self):\n        self.assertTrue(True)\n")
        self.commit("test: inofensivo")
        self.correcao()
        self.commit("fix: total soma")
        r = self.regressao()
        self.assertEqual(r.returncode, 1)
        self.assertIn("precisa falhar", r.stdout)

    def test_teste_em_layout_gradle_conta_como_teste(self):
        # pilot #61: app/src/test/.../XTest.kt is a test file, not production code
        self.escrever("app/src/test/java/io/exemplo/ContaTest.kt", "class ContaTest\n")
        self.escrever("app/src/androidTest/java/io/exemplo/TelaTest.kt", "class TelaTest\n")
        self.commit("test: conta em Kotlin")
        self.correcao()
        self.commit("fix: total soma")
        r = self.regressao()
        self.assertNotIn("só o teste de regressão", r.stdout)  # classified as test, then the stack's tests run

    def test_recusa_um_commit_so(self):
        self.teste_de_regressao()
        self.correcao()
        self.commit("fix: tudo")
        self.assertEqual(self.regressao().returncode, 1)


if __name__ == "__main__":
    unittest.main()
