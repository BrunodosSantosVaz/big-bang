"""projeto.sh: cards, columns, text fields and the single-select Sprint field."""
import unittest

from _scripts import CasoDeScript


class ProjetoSh(CasoDeScript):
    def test_mover_cria_o_cartao_e_respeita_a_origem(self):
        self.issue(5, "Tarefa")
        r = self.rodar("projeto.sh", "mover", "2", "5", "A fazer", "-")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.status(2, 5), "A fazer")
        r = self.rodar("projeto.sh", "mover", "2", "5", "Code", "Feature")  # not from A fazer: kept
        self.assertIn("fora de [Feature]; mantido", r.stdout)
        self.assertEqual(self.status(2, 5), "A fazer")
        self.rodar("projeto.sh", "mover", "2", "5", "Feature", "A fazer|-")
        self.assertEqual(self.status(2, 5), "Feature")

    def test_coluna_inexistente_falha(self):
        self.issue(5)
        r = self.rodar("projeto.sh", "mover", "2", "5", "Homologação")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("não existe", r.stderr)

    def test_simular_nao_altera(self):
        self.issue(5)
        r = self.rodar("projeto.sh", "mover", "2", "5", "Code", env={"DRY_RUN": "1"})
        self.assertIn("[simulado]", r.stdout)
        self.assertIsNone(self.status(2, 5))

    def test_cartoes_so_deste_repositorio(self):
        for n in (5, 6, 7):
            self.issue(n)
        self.cartao(2, 5, "Pronto")
        self.cartao(2, 6, "Code")
        self.cartao(2, 7, "Pronto", _repo="outro/repo")
        self.assertEqual(self.rodar("projeto.sh", "cartoes", "2", "Pronto").stdout.split(), ["5"])

    def test_colunas_e_quadro(self):
        self.assertEqual(self.rodar("projeto.sh", "colunas", "3").stdout.splitlines()[0], "Novo")
        self.issue(5, "Tela de pedidos")
        self.issue(6, "Fechada", state="closed")
        self.cartao(2, 5, "Code", Sprint="Sprint 1 · 2026-10-05")
        self.cartao(2, 6, "Concluído")
        self.assertEqual(self.rodar("projeto.sh", "quadro", "2").stdout,
                         "Code\t5\tTela de pedidos\tSprint 1 · 2026-10-05\n")

    def test_campo_de_texto(self):
        self.issue(5)
        self.rodar("projeto.sh", "texto", "2", "5", "Épico", "#3")
        self.assertEqual(self.estado["boards"]["2"]["items"]["5"]["Épico"], "#3")

    def test_sprint_nova_preserva_as_existentes(self):
        self.issue(5)
        self.rodar("projeto.sh", "sprint-criar", "2", "Sprint 1 · 2026-10-05")
        self.rodar("projeto.sh", "sprint", "2", "5", "Sprint 1 · 2026-10-05")
        r = self.rodar("projeto.sh", "sprint-criar", "2", "Sprint 2 · 2026-10-20")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rodar("projeto.sh", "sprints", "2").stdout.splitlines(),
                         ["Sem sprint", "Sprint 1 · 2026-10-05", "Sprint 2 · 2026-10-20"])
        self.assertEqual(self.rodar("projeto.sh", "sprint-de", "2", "5").stdout, "Sprint 1 · 2026-10-05\n")
        self.assertIn("já existe", self.rodar("projeto.sh", "sprint-criar", "2", "Sprint 2 · 2026-10-20").stdout)

    def test_remover(self):
        self.issue(5)
        self.cartao(2, 5, "Code")
        self.rodar("projeto.sh", "remover", "2", "5")
        self.assertNotIn("5", self.estado["boards"]["2"]["items"])


if __name__ == "__main__":
    unittest.main()


class LabelsEColunas(unittest.TestCase):
    """The setup scripts carry exactly the labels of spec 11.2 and the columns of spec 11.1."""

    def test_labels_da_especificacao(self):
        import re
        from _raiz import ler
        nomes = re.findall(r'^\s+"([^|"]+)\|', ler(".bigbang", "scripts", "criar-labels.sh"), re.M)
        esperadas = {"epic", "task", "teste-aceite", "documentacao", "bug", "fundacao", "seguranca", "sem-release",
                     "com-prototipo", "sem-prototipo", "testes-revisao-ia", "testes-revisao-humana", "revisao-ia",
                     "revisao-humana", "refinamento-aprovado", "prototipo-aprovado", "testes-aprovados",
                     "teste-alterado-aprovado", "homologado", "reprovado", "dono:revisao-ia", "pr-aprovado",
                     "tem-dependencia", "conflito", "bloqueia-producao", "parada", "prioridade:alta",
                     "prioridade:media", "prioridade:baixa", "severidade:critica", "severidade:alta",
                     "severidade:media", "severidade:baixa", "hotfix", "dependencies", "good first issue",
                     "help wanted"}
        self.assertEqual(set(nomes), esperadas)
        self.assertEqual(len(nomes), len(set(nomes)))

    def test_colunas_da_especificacao(self):
        import re
        from _raiz import ler
        from _scripts import STATUS_BUGS, STATUS_EXECUCAO, STATUS_PLANEJAMENTO
        texto = ler(".bigbang", "scripts", "colunas.sh")
        for nome, esperado in (("PLANEJAMENTO", STATUS_PLANEJAMENTO), ("EXECUCAO", STATUS_EXECUCAO),
                               ("BUGS", STATUS_BUGS)):
            bloco = re.search(rf"COLUNAS_{nome}=\((.*?)\)", texto, re.S).group(1)
            with self.subTest(painel=nome):
                self.assertEqual(re.findall(r'"([^":]+):[A-Z]+"', bloco), esperado)
