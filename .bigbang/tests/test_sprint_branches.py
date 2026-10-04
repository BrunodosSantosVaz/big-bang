"""iniciar-sprint.sh and criar-branches.sh against the fake GitHub."""
import unittest

from test_bb_esteira import epico
from test_kanban_mesclar import ComBb

PRONTO = ["epic", "refinamento-aprovado", "sem-prototipo", "revisao-humana", "testes-revisao-ia"]
STRIDE = "S: x. T: x. R: x. I: x. D: x. E: x."


class IniciarSprint(ComBb):
    def setUp(self):
        super().setUp()
        self.estado["refs"] = {"heads/develop": "dev0", "heads/main": "main0"}
        self.gravar_estado()
        self.issue(7, "Bloquear pedido sem estoque", labels=PRONTO,
                   corpo=epico(**{"Análise de ameaças (STRIDE)": STRIDE}))
        self.cartao(1, 7, "Próxima sprint")

    def iniciar(self, **env):
        return self.rodar("iniciar-sprint.sh", env={"BB": self.bb, "DATA": "2026-10-05", **env})

    def criadas(self):
        return {int(n): i for n, i in self.ler_estado()["issues"].items() if int(n) != 7}

    def test_monta_o_epico(self):
        r = self.iniciar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        issues = self.criadas()
        titulos = {i["title"]: n for n, i in issues.items()}
        self.assertEqual(set(titulos), {"Testes de aceite · Bloquear pedido sem estoque", "Regra de estoque no domínio",
                                        "Endpoint de pedido", "Documentação · Bloquear pedido sem estoque"})
        teste = titulos["Testes de aceite · Bloquear pedido sem estoque"]
        t1, t2 = titulos["Regra de estoque no domínio"], titulos["Endpoint de pedido"]
        doc = titulos["Documentação · Bloquear pedido sem estoque"]
        for n in issues:
            with self.subTest(issue=n):  # inherited labels
                self.assertIn("revisao-humana", issues[n]["labels"])
                self.assertIn("testes-revisao-ia", issues[n]["labels"])
                self.assertEqual(issues[n]["parent"], 7)
                self.assertEqual(self.status(2, n), "A fazer")
                self.assertEqual(self.estado["boards"]["2"]["items"][str(n)]["Sprint"], "Sprint 1 · 2026-10-05")
                self.assertEqual(self.estado["boards"]["2"]["items"][str(n)]["Épico"], "#7")
        self.assertIn("CA-1", issues[teste]["body"])
        self.assertEqual(issues[t1]["blocked_by"], [teste])
        self.assertEqual(sorted(issues[t2]["blocked_by"]), sorted([teste, t1]))
        self.assertEqual(sorted(issues[doc]["blocked_by"]), sorted([t1, t2]))
        self.assertIn("heads/epico/7-bloquear-pedido-sem-estoque", self.estado["refs"])
        self.assertTrue(any(ref.startswith(f"heads/teste/{teste}-") for ref in self.estado["refs"]))
        self.assertEqual(self.status(1, 7), "Em desenvolvimento")

    def test_rodar_de_novo_nao_duplica(self):
        self.iniciar()
        antes = len(self.criadas())
        self.cartao(1, 7, "Próxima sprint")
        r = self.iniciar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.criadas()), antes)
        self.assertEqual(self.rodar("projeto.sh", "sprints", "2").stdout.count("Sprint 1 · 2026-10-05"), 1)

    def test_proxima_sprint_numera(self):
        self.iniciar()
        self.issue(8, "Outro", labels=PRONTO, corpo=epico(**{"Análise de ameaças (STRIDE)": STRIDE}))
        self.cartao(1, 8, "Próxima sprint")
        self.iniciar(DATA="2026-10-20")
        self.assertEqual(self.estado["boards"]["1"]["items"]["8"]["Sprint"], "Sprint 2 · 2026-10-20")

    def test_recusa_epico_fora_da_definition_of_ready(self):
        self.issue(7, "Sem refinamento", labels=["epic", "sem-prototipo"], corpo=epico())
        r = self.iniciar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("refinamento-aprovado", r.stdout)
        self.assertEqual(self.criadas(), {})
        self.assertEqual(self.status(1, 7), "Próxima sprint")

    def test_sem_epicos(self):
        self.cartao(1, 7, "Backlog")
        self.assertEqual(self.iniciar().returncode, 1)

    def test_simular_nao_cria(self):
        r = self.iniciar(SIMULAR="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[simulado]", r.stdout + r.stderr)
        self.assertEqual(self.criadas(), {})
        self.assertNotIn("heads/epico/7-bloquear-pedido-sem-estoque", self.estado["refs"])


class CriarBranches(IniciarSprint.__bases__[0]):
    def setUp(self):
        super().setUp()
        self.estado["refs"] = {"heads/develop": "dev0", "heads/epico/7-estoque": "ep0"}
        self.gravar_estado()
        self.issue(7, "Estoque", labels=["epic"], sub=[11, 12, 13, 14])
        self.issue(11, "Testes de aceite · Estoque", labels=["teste-aceite"], parent=7)
        self.issue(12, "Domínio", labels=["task"], parent=7, blocked_by=[11])
        self.issue(13, "API", labels=["task"], parent=7, blocked_by=[11, 12])
        self.issue(14, "Documentação · Estoque", labels=["documentacao"], parent=7, blocked_by=[12, 13])
        for n in (11, 12, 13, 14):
            self.cartao(2, n, "A fazer")

    def criar(self):
        r = self.rodar("criar-branches.sh", env={"BB": self.bb, "EPICO": "7"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def mesclar(self, head):
        prs = self.estado.setdefault("prs", {})
        prs[str(200 + len(prs))] = {"head": head, "base": "epico/7-estoque", "state": "MERGED"}
        self.gravar_estado()

    def branches(self):
        return sorted(ref[6:] for ref in self.ler_estado()["refs"] if ref.startswith("heads/") and
                      not ref.startswith(("heads/develop", "heads/epico/")))

    def test_ordem_teste_tarefas_documentacao(self):
        self.criar()
        self.assertEqual(self.branches(), ["teste/11-testes-de-aceite-estoque"])  # tasks wait for the test
        self.mesclar("teste/11-testes-de-aceite-estoque")
        self.criar()
        self.assertEqual(self.branches(), ["feature/12-dominio", "teste/11-testes-de-aceite-estoque"])
        self.assertEqual(self.status(2, 12), "Feature")
        self.assertEqual(self.status(2, 13), "A fazer")  # depends on 12
        self.mesclar("feature/12-dominio")
        self.criar()
        self.assertIn("feature/13-api", self.branches())
        self.assertNotIn("docs/14-documentacao-estoque", self.branches())
        self.mesclar("feature/13-api")
        self.criar()
        self.assertIn("docs/14-documentacao-estoque", self.branches())
        self.assertEqual(self.criar().stdout.strip().splitlines()[-1], "Branches criadas: 0.")  # idempotent


if __name__ == "__main__":
    unittest.main()
