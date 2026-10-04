"""Standards (spec section 8) and AGENTS.base.md (section 6.3) for epic E2.

"Pronto quando": every rule ID appears in the tracking table, and every verification cited either exists (a path in
the framework) or is marked with the epic that implements it.
"""
import os
import re
import unittest

from _raiz import BIGBANG, ler

PADROES = ["arquitetura", "seguranca", "codigo", "testes", "documentacao", "api", "dados", "frontend",
           "observabilidade"]

# Last finished epic of the roadmap: verifications of finished epics must point to a file, not to an epic.
ULTIMO_EPICO_CONCLUIDO = 4

# Number of rules per prefix, as listed in the spec (section 8).
QUANTIDADE = {"ARQ": 14, "SEG-IA": 5, "SEG": 24, "COD": 13, "TST": 12, "DOC": 14, "API": 7, "DAD": 10, "FE": 10,
              "OBS": 6}

CAMPOS = ["Regra", "Por quê", "Certo", "Errado", "Referência", "Verificação"]
TITULO_REGRA = re.compile(r"^### ((ARQ|SEG-IA|SEG|COD|TST|DOC|API|DAD|FE|OBS)-(\d+)) · \S.*$", re.M)
CITACAO = re.compile(r"\b(ARQ|SEG-IA|SEG|COD|TST|DOC|API|DAD|FE|OBS)-(\d{2})\b")
LINHA_TABELA = re.compile(r"^\| ((?:[A-Z]+-)+\d+) \| \[(\w+)\.md\]\(\2\.md\) \| (.+) \| (.+) \|$", re.M)
EPICO = re.compile(r"^E(\d+)$")
CAMINHO = re.compile(r"^`([^`]+)`$")
OBRIGACAO = re.compile(r"\b(DEVE|DEVEM|NÃO DEVE|NÃO DEVEM|DEVERIA|PODE)\b")


def regras(nome):
    """Return {rule_id: body} for one standards file."""
    texto = ler(".bigbang", "padroes", f"{nome}.md")
    marcas = list(TITULO_REGRA.finditer(texto))
    resultado = {}
    for atual, proxima in zip(marcas, marcas[1:] + [None]):
        fim = proxima.start() if proxima else len(texto)
        corpo = texto[atual.end():fim]
        corpo = corpo.split("\n## ", 1)[0]  # a following section (e.g. the production checklist) is not the rule
        resultado[atual.group(1)] = corpo
    return resultado


def campo(corpo, nome):
    achado = re.search(rf"^- \*\*{re.escape(nome)}:\*\* (.+?)(?=\n- \*\*|\n\n|\Z)", corpo, re.M | re.S)
    return " ".join(achado.group(1).split()) if achado else None


def todas_as_regras():
    return {rid: (nome, corpo) for nome in PADROES for rid, corpo in regras(nome).items()}


def tabela():
    texto = ler(".bigbang", "padroes", "README.md")
    return {m.group(1): (m.group(2), m.group(3).replace("\\|", "|"), m.group(4)) for m in LINHA_TABELA.finditer(texto)}


def prefixo(rid):
    return rid.rsplit("-", 1)[0]


class Regras(unittest.TestCase):
    def test_os_nove_arquivos(self):
        for nome in PADROES:
            with self.subTest(padrao=nome):
                self.assertTrue(os.path.isfile(os.path.join(BIGBANG, "padroes", f"{nome}.md")))

    def test_quantidade_e_numeracao_sem_buraco(self):
        por_prefixo = {}
        for rid in todas_as_regras():
            por_prefixo.setdefault(prefixo(rid), []).append(int(rid.rsplit("-", 1)[1]))
        self.assertEqual(set(por_prefixo), set(QUANTIDADE))
        for chave, numeros in por_prefixo.items():
            with self.subTest(prefixo=chave):
                self.assertEqual(numeros, list(range(1, QUANTIDADE[chave] + 1)))

    def test_cada_regra_tem_os_seis_campos(self):
        for rid, (_, corpo) in todas_as_regras().items():
            for nome in CAMPOS:
                with self.subTest(regra=rid, campo=nome):
                    self.assertTrue(campo(corpo, nome), "campo ausente ou vazio")

    def test_regra_usa_palavra_de_obrigacao(self):
        for rid, (_, corpo) in todas_as_regras().items():
            with self.subTest(regra=rid):
                self.assertRegex(campo(corpo, "Regra"), OBRIGACAO)

    def test_citacoes_apontam_para_regras_existentes(self):
        existentes = set(todas_as_regras())
        for nome in PADROES + ["README"]:
            texto = ler(".bigbang", "padroes", f"{nome}.md")
            for achado in CITACAO.finditer(texto):
                rid = f"{achado.group(1)}-{achado.group(2)}"
                with self.subTest(arquivo=nome, citacao=rid):
                    self.assertIn(rid, existentes)


