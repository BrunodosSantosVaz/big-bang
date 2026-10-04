"""Acceptance tests as a contract (spec 11.7): bb aceite liberar, the lock and the pending marks."""
import os
import shutil
import tempfile
import unittest

from _raiz import importar_bb

importar_bb()
from bb import acceptance, pipeline  # noqa: E402

PY = '''import unittest


class Estoque(unittest.TestCase):
    @unittest.expectedFailure  # pendente da tarefa #11
    def test_rn0042_bloqueia(self):
        self.assertTrue(False)

    @unittest.expectedFailure  # pendente da tarefa #12
    def test_rn0043_avisa(self):
        self.assertTrue(False)
'''
JS = '''test.failing("RN-0042 bloqueia pedido", () => {  // pendente da tarefa #11
  expect(1).toBe(2);
});
'''


def diff_de(antes, depois, arquivo="tests/aceite/7-e/test_a.py"):
    import difflib
    linhas = difflib.unified_diff(antes.splitlines(), depois.splitlines(), f"a/{arquivo}", f"b/{arquivo}", lineterm="")
    return f"diff --git a/{arquivo} b/{arquivo}\n" + "\n".join(linhas) + "\n"


class Liberar(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz)
        os.makedirs(os.path.join(self.raiz, "tests", "aceite", "7-e"))
        self.py = os.path.join(self.raiz, "tests", "aceite", "7-e", "test_a.py")
        self.js = os.path.join(self.raiz, "tests", "aceite", "7-e", "a.test.js")
        for caminho, texto in ((self.py, PY), (self.js, JS)):
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write(texto)

    def ler(self, caminho):
        with open(caminho, encoding="utf-8") as arquivo:
            return arquivo.read()

    def test_libera_so_as_marcas_da_tarefa_e_o_diff_passa_na_trava(self):
        mudou = acceptance.release_marks(self.raiz, 11, "expectedFailure")
        self.assertEqual(mudou, [("tests/aceite/7-e/test_a.py", 5)])
        depois = self.ler(self.py)
        self.assertNotIn("tarefa #11", depois)
        self.assertIn("@unittest.expectedFailure  # pendente da tarefa #12", depois)
        self.assertEqual(acceptance.lock_problems(diff_de(PY, depois), "feature", 11, "expectedFailure", False), [])

    def test_marca_embutida_do_jest(self):
        acceptance.release_marks(self.raiz, 11, "test.failing")
        depois = self.ler(self.js)
        self.assertEqual(depois.splitlines()[0], 'test("RN-0042 bloqueia pedido", () => {')
        diff = diff_de(JS, depois, "tests/aceite/7-e/a.test.js")
        self.assertTrue(pipeline.only_own_marks_released(diff, 11, "test.failing"))

    def test_pendentes(self):
        self.assertEqual(acceptance.pending_marks(self.raiz, "expectedFailure"),
                         [(11, "tests/aceite/7-e/test_a.py:5"), (12, "tests/aceite/7-e/test_a.py:9")])


class Trava(unittest.TestCase):
    NOVO = PY + '''
    @unittest.expectedFailure  # pendente da tarefa #13
    def test_rn0044_novo(self):
        self.assertTrue(False)
'''
    ENFRAQUECIDO = PY.replace("self.assertTrue(False)", "pass", 1)

    def test_pr_de_teste_pode_acrescentar_mas_nao_alterar(self):
        self.assertEqual(acceptance.lock_problems(diff_de(PY, self.NOVO), "teste", 10, "expectedFailure", False), [])
        self.assertTrue(acceptance.lock_problems(diff_de(PY, self.ENFRAQUECIDO), "teste", 10, "expectedFailure",
                                                 False))

    def test_tarefa_nao_pode_enfraquecer_nem_mexer_em_marca_alheia(self):
        self.assertTrue(acceptance.lock_problems(diff_de(PY, self.ENFRAQUECIDO), "feature", 11, "expectedFailure",
                                                 False))
        alheia = PY.replace("    @unittest.expectedFailure  # pendente da tarefa #12\n", "")
        self.assertTrue(acceptance.lock_problems(diff_de(PY, alheia), "feature", 11, "expectedFailure", False))
        self.assertTrue(acceptance.lock_problems(diff_de(PY, self.NOVO), "feature", 11, "expectedFailure", False))

    def test_bug_pode_acrescentar_regressao(self):
        self.assertEqual(acceptance.lock_problems(diff_de(PY, self.NOVO), "bugfix", 20, "expectedFailure", False), [])
        self.assertTrue(acceptance.lock_problems(diff_de(PY, self.ENFRAQUECIDO), "hotfix", 20, "expectedFailure",
                                                 False))

    def test_teste_alterado_aprovado_libera(self):
        self.assertEqual(acceptance.lock_problems(diff_de(PY, self.ENFRAQUECIDO), "feature", 11, "expectedFailure",
                                                  True), [])

    def test_sem_mudanca_em_aceite(self):
        self.assertEqual(acceptance.lock_problems("diff --git a/src/a.py b/src/a.py\n+x\n", "feature", 11,
                                                  "expectedFailure", False), [])


if __name__ == "__main__":
    unittest.main()
