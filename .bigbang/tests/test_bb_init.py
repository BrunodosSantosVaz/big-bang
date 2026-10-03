"""`bb init` (Foundation F0) with a fake gh that records every call."""
import contextlib
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import tomllib
import unittest

from _raiz import RAIZ, ignorar_para_copia, importar_bb

importar_bb()
from bb import checksums, cli, init, verify  # noqa: E402
from bb.errors import EXIT_INVALID_STATE, EXIT_OK, EXIT_USAGE  # noqa: E402

GH_FALSO = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
if os.environ.get("GH_FALHA") and args[:2] == ["label", "create"]:
    sys.stderr.write("HTTP 403: sem permissão\n"); sys.exit(1)
if args[:2] == ["api", "user"]:
    print("dona-teste")
elif args[:1] == ["api"] and args[1].startswith("licenses/"):
    print("MIT License\n\nCopyright (c) [year] [fullname]\n")
elif args[:1] == ["api"] and args[1].startswith("users/"):
    print("Pessoa Fictícia")
elif args[:2] == ["issue", "list"]:
    print(os.environ.get("GH_ISSUES", "[]"))
elif args[:2] == ["issue", "create"]:
    print("https://github.com/dona-teste/sistema-x/issues/1")
'''


class Init(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.pasta.name, "sistema-x")
        shutil.copytree(RAIZ, self.raiz, ignore=ignorar_para_copia("bigbang.toml", "STACK.md"))
        checksums.write(self.raiz)
        os.makedirs(os.path.join(self.raiz, ".git"))
        with open(os.path.join(self.raiz, ".git", "config"), "w", encoding="utf-8") as arquivo:
            arquivo.write('[remote "origin"]\n\turl = git@github.com:dona-teste/sistema-x.git\n')
        self.log = os.path.join(self.pasta.name, "gh.log")
        falso = os.path.join(self.pasta.name, "gh_falso.py")
        with open(falso, "w", encoding="utf-8") as arquivo:
            arquivo.write(GH_FALSO)
        self.ambiente = {"BB_GH": f'"{sys.executable}" "{falso}"', "GH_LOG": self.log}
        self.antigo = {chave: os.environ.get(chave) for chave in (*self.ambiente, "GH_ISSUES", "GH_FALHA")}
        os.environ.update(self.ambiente)

    def tearDown(self):
        for chave, valor in self.antigo.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor
        self.pasta.cleanup()

    def chamadas(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as arquivo:
            return [json.loads(linha) for linha in arquivo]

    def ler(self, caminho):
        with open(os.path.join(self.raiz, *caminho.split("/")), encoding="utf-8") as arquivo:
            return arquivo.read()

    def rodar(self, *argv):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            codigo = cli.main(["--raiz", self.raiz, "init", *argv])
        return codigo, saida.getvalue()

    def test_privado(self):
        readme_framework = self.ler("README.md")
        codigo, saida = self.rodar("--nome", "Sistema Ação X")
        self.assertEqual(codigo, EXIT_OK, saida)
        with open(os.path.join(self.raiz, "bigbang.toml"), "rb") as arquivo:
            config = tomllib.load(arquivo)
        self.assertEqual(config["projeto"], {"nome": "Sistema Ação X", "slug": "sistema-acao-x", "dono": "dona-teste",
                                             "repositorio": "dona-teste/sistema-x", "visibilidade": "privado",
                                             "licenca": ""})
        self.assertEqual(config["deploy"]["imagem"], "ghcr.io/dona-teste/sistema-acao-x")
        self.assertEqual(config["paineis"]["owner"], "dona-teste")
        self.assertIn("# versão do framework instalada", self.ler("bigbang.toml"))  # comments kept
        self.assertEqual(self.ler(".bigbang/README.md"), readme_framework)
        self.assertTrue(self.ler(".bigbang/LICENSE").startswith("MIT License"))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "LICENSE")))
        self.assertTrue(self.ler("README.md").startswith("# Sistema Ação X\n"))
        self.assertIn("a partir de .bigbang/AGENTS.base.md", self.ler("AGENTS.md"))
        self.assertIn("# Instruções para IAs — Sistema Ação X", self.ler("AGENTS.md"))
        self.assertIn("Issue de F0: https://github.com/dona-teste/sistema-x/issues/1", saida)
        self.assertEqual(verify.run(self.raiz), [])
        chamadas = self.chamadas()
        self.assertEqual(chamadas[0][:3], ["label", "create", "fundacao"])
        self.assertEqual(chamadas[-1][:2], ["issue", "create"])
        self.assertIn(init.F0_TITLE, chamadas[-1])

    def test_publico_cria_licenca_do_sistema(self):
        codigo, saida = self.rodar("--nome", "X", "--visibilidade", "publico", "--licenca", "MIT")
        self.assertEqual(codigo, EXIT_OK, saida)
        ano = datetime.date.today().year
        self.assertEqual(self.ler("LICENSE"), f"MIT License\n\nCopyright (c) {ano} Pessoa Fictícia\n")
        self.assertIn(["api", "licenses/mit", "--jq", ".body"], self.chamadas())

    def test_publico_sem_licenca(self):
        self.assertEqual(self.rodar("--nome", "X", "--visibilidade", "publico")[0], EXIT_USAGE)

    def test_nao_roda_duas_vezes(self):
        self.assertEqual(self.rodar("--nome", "X")[0], EXIT_OK)
        self.assertEqual(self.rodar("--nome", "X")[0], EXIT_INVALID_STATE)

    def test_issue_de_f0_existente_nao_duplica(self):
        os.environ["GH_ISSUES"] = json.dumps([{"number": 7, "title": init.F0_TITLE}])
        codigo, saida = self.rodar("--nome", "X")
        self.assertEqual(codigo, EXIT_OK)
        self.assertIn("Issue de F0: 7", saida)
        self.assertNotIn(["issue", "create"], [c[:2] for c in self.chamadas()])

    def test_falha_no_github_nao_altera_arquivos(self):
        os.environ["GH_FALHA"] = "1"
        codigo, saida = self.rodar("--nome", "X")
        self.assertNotEqual(codigo, EXIT_OK)
        self.assertIn("sem permissão", saida)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "bigbang.toml")))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, ".bigbang", "README.md")))

    def test_simular_nao_faz_nada(self):
        codigo, saida = self.rodar("--nome", "X", "--simular")
        self.assertEqual(codigo, EXIT_OK)
        self.assertIn("Simulação do bb init para dona-teste/sistema-x", saida)
        self.assertEqual(self.chamadas(), [])
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "bigbang.toml")))

    def test_sem_github(self):
        self.assertEqual(self.rodar("--nome", "X", "--sem-github")[0], EXIT_OK)
        self.assertEqual(self.chamadas(), [])


class Auxiliares(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(init.slugify("  Gestão de Pedidos 2.0! "), "gestao-de-pedidos-2-0")

    def test_set_value_mantem_comentario_e_secao(self):
        texto = '[a]\nx = "1"   # comentário\n\n[b]\nx = "2"\n'
        self.assertEqual(init.set_value(texto, "b", "x", 'novo "valor"'),
                         '[a]\nx = "1"   # comentário\n\n[b]\nx = "novo \\"valor\\""\n')
        self.assertEqual(init.set_value(texto, "a", "x", "z"), '[a]\nx = "z"   # comentário\n\n[b]\nx = "2"\n')


if __name__ == "__main__":
    unittest.main()
