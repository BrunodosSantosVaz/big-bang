"""DOC-15: after the first release the system README is complete and current (pilot ScreenFakeCam: the README still
said "Em Fundação" with three versions in production)."""
import os
import shutil
import subprocess
import tempfile
import unittest

from _raiz import BIGBANG, importar_bb

importar_bb()
from bb import docs_check  # noqa: E402

COMPLETO = """# Sistema

[![CI](https://github.com/d/s/actions/workflows/bb-ci.yml/badge.svg)](https://github.com/d/s/actions)

## Índice

- [Estado atual](#estado-atual)

## Estado atual

v0.3.0 em produção.

## Para que serve

x

## Recursos

x

## Instalação

x

## Como usar

x

## Para desenvolvedores

x

## Versões e releases

x

## Segurança e privacidade

x

## Limitações conhecidas

x

## Contribuindo

x

## Licença

x
"""


class ReadmeDoSistema(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz)
        subprocess.run(["git", "init", "-q", self.raiz], check=True)
        for nome, texto in (("bigbang.toml", "x = 1\n"), ("README.md", COMPLETO)):
            with open(os.path.join(self.raiz, nome), "w", encoding="utf-8") as arquivo:
                arquivo.write(texto)
        subprocess.run(["git", "-C", self.raiz, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "x",
                        "--allow-empty"], check=True)
        subprocess.run(["git", "-C", self.raiz, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.raiz, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "y"],
                       check=True)

    def readme(self, texto):
        with open(os.path.join(self.raiz, "README.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    def publicar(self, tag="v0.1.0"):
        subprocess.run(["git", "-C", self.raiz, "tag", tag], check=True)

    def test_antes_da_primeira_release_nao_cobra(self):
        self.readme("# Sistema\n\nEm **Fundação**.\n")
        self.publicar("v0.1.0-rc.1")  # a candidate is not a release
        self.assertEqual(docs_check.readme_problems(self.raiz), [])

    def test_completo_passa(self):
        self.publicar()
        self.assertEqual(docs_check.readme_problems(self.raiz), [])

    def test_ainda_na_fundacao_ou_a_preencher_reprova(self):
        self.publicar()
        self.readme(COMPLETO.replace("v0.3.0 em produção.", "Em **Fundação**: ainda.\n\n(a preencher)"))
        problemas = docs_check.readme_problems(self.raiz)
        self.assertTrue(any("Fundação" in p for p in problemas), problemas)
        self.assertTrue(any("a preencher" in p for p in problemas), problemas)

    def test_falta_secao_e_selo(self):
        self.publicar()
        self.readme(COMPLETO.replace("## Recursos", "## Coisas").replace("badge.svg", "x.png"))
        problemas = docs_check.readme_problems(self.raiz)
        self.assertIn('README.md: falta a seção "Recursos" (DOC-15, modelo em .bigbang/modelos/README-sistema.md)',
                      problemas)
        self.assertIn("README.md: sem o selo da CI (DOC-15)", problemas)

    def test_comentario_do_modelo_nao_conta(self):
        self.publicar()
        self.readme(COMPLETO + "\n<!-- Em **Fundação** era o texto antigo; (a preencher) -->\n")
        self.assertEqual(docs_check.readme_problems(self.raiz), [])

    def test_modelo_tem_todas_as_secoes(self):
        with open(os.path.join(BIGBANG, "modelos", "README-sistema.md"), encoding="utf-8") as arquivo:
            modelo = arquivo.read()
        for secao in docs_check.README_SECTIONS:
            self.assertIn(secao, modelo)

    def test_sem_bigbang_toml_nao_se_aplica(self):  # the framework repository itself
        os.remove(os.path.join(self.raiz, "bigbang.toml"))
        self.publicar()
        self.readme("# x\n")
        self.assertEqual(docs_check.readme_problems(self.raiz), [])


class ComunidadeEIcone(ReadmeDoSistema):
    """DOC-16 (community files) and DOC-17 (global icon); pilot: the repository showed only README and license."""

    def escrever(self, caminho, texto="x\n"):
        os.makedirs(os.path.dirname(os.path.join(self.raiz, caminho)) or self.raiz, exist_ok=True)
        with open(os.path.join(self.raiz, caminho), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    def test_cobra_os_arquivos_de_comunidade(self):
        problemas = docs_check.community_problems(self.raiz)
        for nome in docs_check.COMMUNITY_FILES:
            self.assertTrue(any(p.startswith(nome) for p in problemas), problemas)
        for nome in docs_check.COMMUNITY_FILES:
            self.escrever(nome)
        self.assertEqual(docs_check.community_problems(self.raiz), [])

    def test_icone_depois_do_design_ou_da_release(self):
        for nome in docs_check.COMMUNITY_FILES:
            self.escrever(nome)
        self.assertEqual(docs_check.community_problems(self.raiz), [])  # still in the Foundation, before F3
        self.escrever("DESIGN.md")
        self.assertIn("ícone global", " ".join(docs_check.community_problems(self.raiz)))
        self.escrever(docs_check.ICON, "<svg/>")
        self.assertEqual(docs_check.community_problems(self.raiz), [])
        os.remove(os.path.join(self.raiz, "DESIGN.md"))
        os.remove(os.path.join(self.raiz, docs_check.ICON))
        self.publicar()
        self.assertIn("ícone global", " ".join(docs_check.community_problems(self.raiz)))

    def test_modelos_existem(self):
        for nome in docs_check.COMMUNITY_FILES:
            self.assertTrue(os.path.exists(os.path.join(BIGBANG, "modelos", "comunidade", nome)), nome)


if __name__ == "__main__":
    unittest.main()
