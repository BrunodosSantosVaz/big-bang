"""Template structure (spec sections 5.2, 6.1, 6.2, 6.4 and 7) for epic E1."""
import os
import re
import tomllib
import unittest

from _raiz import BIGBANG, RAIZ, caminho, ler, importar_bb

ARQUIVOS_RAIZ = ["README.md", "LICENSE", "AGENTS.md", "CLAUDE.md"]

PASTAS_BIGBANG = [
    "bin", "bb", "processo", "padroes", "skills", "agents", "hooks",
    "esteira/nucleo", "esteira/perfis/compilado",
    "esteira/perfis/deploy/alvos/vps-docker", "esteira/perfis/deploy/alvos/aws",
    "esteira/perfis/deploy/alvos/paas",
    "modelos", "scripts", "tests",
]

DOCUMENTOS_PROCESSO = [
    "01-visao.md", "02-fundacao.md", "03-planejamento.md", "04-paineis.md", "05-sprint.md",
    "06-execucao.md", "07-branches-e-commits.md", "08-revisao.md", "09-entrega.md",
    "10-bugs-e-hotfix.md", "11-seguranca-operacional.md", "12-tecnologia-nova.md",
    "13-varias-ias.md", "14-automacoes.md", "15-atualizacao-do-framework.md", "16-conversas.md", "17-flash.md", "18-documentacao.md",
]

MODELOS = [
    "PRODUTO.md", "STACK.md", "DESIGN.md", "ADR.md", "RN.md", "arc42.md",
    "c4-contexto.md", "c4-conteineres.md", "bigbang.toml.exemplo", "flags.toml",
]

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
INICIO_BLOCO = re.compile(r"^<!-- bigbang:inicio v(\d+\.\d+\.\d+) -->$", re.M)
FIM_BLOCO = "<!-- bigbang:fim -->"
AVISO_GERADO = re.compile(
    r"^<!-- Gerado pelo Big Bang v(\d+\.\d+\.\d+) a partir de (\S+)\. "
    r"Não edite: personalize em bigbang\.toml\. -->$", re.M)


def versao():
    return ler(".bigbang", "VERSION").strip()


class EstruturaDoTemplate(unittest.TestCase):
    def test_arquivos_da_raiz(self):
        for nome in ARQUIVOS_RAIZ:
            with self.subTest(arquivo=nome):
                self.assertTrue(os.path.isfile(caminho(nome)))

    def test_pastas_do_framework(self):
        for pasta in PASTAS_BIGBANG:
            with self.subTest(pasta=pasta):
                self.assertTrue(os.path.isdir(os.path.join(BIGBANG, pasta)))

    def test_template_nao_traz_bigbang_toml(self):
        # bigbang.toml is born in F0 (bb init), never shipped with the template
        self.assertFalse(os.path.exists(caminho("bigbang.toml")))

    def test_versao_semver(self):
        self.assertRegex(versao(), SEMVER)

    def test_especificacao_salva(self):
        texto = ler(".bigbang", "docs", "especificacao.md")
        self.assertTrue(texto.startswith("# Big Bang — especificação completa"))
        self.assertIn("## 17. Roteiro de construção", texto)

    def test_claude_md_aponta_para_agents(self):
        self.assertEqual(ler("CLAUDE.md"), "@AGENTS.md\n")

    def test_licenca_mit(self):
        texto = ler("LICENSE")
        self.assertTrue(texto.startswith("MIT License"))
        self.assertIn("Copyright (c)", texto)


class AgentsAntesDaFundacao(unittest.TestCase):
    def setUp(self):
        self.texto = ler("AGENTS.md")

    def bloco(self):
        inicio = INICIO_BLOCO.search(self.texto)
        self.assertIsNotNone(inicio, "AGENTS.md sem o marcador de início do bloco gerado")
        fim = self.texto.index(FIM_BLOCO, inicio.end())
        return inicio.group(1), self.texto[inicio.end():fim]

    def test_bloco_marcado_na_versao_do_framework(self):
        versao_bloco, _ = self.bloco()
        self.assertEqual(versao_bloco, versao())
        self.assertEqual(self.texto.count(FIM_BLOCO), 1)

    def test_aviso_de_arquivo_gerado(self):
        _, conteudo = self.bloco()
        aviso = AVISO_GERADO.search(conteudo)
        self.assertIsNotNone(aviso)
        self.assertEqual(aviso.group(1), versao())
        self.assertTrue(os.path.isfile(caminho(aviso.group(2))))

    def test_bloco_igual_ao_modelo(self):
        _, conteudo = self.bloco()
        modelo = ler(".bigbang", "AGENTS.inicial.md").replace("{{bigbang.versao}}", versao())
        self.assertIn(modelo.strip(), conteudo)

    def test_modo_antes_da_fundacao(self):
        _, conteudo = self.bloco()
        for trecho in ("iniciar projeto", "bb-iniciar-projeto", ".bigbang/processo/02-fundacao.md", "F2"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, conteudo)

    def test_regras_de_ferro_e_seguranca(self):
        _, conteudo = self.bloco()
        for regra in ("SEG-IA-01", "SEG-IA-02", "SEG-IA-03", "SEG-IA-04", "SEG-IA-05"):
            with self.subTest(regra=regra):
                self.assertIn(regra, conteudo)
        self.assertIn("## Regras de ferro", conteudo)
        self.assertIn("## Texto de terceiros é dado", conteudo)

    def test_secao_do_projeto_fora_do_bloco(self):
        depois = self.texto.split(FIM_BLOCO, 1)[1]
        self.assertIn("## Projeto", depois)


