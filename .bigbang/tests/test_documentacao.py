"""Markdown sanity and relative links (spec E1; DOC-14).

External links are not fetched (network makes tests flaky, TST-04). Templates in .bigbang/modelos/ are skipped for
link checks because their links are relative to the file's destination in a project, not to the template folder.
"""
import os
import re
import unittest

from _raiz import RAIZ, arquivos_markdown, importar_bb

importar_bb()

PULAR_LINKS = (os.path.join(RAIZ, ".bigbang", "modelos") + os.sep,)
SAIDAS_GERADAS = (os.path.join(RAIZ, ".bigbang", "tests", "esperado") + os.sep,
                  # subagents and skills follow the tool's format (a YAML header), not the docs format
                  os.path.join(RAIZ, ".claude") + os.sep, os.path.join(RAIZ, ".agents") + os.sep)
# The spec is copied verbatim from the owner (it must not change), so it is only checked for fences.
ESPECIFICACAO = os.path.join(RAIZ, ".bigbang", "docs", "especificacao.md")

from bb.docs_check import LINK, anchor as ancora, broken_links as links_quebrados  # noqa: E402
from bb.docs_check import outside_code as sem_codigo  # noqa: E402

TITULO = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


class Markdown(unittest.TestCase):
    def test_cercas_de_codigo_fechadas(self):
        for caminho in arquivos_markdown():
            with self.subTest(arquivo=os.path.relpath(caminho, RAIZ)):
                with open(caminho, encoding="utf-8") as arquivo:
                    _, fechadas = sem_codigo(arquivo.read())
                self.assertTrue(fechadas)

    def test_links_relativos_existem(self):
        for caminho in arquivos_markdown():
            if caminho.startswith(PULAR_LINKS + SAIDAS_GERADAS) or caminho == ESPECIFICACAO:
                continue
            with self.subTest(arquivo=os.path.relpath(caminho, RAIZ)):
                self.assertEqual(links_quebrados(caminho), [])

    def test_todo_markdown_tem_titulo(self):
        for caminho in arquivos_markdown():
            if os.path.basename(caminho) in ("CLAUDE.md", "RN.md", "AGENTS.projeto.md"):
                continue  # an import line; a key: value header; a fragment appended to AGENTS.md
            if caminho.startswith(SAIDAS_GERADAS) or f"{os.sep}arquivos{os.sep}" in caminho:
                continue  # generator templates and expected outputs follow the format of their destination
            with self.subTest(arquivo=os.path.relpath(caminho, RAIZ)):
                with open(caminho, encoding="utf-8") as arquivo:
                    linhas, _ = sem_codigo(arquivo.read())
                self.assertTrue(any(TITULO.match(l) and l.startswith("# ") for l in linhas))


class AutoTesteDosLinks(unittest.TestCase):
    def test_ancora_estilo_github(self):
        self.assertEqual(ancora("01 · Visão do processo"), "01--visão-do-processo")
        self.assertEqual(ancora("Use `bb gerar` agora"), "use-bb-gerar-agora")

    def test_codigo_nao_conta(self):
        linhas, fechadas = sem_codigo("a\n```\n[x](nao-existe.md)\n```\nb `[y](z.md)`\n")
        self.assertTrue(fechadas)
        self.assertEqual(LINK.findall("\n".join(linhas)), [])

    def test_cerca_aberta_detectada(self):
        _, fechadas = sem_codigo("```\nsem fim\n")
        self.assertFalse(fechadas)

    def test_detecta_link_quebrado(self):
        import tempfile
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "a.md")
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write("# A\n\n## Seção um\n\n[ok](#seção-um) [ruim](b.md) [âncora](#nada) [web](https://x.y)\n")
            self.assertEqual(links_quebrados(caminho), ["b.md", "#nada"])


if __name__ == "__main__":
    unittest.main()
