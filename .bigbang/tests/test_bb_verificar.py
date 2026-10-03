"""`bb verificar` and CHECKSUMS (spec 5.1 and 15.5): each gate refuses the wrong case and accepts the right one."""
import contextlib
import io
import os
import shutil
import tempfile
import unittest

from _raiz import RAIZ, exemplo_toml, ignorar_para_copia, importar_bb

importar_bb()
from bb import checksums, cli, generator, verify, workflow_rules  # noqa: E402
from bb.errors import EXIT_OK, EXIT_VERIFICATION_FAILED  # noqa: E402

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
WORKFLOW_BOM = f"""name: X
on: push
permissions:
  contents: read
jobs:
  a:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@{SHA} # v7.0.1
      - uses: ./.github/actions/local
"""


def copiar_template(destino):
    shutil.copytree(RAIZ, destino, ignore=ignorar_para_copia("bigbang.toml", "STACK.md"))
    checksums.write(destino)  # the working copy may have uncommitted framework edits


def anexar(raiz, caminho, texto):
    with open(os.path.join(raiz, *caminho.split("/")), "a", encoding="utf-8") as arquivo:
        arquivo.write(texto)


class Verificar(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.pasta.name, "projeto")
        copiar_template(self.raiz)

    def tearDown(self):
        self.pasta.cleanup()

    def fundar(self):
        with open(os.path.join(self.raiz, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(exemplo_toml())
        shutil.copy(os.path.join(self.raiz, ".bigbang", "modelos", "STACK.md"), os.path.join(self.raiz, "STACK.md"))
        generator.apply(generator.build_plan(self.raiz, install_pipeline=True), self.raiz)

    def test_template_limpo_passa(self):
        self.assertEqual(verify.run(self.raiz), [])

    def test_editar_bloco_gerado_do_agents_md_reprova(self):
        texto = open(os.path.join(self.raiz, "AGENTS.md"), encoding="utf-8").read()
        with open(os.path.join(self.raiz, "AGENTS.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto.replace("Regras de ferro", "Regras flexíveis"))
        self.assertIn("AGENTS.md: " + verify.CHANGE_MESSAGES["alterar"], verify.run(self.raiz))

    def test_editar_secao_do_projeto_no_agents_md_passa(self):
        anexar(self.raiz, "AGENTS.md", "\n- Pegadinha nova do projeto.\n")
        self.assertEqual(verify.run(self.raiz), [])

    def test_editar_arquivo_gerado_da_esteira_reprova(self):
        self.fundar()
        self.assertEqual(verify.run(self.raiz), [])
        anexar(self.raiz, ".github/pull_request_template.md", "- [ ] item inventado\n")
        self.assertEqual(verify.run(self.raiz),
                         [".github/pull_request_template.md: " + verify.CHANGE_MESSAGES["alterar"]])

    def test_apagar_ou_sobrar_gerado_reprova(self):
        self.fundar()
        os.remove(os.path.join(self.raiz, ".github", "pull_request_template.md"))
        with open(os.path.join(self.raiz, ".github", "bb-sobra.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write("# Sobra\n")
        problemas = verify.run(self.raiz)
        # with no generated file left in .github/ except the stale one, the pipeline still counts as installed
        self.assertIn(".github/bb-sobra.md: " + verify.CHANGE_MESSAGES["remover"], problemas)
        self.assertIn(".github/pull_request_template.md: " + verify.CHANGE_MESSAGES["criar"], problemas)

    def test_editar_bloco_do_stack_md_reprova(self):
        self.fundar()
        caminho = os.path.join(self.raiz, "STACK.md")
        texto = open(caminho, encoding="utf-8").read()
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto.replace("- `migrations/**`\n", ""))
        self.assertIn("STACK.md: " + verify.CHANGE_MESSAGES["alterar"], verify.run(self.raiz))

    def test_stack_md_sem_tabela_de_dependencias_reprova(self):
        self.fundar()
        caminho = os.path.join(self.raiz, "STACK.md")
        texto = open(caminho, encoding="utf-8").read()
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto.replace("<!-- bb:dependencias:fim -->", ""))
        self.assertIn("STACK.md: o marcador <!-- bb:dependencias:fim --> precisa aparecer uma vez",
                      verify.run(self.raiz))

    def test_editar_framework_reprova(self):
        anexar(self.raiz, ".bigbang/processo/01-visao.md", "\nmudança\n")
        self.assertEqual(verify.run(self.raiz),
                         [".bigbang/processo/01-visao.md: alterado (o framework não pode ser editado no projeto)"])

    def test_arquivo_a_mais_no_framework_reprova(self):
        anexar(self.raiz, ".bigbang/padroes/meu.md", "# meu\n")
        self.assertEqual(verify.run(self.raiz), [".bigbang/padroes/meu.md: arquivo que não faz parte do framework"])

    def test_readme_e_licenca_movidos_pelo_init_passam(self):
        shutil.copy(os.path.join(self.raiz, "README.md"), os.path.join(self.raiz, ".bigbang", "README.md"))
        shutil.copy(os.path.join(self.raiz, "LICENSE"), os.path.join(self.raiz, ".bigbang", "LICENSE"))
        self.assertEqual(verify.run(self.raiz), [])

    def test_crlf_do_windows_passa(self):
        caminho = os.path.join(self.raiz, ".bigbang", "VERSION")
        texto = open(caminho, encoding="utf-8").read()
        with open(caminho, "w", encoding="utf-8", newline="\r\n") as arquivo:
            arquivo.write(texto)
        self.assertEqual(verify.run(self.raiz), [])

    def test_bigbang_toml_invalido_reprova(self):
        self.fundar()
        anexar(self.raiz, "bigbang.toml", "\n[extra]\n")
        self.assertTrue(any("seção desconhecida [extra]" in p for p in verify.run(self.raiz)))

    def test_workflow_fora_das_regras_reprova(self):
        with open(os.path.join(self.raiz, ".github", "workflows", "meu.yml"), "w", encoding="utf-8") as arquivo:
            arquivo.write("name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n")
        problemas = verify.run(self.raiz)
        self.assertIn(".github/workflows/meu.yml: falta `permissions:` no topo (permissão mínima declarada)", problemas)

    def test_codigos_de_saida_do_cli(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["--raiz", self.raiz, "verificar"]), EXIT_OK)
            anexar(self.raiz, ".bigbang/VERSION", "x")
            self.assertEqual(cli.main(["--raiz", self.raiz, "verificar"]), EXIT_VERIFICATION_FAILED)
            self.assertEqual(cli.main(["--raiz", self.raiz, "checksums"]), EXIT_VERIFICATION_FAILED)


class RegrasDeWorkflow(unittest.TestCase):
    def test_aceita_workflow_certo(self):
        self.assertEqual(workflow_rules.problems("w", WORKFLOW_BOM), [])

    def test_recusa_cada_erro(self):
        casos = {
            "sem SHA": WORKFLOW_BOM.replace(f"@{SHA} # v7.0.1", "@v7"),
            "sem comentário": WORKFLOW_BOM.replace(" # v7.0.1", ""),
            "runner móvel": WORKFLOW_BOM.replace("ubuntu-24.04", "ubuntu-latest"),
            "sem permissões": WORKFLOW_BOM.replace("permissions:\n  contents: read\n", ""),
            "write-all": WORKFLOW_BOM.replace("permissions:\n  contents: read\n", "permissions: write-all\n"),
            "pr target": WORKFLOW_BOM.replace("on: push", "on: pull_request_target").replace(
                "# v7.0.1", "# v7.0.1\n        with:\n          ref: ${{ github.event.pull_request.head.sha }}"),
        }
        for nome, texto in casos.items():
            with self.subTest(caso=nome):
                self.assertTrue(workflow_rules.problems("w", texto))

    def test_pull_request_target_sem_checkout_do_pr_passa(self):
        self.assertEqual(workflow_rules.problems("w", WORKFLOW_BOM.replace("on: push", "on: pull_request_target")),
                         [])


if __name__ == "__main__":
    unittest.main()