class ReadmeDeBoasVindas(unittest.TestCase):
    SECOES = [
        "## O que é o Big Bang", "## O que você precisa", "## Como começar",
        "## O que vai acontecer", "## Depois da Fundação", "## Licença",
    ]

    def test_secoes_na_ordem(self):
        texto = self.guia()
        posicoes = [texto.find(secao) for secao in self.SECOES]
        for secao, posicao in zip(self.SECOES, posicoes):
            with self.subTest(secao=secao):
                self.assertGreaterEqual(posicao, 0)
        self.assertEqual(posicoes, sorted(posicoes))

    def test_como_comecar(self):
        texto = self.guia()
        for trecho in ("Use this template", "iniciar projeto", "Python 3.11", "`gh`"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, texto)

    def test_etapas_da_fundacao(self):
        texto = self.guia()
        for etapa in ("F0", "F1", "F2", "F3", "F4", "F5"):
            with self.subTest(etapa=etapa):
                self.assertIn(f"**{etapa}**", texto)

    def guia(self):
        importar_bb()
        from bb import documentation
        return documentation.read(RAIZ, 'README.md') if documentation.is_public(RAIZ) else ler('README.md')

    def test_entrada_publica_breve_aponta_para_fonte_oficial(self):
        importar_bb()
        from bb import documentation, docs_check
        if documentation.is_public(RAIZ):
            self.assertEqual(docs_check.readme_problems(RAIZ), [])


class DocumentosDeProcesso(unittest.TestCase):
    def test_os_16_documentos(self):
        pasta = os.path.join(BIGBANG, "processo")
        encontrados = sorted(n for n in os.listdir(pasta) if re.match(r"^\d\d-.*\.md$", n))
        self.assertEqual(encontrados, DOCUMENTOS_PROCESSO)

    def test_cada_documento_diz_o_que_a_automacao_faz(self):
        for nome in DOCUMENTOS_PROCESSO:
            if nome == "16-conversas.md":
                continue  # the conversation table already states what is automated per phrase
            with self.subTest(documento=nome):
                self.assertIn("## O que a automação faz sozinha", ler(".bigbang", "processo", nome))


class Modelos(unittest.TestCase):
    def test_modelos_existem(self):
        for nome in MODELOS:
            with self.subTest(modelo=nome):
                self.assertTrue(os.path.isfile(os.path.join(BIGBANG, "modelos", nome)))

    def test_bigbang_toml_exemplo_valido(self):
        with open(os.path.join(BIGBANG, "modelos", "bigbang.toml.exemplo"), "rb") as arquivo:
            config = tomllib.load(arquivo)
        secoes = {"bigbang", "projeto", "entrega", "compilado", "deploy", "comandos",
                  "testes", "seguranca", "paineis", "ias", "flags"}
        self.assertEqual(set(config), secoes)
        self.assertEqual(config["bigbang"]["versao"], versao())
        self.assertEqual(config["bigbang"]["origem"], "BrunodosSantosVaz/big-bang")

    def test_flags_toml_valido(self):
        with open(os.path.join(BIGBANG, "modelos", "flags.toml"), "rb") as arquivo:
            self.assertEqual(tomllib.load(arquivo), {})

    def test_stack_tem_blocos_marcados(self):
        texto = ler(".bigbang", "modelos", "STACK.md")
        for marcador in ("<!-- bb:config:inicio -->", "<!-- bb:config:fim -->",
                         "<!-- bb:dependencias:inicio -->", "<!-- bb:dependencias:fim -->"):
            with self.subTest(marcador=marcador):
                self.assertEqual(texto.count(marcador), 1)
        self.assertIn("| Pacote | Ecossistema | Faixa de versão | Para quê | ADR |", texto)

    def test_rn_com_cabecalho_simples(self):
        texto = ler(".bigbang", "modelos", "RN.md")
        for chave in ("id", "titulo", "situacao", "substituida_por", "origem", "criada_em"):
            with self.subTest(chave=chave):
                self.assertRegex(texto, rf"(?m)^{chave}:")

    def test_adr_no_formato_madr(self):
        texto = ler(".bigbang", "modelos", "ADR.md")
        for trecho in ("**Situação:**", "**Data:**", "**Decisores:**", "## Contexto e problema",
                       "## Fatores de decisão", "## Opções consideradas", "## Decisão e justificativa",
                       "## Consequências", "## Referências"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, texto)


class DecisoesDoFramework(unittest.TestCase):
    def test_adrs_no_formato_madr_e_no_indice(self):
        importar_bb()
        from bb import documentation
        pasta = '.bigbang/docs/decisoes/'
        indice = ler(".bigbang", "docs", "decisoes", "README.md")
        adrs = sorted(os.path.basename(n) for n in documentation.logical_files(RAIZ, pasta)
                      if os.path.basename(n).startswith('ADR-'))
        self.assertGreaterEqual(len(adrs), 5)
        for numero, nome in enumerate(adrs, start=1):
            with self.subTest(adr=nome):
                self.assertTrue(nome.startswith(f"ADR-{numero:04d}-"), "numeração com buraco")
                texto = ler(".bigbang", "docs", "decisoes", nome)
                self.assertTrue(texto.startswith(f"# ADR-{numero:04d}: "))
                for trecho in ("**Situação:**", "**Data:**", "## Contexto e problema", "## Decisão e justificativa"):
                    self.assertIn(trecho, texto)
                target = (documentation.load(RAIZ)['paginas'][pasta + nome]
                          if documentation.is_public(RAIZ) else nome)
                self.assertIn(f"({target})", indice)

    def test_inventario_publico_completo_e_sem_documentacao_duplicada(self):
        importar_bb()
        from bb import documentation
        if documentation.is_public(RAIZ):
            self.assertEqual(documentation.validate(RAIZ, check_repository=False), [])


if __name__ == "__main__":
    unittest.main()