class TabelaDeRastreio(unittest.TestCase):
    def test_toda_regra_esta_na_tabela_e_vice_versa(self):
        self.assertEqual(set(tabela()), set(todas_as_regras()))

    def test_linha_aponta_para_o_arquivo_e_a_verificacao_da_regra(self):
        linhas = tabela()
        for rid, (nome, corpo) in todas_as_regras().items():
            with self.subTest(regra=rid):
                arquivo, verificacao, _ = linhas[rid]
                self.assertEqual(arquivo, nome)
                self.assertEqual(verificacao, campo(corpo, "Verificação"))

    def test_verificacao_existe_ou_tem_epico(self):
        for rid, (_, _, implementada) in tabela().items():
            itens = [i.strip() for i in implementada.split(",")]
            for item in itens:
                with self.subTest(regra=rid, item=item):
                    epico, caminho = EPICO.match(item), CAMINHO.match(item)
                    self.assertTrue(epico or caminho, "use E<n> ou um caminho entre crases")
                    if epico:
                        self.assertTrue(ULTIMO_EPICO_CONCLUIDO < int(epico.group(1)) <= 12,
                                        "épico já concluído (aponte o arquivo) ou fora do roteiro")
                    if caminho:
                        raiz = os.path.dirname(BIGBANG)
                        self.assertTrue(os.path.exists(os.path.join(raiz, caminho.group(1))), "caminho inexistente")


class AgentsBase(unittest.TestCase):
    def test_texto_integral_da_secao_6_3(self):
        especificacao = ler(".bigbang", "docs", "especificacao.md")
        inicio = especificacao.index("````markdown\n", especificacao.index("### 6.3")) + len("````markdown\n")
        fim = especificacao.index("\n````", inicio)
        self.assertEqual(ler(".bigbang", "AGENTS.base.md"), especificacao[inicio:fim] + "\n")

    def test_marcadores_conhecidos(self):
        marcadores = set(re.findall(r"\{\{([a-z_.]+)\}\}", ler(".bigbang", "AGENTS.base.md")))
        self.assertEqual(marcadores, {"projeto.nome", "bigbang.versao"})

    def test_garantias_iguais_em_todos_os_lugares(self):
        seguranca = ler(".bigbang", "padroes", "seguranca.md")
        bloco = seguranca.split("<!-- bb:seg-ia:inicio -->\n", 1)[1].split("<!-- bb:seg-ia:fim -->", 1)[0]
        for arquivo in (("AGENTS.base.md",), ("AGENTS.inicial.md",)):
            with self.subTest(arquivo=arquivo[0]):
                self.assertIn(bloco, ler(".bigbang", *arquivo))


class AutoTeste(unittest.TestCase):
    def test_campo_ausente_e_detectado(self):
        corpo = "\n- **Regra:** O sistema DEVE x.\n- **Por quê:** y.\n"
        self.assertEqual(campo(corpo, "Regra"), "O sistema DEVE x.")
        self.assertIsNone(campo(corpo, "Certo"))

    def test_item_de_implementacao_invalido(self):
        self.assertIsNone(EPICO.match("E4 talvez"))
        self.assertIsNone(CAMINHO.match(".bigbang/x"))
        self.assertTrue(EPICO.match("E6"))

    def test_obrigacao_exigida(self):
        self.assertNotRegex("O sistema faz x.", OBRIGACAO)
        self.assertRegex("O sistema NÃO DEVE fazer x.", OBRIGACAO)


if __name__ == "__main__":
    unittest.main()
