"""`bb gerar`: rendering, layer composition, skills copies, marked blocks and stale files (spec 5.1, 5.5, 5.6)."""
import os
import re
import shutil
import tempfile
import unittest

from _raiz import exemplo_toml, importar_bb

importar_bb()
from bb import generator, render  # noqa: E402
from bb.errors import BbError  # noqa: E402

VERSAO = "0.3.0"


def escrever(raiz, caminho, conteudo):
    destino = os.path.join(raiz, *caminho.split("/"))
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def ler(raiz, caminho):
    with open(os.path.join(raiz, *caminho.split("/")), encoding="utf-8") as arquivo:
        return arquivo.read()


def config_toml(perfil="deploy", alvo="vps-docker"):
    texto = re.sub(r'(?m)^versao = "[^"]*"', f'versao = "{VERSAO}"', exemplo_toml())
    if perfil == "compilado":
        texto = texto.replace('perfil = "deploy"', 'perfil = "compilado"').replace('alvo = "vps-docker"', 'alvo = ""')
    else:
        texto = texto.replace('alvo = "vps-docker"', f'alvo = "{alvo}"')
    return texto


class FrameworkFalso(unittest.TestCase):
    """A minimal framework with one file per layer, to test composition without depending on real templates."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = self.pasta.name
        r = self.raiz
        escrever(r, ".bigbang/VERSION", VERSAO + "\n")
        escrever(r, ".bigbang/modelos/bigbang.toml.exemplo", config_toml())
        escrever(r, ".bigbang/modelos/AGENTS.projeto.md", "## Projeto\n\nDo projeto.\n")
        escrever(r, ".bigbang/AGENTS.inicial.md", "# Antes da Fundação\n\nBig Bang v{{bigbang.versao}}.\n")
        escrever(r, ".bigbang/AGENTS.base.md", "# Instruções — {{projeto.nome}}\n")
        escrever(r, ".bigbang/esteira/sempre/arquivos/.claude/agents/bb-revisor.md", "# Revisor\n")
        escrever(r, ".bigbang/esteira/nucleo/arquivos/.github/workflows/bb-ci.yml.tmpl",
                 "name: CI\n# {{projeto.slug}} ${{ github.ref }}\nsistemas: {{entrega.caminhos_artefato}}\n")
        escrever(r, ".bigbang/esteira/nucleo/arquivos/.github/bb-comum.md", "# Núcleo\n")
        escrever(r, ".bigbang/esteira/perfis/deploy/arquivos/.github/workflows/bb-candidata.yml", "name: deploy\n")
        escrever(r, ".bigbang/esteira/perfis/deploy/arquivos/.github/bb-comum.md", "# Substituído pelo perfil\n")
        escrever(r, ".bigbang/esteira/perfis/compilado/arquivos/.github/workflows/bb-candidata.yml",
                 "name: compilado\n")
        escrever(r, ".bigbang/esteira/perfis/deploy/alvos/vps-docker/arquivos/.github/bb-alvo.sh",
                 "#!/usr/bin/env bash\necho vps\n")
        escrever(r, ".bigbang/esteira/perfis/deploy/alvos/aws/arquivos/.github/bb-alvo.sh",
                 "#!/usr/bin/env bash\necho aws\n")
        # Installed contracts are part of the minimal framework; this fake AWS is implemented, unlike the reserve.
        target_contract = ('descricao = "Alvo de teste"\nsituacao = "implementado"\nartefatos = ["imagem"]\n'
                           'operacoes = ["publicar", "migrar", "saude", "voltar"]\nvariaveis = []\nsegredos = []\n')
        for name in ('vps-docker', 'aws'):
            escrever(r, f'.bigbang/esteira/perfis/deploy/alvos/{name}/alvo.toml', target_contract)
            escrever(r, f'.bigbang/esteira/perfis/deploy/alvos/{name}/scripts/alvo.sh', '#!/bin/bash\nexit 0\n')
        escrever(r, '.bigbang/esteira/perfis/deploy/artefatos/imagem/artefato.toml',
                 'descricao = "Imagem de teste"\nsituacao = "implementado"\nidentidade = "digest"\n'
                 '[scripts]\nconstruir = "script.sh"\ncandidata = "script.sh"\npromover = "script.sh"\n')
        escrever(r, '.bigbang/script.sh', '#!/bin/bash\nexit 0\n')
        escrever(r, ".bigbang/skills/README.md", "# Skills\n")
        escrever(r, ".bigbang/skills/bb-status/SKILL.md.tmpl",
                 "---\nname: bb-status\ndescription: Use quando…\n---\n\n# Status v{{bigbang.versao}}\n")

    def tearDown(self):
        self.pasta.cleanup()

    def fundar(self, perfil="deploy", alvo="vps-docker"):
        escrever(self.raiz, "bigbang.toml", config_toml(perfil, alvo))

    def gerar(self, esteira=False):
        plano = generator.build_plan(self.raiz, install_pipeline=esteira)
        generator.apply(plano, self.raiz)
        return plano

    def arquivos(self):
        resultado = set()
        for pasta, _, nomes in os.walk(self.raiz):
            for nome in nomes:
                caminho = os.path.relpath(os.path.join(pasta, nome), self.raiz).replace(os.sep, "/")
                if not caminho.startswith(".bigbang/"):
                    resultado.add(caminho)
        return resultado

    def test_antes_da_fundacao(self):
        self.gerar()
        self.assertEqual(self.arquivos(), {
            "AGENTS.md", ".claude/agents/bb-revisor.md",
            ".agents/skills/bb-status/SKILL.md", ".claude/skills/bb-status/SKILL.md"})
        agents = ler(self.raiz, "AGENTS.md")
        self.assertTrue(agents.startswith(f"<!-- bigbang:inicio v{VERSAO} -->\n"))
        self.assertIn("a partir de .bigbang/AGENTS.inicial.md", agents)
        self.assertIn(f"Big Bang v{VERSAO}.", agents)
        self.assertTrue(agents.endswith("<!-- bigbang:fim -->\n\n## Projeto\n\nDo projeto.\n"))

    def test_esteira_exige_fundacao(self):
        with self.assertRaises(BbError):
            self.gerar(esteira=True)

    def test_skills_em_duas_copias_iguais_com_aviso_depois_do_cabecalho(self):
        self.gerar()
        agentes = ler(self.raiz, ".agents/skills/bb-status/SKILL.md")
        self.assertEqual(agentes, ler(self.raiz, ".claude/skills/bb-status/SKILL.md"))
        self.assertTrue(agentes.startswith("---\nname: bb-status\n"))
        self.assertIn("---\n<!-- Gerado pelo Big Bang", agentes)
        self.assertIn(f"# Status v{VERSAO}", agentes)

    def test_composicao_deploy_vps_docker(self):
        self.fundar()
        self.gerar(esteira=True)
        self.assertIn(".github/workflows/bb-ci.yml", self.arquivos())
        self.assertIn("name: deploy", ler(self.raiz, ".github/workflows/bb-candidata.yml"))
        self.assertIn("# Substituído pelo perfil", ler(self.raiz, ".github/bb-comum.md"))
        alvo = ler(self.raiz, ".github/bb-alvo.sh")
        self.assertTrue(alvo.startswith("#!/usr/bin/env bash\n# Gerado pelo Big Bang"))
        self.assertIn("echo vps", alvo)
        ci = ler(self.raiz, ".github/workflows/bb-ci.yml")
        self.assertTrue(ci.startswith(f"# Gerado pelo Big Bang v{VERSAO} a partir de "
                                      ".bigbang/esteira/nucleo/arquivos/.github/workflows/bb-ci.yml.tmpl."))
        self.assertIn("# meu-sistema ${{ github.ref }}", ci)
        self.assertIn('sistemas: ["src/", "migrations/", "Dockerfile", "package.json", "package-lock.json"]', ci)
        self.assertIn("a partir de .bigbang/AGENTS.base.md", ler(self.raiz, "AGENTS.md"))
        self.assertIn("# Instruções — Meu Sistema", ler(self.raiz, "AGENTS.md"))

    def test_composicao_compilado_sem_alvo(self):
        self.fundar("compilado")
        self.gerar(esteira=True)
        self.assertIn("name: compilado", ler(self.raiz, ".github/workflows/bb-candidata.yml"))
        self.assertNotIn(".github/bb-alvo.sh", self.arquivos())

    def test_troca_de_alvo_remove_e_cria(self):
        self.fundar()
        self.gerar(esteira=True)
        self.fundar(alvo="aws")
        self.gerar()  # already installed: no flag needed
        self.assertIn("echo aws", ler(self.raiz, ".github/bb-alvo.sh"))
        self.fundar("compilado")
        plano = self.gerar()
        self.assertIn(".github/bb-alvo.sh", plano.stale)
        self.assertNotIn(".github/bb-alvo.sh", self.arquivos())

    def test_segunda_geracao_nao_muda_nada(self):
        self.fundar()
        self.gerar(esteira=True)
        self.assertEqual(generator.changes(generator.build_plan(self.raiz), self.raiz), [])

    def test_remove_ci_do_framework_ao_instalar_a_esteira(self):
        escrever(self.raiz, ".github/workflows/bb-framework-ci.yml", "name: x\n")
        self.gerar()
        self.assertIn(".github/workflows/bb-framework-ci.yml", self.arquivos())  # template: kept
        self.fundar()
        self.gerar(esteira=True)
        self.assertNotIn(".github/workflows/bb-framework-ci.yml", self.arquivos())

    def test_nao_toca_arquivos_do_projeto(self):
        escrever(self.raiz, ".github/workflows/meu-deploy.yml", "name: meu\n")
        escrever(self.raiz, ".agents/skills/minha-skill/SKILL.md", "---\nname: minha-skill\n---\n")
        self.fundar()
        self.gerar(esteira=True)
        self.assertIn(".github/workflows/meu-deploy.yml", self.arquivos())
        self.assertIn(".agents/skills/minha-skill/SKILL.md", self.arquivos())

    def test_bloco_inserido_em_agents_md_existente(self):
        escrever(self.raiz, "AGENTS.md", "# Meu AGENTS\n")
        self.gerar()
        agents = ler(self.raiz, "AGENTS.md")
        self.assertTrue(agents.startswith("<!-- bigbang:inicio"))
        self.assertTrue(agents.endswith("<!-- bigbang:fim -->\n\n# Meu AGENTS\n"))
        self.fundar()
        self.gerar()
        self.assertEqual(ler(self.raiz, "AGENTS.md").count("<!-- bigbang:inicio"), 1)

    def test_dois_blocos_no_agents_md(self):
        bloco = "<!-- bigbang:inicio v0.1.0 -->\nx\n<!-- bigbang:fim -->\n"
        escrever(self.raiz, "AGENTS.md", bloco + bloco)
        with self.assertRaises(BbError):
            generator.build_plan(self.raiz)

    def test_bloco_do_stack_md(self):
        self.fundar()
        escrever(self.raiz, "STACK.md", "# Stack\n\n<!-- bb:config:inicio -->\nvelho\n<!-- bb:config:fim -->\n\nfim\n")
        self.gerar()
        stack = ler(self.raiz, "STACK.md")
        self.assertNotIn("velho", stack)
        self.assertIn("- `src/**/auth/**`", stack)
        self.assertTrue(stack.endswith("<!-- bb:config:fim -->\n\nfim\n"))
        escrever(self.raiz, "STACK.md", "# Stack sem bloco\n")
        with self.assertRaises(BbError):
            generator.build_plan(self.raiz)

    def test_camada_sempre_nao_escreve_em_github(self):
        escrever(self.raiz, ".bigbang/esteira/sempre/arquivos/.github/bb-x.md", "# x\n")
        with self.assertRaises(BbError):
            generator.build_plan(self.raiz)

    def test_skill_sem_prefixo_bb(self):
        escrever(self.raiz, ".bigbang/skills/status/SKILL.md", "---\nname: status\n---\n")
        with self.assertRaises(BbError):
            generator.build_plan(self.raiz)

    def test_simular_nao_grava(self):
        plano = generator.build_plan(self.raiz)
        self.assertTrue(generator.changes(plano, self.raiz))
        self.assertIn("+<!-- bigbang:inicio", generator.diff(plano, self.raiz, "AGENTS.md"))
        self.assertEqual(self.arquivos(), set())


class Render(unittest.TestCase):
    def test_marcadores(self):
        contexto = {"projeto": {"nome": "X", "lista": ["a", "b"], "ativo": True, "n": 3},
                    "compilado": {"build_linux-x64": "make"}}
        texto = "{{projeto.nome}} {{projeto.lista}} {{projeto.ativo}} {{projeto.n}} {{compilado.build_linux-x64}}"
        self.assertEqual(render.substitute(texto, contexto, "t"), 'X ["a", "b"] true 3 make')

    def test_expressao_do_github_actions_nao_e_marcador(self):
        self.assertEqual(render.substitute("${{github.ref}} ${{ github.sha }}", {}, "t"),
                         "${{github.ref}} ${{ github.sha }}")

    def test_marcador_sem_valor(self):
        with self.assertRaises(BbError) as contexto:
            render.substitute("{{projeto.nada}}", {"projeto": {}}, "modelo.tmpl")
        self.assertIn("modelo.tmpl", contexto.exception.message)
        self.assertIn("projeto.nada", contexto.exception.message)

    def test_aviso_por_tipo(self):
        self.assertTrue(render.add_notice("x\n", "a.yml", "1.0.0", "s").startswith("# Gerado pelo Big Bang v1.0.0"))
        self.assertTrue(render.add_notice("x\n", "a.md", "1.0.0", "s").startswith("<!-- Gerado pelo Big Bang"))
        self.assertEqual(render.add_notice("{}\n", "settings.json", "1.0.0", "s"), "{}\n")
        com_shebang = render.add_notice("#!/bin/sh\necho\n", "x", "1.0.0", "s")
        self.assertTrue(com_shebang.startswith("#!/bin/sh\n# Gerado"))
        with self.assertRaises(BbError):
            render.add_notice("x", "imagem.png", "1.0.0", "s")

    def test_reconhece_aviso(self):
        self.assertTrue(render.has_notice(render.add_notice("x\n", "a.yml", "1.0.0", "s")))
        self.assertFalse(render.has_notice("# Gerado por outra ferramenta\n"))


class RepositorioDoBigBang(unittest.TestCase):
    """The template itself must be exactly what `bb gerar` produces."""

    def test_template_em_dia(self):
        from _raiz import RAIZ, ignorar_para_copia
        with tempfile.TemporaryDirectory() as pasta:
            copia = os.path.join(pasta, "copia")
            shutil.copytree(RAIZ, copia, ignore=ignorar_para_copia())
            if os.path.exists(os.path.join(copia, "bigbang.toml")):
                self.skipTest("cópia de trabalho com bigbang.toml")
            self.assertEqual(generator.changes(generator.build_plan(copia), copia), [])


if __name__ == "__main__":
    unittest.main()
