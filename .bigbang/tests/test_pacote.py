"""Framework package (ADR-0014): reproducible tarball of .bigbang/ and the MIGRACAO.md notes."""
import os
import shutil
import tarfile
import tempfile
import unittest

from _raiz import BIGBANG, RAIZ, ignorar_para_copia, importar_bb

importar_bb()
from bb import checksums, package  # noqa: E402
from bb.errors import BbError  # noqa: E402
from bb.paths import framework_version  # noqa: E402

MIGRACAO = """# Migração

## [1.1.0] - 2026-01-02

### O que muda

- Algo.

### O que o projeto precisa fazer

Renomeie a chave `a` para `b` no bigbang.toml.

## [1.0.1] - 2026-01-01

### O que muda

- Correção.

### O que o projeto precisa fazer

Nada.

## [1.0.0] - 2026-01-01

### O que muda

- Primeira.

### O que o projeto precisa fazer

Nada.
"""


class Pacote(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta)
        self.raiz = os.path.join(self.pasta, "repo")
        shutil.copytree(BIGBANG, os.path.join(self.raiz, ".bigbang"), ignore=ignorar_para_copia())

    def test_reprodutivel(self):
        _, um = package.build(self.raiz, os.path.join(self.pasta, "a"))
        os.utime(os.path.join(self.raiz, ".bigbang", "VERSION"), (1, 1))  # disk dates do not matter
        _, dois = package.build(self.raiz, os.path.join(self.pasta, "b"))
        self.assertEqual(um, dois)

    def test_conteudo_so_dentro_de_bigbang(self):
        alvo, digest = package.build(self.raiz, os.path.join(self.pasta, "a"))
        with open(alvo + ".sha256", encoding="utf-8") as arquivo:
            self.assertEqual(arquivo.read(), f"{digest}  {os.path.basename(alvo)}\n")
        with tarfile.open(alvo) as tar:
            package.tarball_members_ok(tar)
            nomes = tar.getnames()
        self.assertIn(".bigbang/CHECKSUMS", nomes)
        self.assertIn(".bigbang/MIGRACAO.md", nomes)
        self.assertEqual(len(nomes), len(list(checksums.framework_files(self.raiz))) + 1)

    def test_recusa_framework_alterado(self):
        with open(os.path.join(self.raiz, ".bigbang", "AGENTS.base.md"), "a", encoding="utf-8") as arquivo:
            arquivo.write("mexido\n")
        with self.assertRaises(BbError):
            package.build(self.raiz, os.path.join(self.pasta, "a"))

    def test_recusa_entrada_suspeita(self):
        caminho = os.path.join(self.pasta, "mau.tar")
        with tarfile.open(caminho, "w") as tar:
            info = tarfile.TarInfo("../fora")
            tar.addfile(info)
        with tarfile.open(caminho) as tar, self.assertRaises(BbError):
            package.tarball_members_ok(tar)


class Migracao(unittest.TestCase):
    def test_secoes_entre_versoes(self):
        secoes = package.migration_between(MIGRACAO, "1.0.0", "1.1.0")
        self.assertEqual([s.split("]")[0] for s in secoes], ["## [1.0.1", "## [1.1.0"])
        self.assertEqual(package.manual_steps(secoes[0]), "")
        self.assertIn("Renomeie", package.manual_steps(secoes[1]))

    def test_migracao_do_framework_tem_a_versao_atual(self):
        texto = package.release_notes(RAIZ, framework_version(RAIZ))
        self.assertIn("### O que muda", texto)
        self.assertIn(package.MANUAL_HEADING, texto)

    def test_versoes_publicadas_sem_passo_manual(self):
        # Update this list when a version really needs the owner to act (major version, spec 5.7).
        with_steps = []
        with open(os.path.join(BIGBANG, "MIGRACAO.md"), encoding="utf-8") as arquivo:
            secoes = package.migration_sections(arquivo.read())
        for versao, texto in secoes.items():
            with self.subTest(versao=versao):
                self.assertEqual(bool(package.manual_steps(texto)), versao in with_steps)

    def test_toda_secao_tem_as_duas_partes(self):
        with open(os.path.join(BIGBANG, "MIGRACAO.md"), encoding="utf-8") as arquivo:
            secoes = package.migration_sections(arquivo.read())
        for versao, texto in secoes.items():
            with self.subTest(versao=versao):
                self.assertIn("### O que muda", texto)
                self.assertIn(package.MANUAL_HEADING, texto)


if __name__ == "__main__":
    unittest.main()
