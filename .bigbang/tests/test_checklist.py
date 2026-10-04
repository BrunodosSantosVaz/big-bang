"""bb checklist producao (spec 8.2): an item without verification, a failing command, a value in .env.example or an
undocumented variable each refuse the checklist."""
import os
import shutil
import tempfile
import unittest

from _raiz import importar_bb

importar_bb()
from bb import checklist  # noqa: E402


def linha(item, verificacao):
    return f"- [ ] {item} — verificação: `{verificacao}`"


class Checklist(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz)
        os.makedirs(os.path.join(self.raiz, "docs", "operacao"))
        self.itens = {item: "nao-se-aplica: projeto sem front" for item in checklist.ITEMS}

    def gravar(self):
        texto = "# Checklist\n\n" + "\n".join(linha(item, v) for item, v in self.itens.items()) + "\n"
        with open(os.path.join(self.raiz, checklist.CHECKLIST_FILE), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    def escrever(self, nome, texto):
        with open(os.path.join(self.raiz, nome), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    def rodar(self):
        self.gravar()
        return checklist.run(self.raiz, with_github=False)

    def test_tudo_verificado(self):
        self.itens[checklist.ITEMS[0]] = "cmd: true"
        self.itens[checklist.ITEMS[4]] = "portao: seguranca"
        resultados, problemas = self.rodar()
        self.assertEqual(problemas, [])
        self.assertEqual(resultados[0], (checklist.ITEMS[0], "ok", "true"))

    def test_recusa_cada_caso(self):
        casos = {
            "item a definir": lambda: self.itens.update({checklist.ITEMS[1]: "a definir"}),
            "comando falha": lambda: self.itens.update({checklist.ITEMS[0]: "cmd: exit 3"}),
            "portão inventado": lambda: self.itens.update({checklist.ITEMS[0]: "portao: confia"}),
            "valor no .env.example": lambda: (self.escrever(".env.example", "DATABASE_URL=postgres://segredo\n"),
                                              self.escrever("README.md", "DATABASE_URL\n")),
            "variável sem documentação": lambda: (self.escrever(".env.example", "API_KEY=\n"),
                                                  self.escrever("README.md", "# Sistema\n")),
        }
        for nome, estragar in casos.items():
            with self.subTest(caso=nome):
                self.setUp()
                estragar()
                self.assertTrue(self.rodar()[1])

    def test_sem_arquivo(self):
        self.assertTrue(checklist.run(self.raiz, with_github=False)[1])

    def test_modelo_vem_com_itens_a_definir(self):
        from _raiz import ler
        modelo = ler(".bigbang", "modelos", "checklist-producao.md")
        for item in checklist.ITEMS:
            self.assertIn(item, modelo)
        with open(os.path.join(self.raiz, checklist.CHECKLIST_FILE), "w", encoding="utf-8") as arquivo:
            arquivo.write(modelo)
        self.assertTrue(checklist.run(self.raiz, with_github=False)[1])  # the model alone never passes


if __name__ == "__main__":
    unittest.main()
