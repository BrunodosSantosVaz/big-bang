"""kanban.sh and mesclar-pr.sh against the fake GitHub."""
import os
import shutil
import sys
import unittest

from _raiz import BIGBANG, exemplo_toml
from _scripts import CasoDeScript

BB = os.path.join(BIGBANG, "bin", "bb.py")


def corpo_epico(prototipo="Não", testes="IA", prs="IA", artefato="Sim"):
    return (f"### Problema ou oportunidade\n\nx\n\n### Muda o artefato?\n\n{artefato}\n\n"
            f"### Precisa de protótipo?\n\n{prototipo}\n\n### Quem revisa os testes de aceite?\n\n{testes}\n\n"
            f"### Quem revisa os PRs?\n\n{prs}\n\n### Depende de outro épico ainda não publicado?\n\n_No response_")


class ComBb(CasoDeScript):
    def setUp(self):
        super().setUp()
        projeto = os.path.join(self.pasta, "projeto")
        os.makedirs(os.path.join(projeto, ".bigbang"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(projeto, ".bigbang", "VERSION"))
        with open(os.path.join(projeto, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(exemplo_toml())
        self.bb = f"{sys.executable} {BB} --raiz {projeto}"

    def kanban(self, **env):
        return self.rodar("kanban.sh", env={"BB": self.bb, **{k: str(v) for k, v in env.items()}})


class Kanban(ComBb):
    def test_epico_novo_vai_para_brainstorm_com_labels_do_formulario(self):
        self.issue(7, "Estoque", labels=["epic"], corpo=corpo_epico(prototipo="Sim", prs="Eu"))
        r = self.kanban(EVENT="issues", ACTION="opened", ISSUE=7)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status(1, 7), "Brainstorm")
        self.assertEqual(set(self.estado["issues"]["7"]["labels"]),
                         {"epic", "com-prototipo", "testes-revisao-ia", "revisao-humana"})

    def test_edicao_so_muda_o_que_mudou(self):
        self.issue(7, "Estoque", labels=["epic", "sem-prototipo", "testes-revisao-ia", "revisao-humana"],
                   corpo=corpo_epico(prototipo="Sim"))
        self.kanban(EVENT="issues", ACTION="edited", ISSUE=7, BODY_FROM=corpo_epico(prototipo="Não"))
        labels = set(self.estado["issues"]["7"]["labels"])
        self.assertIn("com-prototipo", labels)
        self.assertIn("revisao-humana", labels)  # the AI's switch to human review survives the edit

    def test_decisoes_do_dono_movem_o_epico(self):
        self.issue(7, "Estoque", labels=["epic", "com-prototipo"])
        self.cartao(1, 7, "Backlog Refinement")
        self.kanban(EVENT="issues", ACTION="labeled", ISSUE=7, LABEL="refinamento-aprovado")
        self.assertEqual(self.status(1, 7), "Validar protótipo")
        self.kanban(EVENT="issues", ACTION="labeled", ISSUE=7, LABEL="prototipo-aprovado")
        self.assertEqual(self.status(1, 7), "Próxima sprint")
        self.cartao(1, 7, "Homologação")
        self.kanban(EVENT="issues", ACTION="labeled", ISSUE=7, LABEL="reprovado")
        self.assertEqual(self.status(1, 7), "Em desenvolvimento")

    def test_sem_prototipo_vai_direto_para_proxima_sprint(self):
        self.issue(7, "Estoque", labels=["epic", "sem-prototipo"])
        self.cartao(1, 7, "Backlog")
        self.kanban(EVENT="issues", ACTION="labeled", ISSUE=7, LABEL="refinamento-aprovado")
        self.assertEqual(self.status(1, 7), "Próxima sprint")

    def test_bug_com_severidade(self):
        self.issue(20, "Total errado", labels=["bug"], corpo="### Severidade\n\nalta")
        self.kanban(EVENT="issues", ACTION="opened", ISSUE=20)
        self.assertEqual(self.status(3, 20), "Novo")
        self.assertIn("severidade:alta", self.estado["issues"]["20"]["labels"])

    def test_ciclo_de_uma_tarefa(self):
        self.issue(12, "Tarefa", labels=["task"])
        self.kanban(EVENT="issues", ACTION="opened", ISSUE=12)
        self.assertEqual(self.status(2, 12), "A fazer")
        self.kanban(EVENT="push", REF_NAME="feature/12-tarefa", CREATED="true")
        self.assertEqual(self.status(2, 12), "Feature")
        self.kanban(EVENT="push", REF_NAME="feature/12-tarefa", CREATED="false")
        self.assertEqual(self.status(2, 12), "Code")
        self.kanban(EVENT="pull_request", ACTION="opened", HEAD_REF="feature/12-tarefa", BASE_REF="epico/7-x")
        self.assertEqual(self.status(2, 12), "CI/PR")
        self.kanban(EVENT="pull_request", ACTION="closed", MERGED="false", HEAD_REF="feature/12-tarefa",
                    BASE_REF="epico/7-x")
        self.assertEqual(self.status(2, 12), "Code")
        self.cartao(2, 12, "CI/PR")
        self.kanban(EVENT="pull_request", ACTION="closed", MERGED="true", HEAD_REF="feature/12-tarefa",
                    BASE_REF="epico/7-x")
        self.assertEqual(self.status(2, 12), "Pronto")

    def test_ci_verde_com_revisao_humana_vai_para_validar_pr(self):
        self.issue(12, "Tarefa", labels=["task"])
        self.issue(30, "PR", labels=["revisao-humana"])
        self.cartao(2, 12, "CI/PR")
        self.kanban(EVENT="workflow_run", CONCLUSION="failure", HEAD_REF="feature/12-tarefa", PR_NUMBER=30)
        self.assertEqual(self.status(2, 12), "CI/PR")
        self.kanban(EVENT="workflow_run", CONCLUSION="success", HEAD_REF="feature/12-tarefa", PR_NUMBER=30)
        self.assertEqual(self.status(2, 12), "Validar PR")

    def test_ci_verde_com_revisao_ia_fica(self):
        self.issue(12, "Tarefa", labels=["task"])
        self.issue(30, "PR", labels=["revisao-ia"])
        self.cartao(2, 12, "CI/PR")
        self.kanban(EVENT="workflow_run", CONCLUSION="success", HEAD_REF="feature/12-tarefa", PR_NUMBER=30)
        self.assertEqual(self.status(2, 12), "CI/PR")


class Mesclar(ComBb):
    VERDE = [{"name": "check", "status": "completed", "conclusion": "success"},
             {"name": "regras", "status": "completed", "conclusion": "success"},
             {"name": "seguranca", "status": "completed", "conclusion": "success"}]

    def pr(self, numero=30, head="feature/12-tarefa", base="epico/7-estoque", labels=("pr-aprovado",),
           checks=None, sha="abc"):
        self.estado.setdefault("prs", {})[str(numero)] = {"head": head, "base": base, "labels": list(labels),
                                                          "sha": sha, "state": "OPEN"}
        self.estado["checks"][sha] = self.VERDE if checks is None else checks
        self.gravar_estado()

    def mesclar(self, numero=30, **env):
        return self.rodar("mesclar-pr.sh", env={"PR_NUMBER": str(numero), **env})

    def mesclado(self, numero=30):
        return self.ler_estado()["prs"][str(numero)]["state"] == "MERGED"

    def epico(self):
        self.issue(7, "Estoque", labels=["epic"], sub=[11, 12, 13])
        self.issue(11, "Testes", labels=["teste-aceite"], parent=7)
        self.issue(12, "Tarefa", labels=["task"], parent=7)
        self.issue(13, "Documentação", labels=["documentacao"], parent=7)

    def test_aprovado_e_verde_mescla(self):
        self.epico()
        self.pr()
        r = self.mesclar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.mesclado())
        self.assertIn("faltam 2 issue(s)", r.stdout)

    def test_espera_sem_aprovacao_ou_checks(self):
        casos = {"sem label": dict(labels=()), "check falhou": dict(checks=[
            {"name": "check", "status": "completed", "conclusion": "failure"}, self.VERDE[1]]),
            "check rodando": dict(checks=[{"name": "check", "status": "in_progress", "conclusion": None},
                                          self.VERDE[1]]),
            "check ausente": dict(checks=[self.VERDE[1]])}
        for nome, args in casos.items():
            with self.subTest(caso=nome):
                self.epico()
                self.pr(**args)
                r = self.mesclar()
                self.assertEqual(r.returncode, 0)
                self.assertIn("não será mesclado", r.stdout)
                self.assertFalse(self.mesclado())

    def test_nunca_na_main(self):
        self.pr(head="release/1.0.0", base="main")
        self.assertIn("só recebe releases", self.mesclar().stdout)
        self.assertFalse(self.mesclado())

    def test_develop_so_recebe_fundacao_framework_e_actions(self):
        self.pr(head="feature/12-tarefa", base="develop")
        self.assertIn("na develop só entram", self.mesclar().stdout)
        self.assertFalse(self.mesclado())
        self.pr(head="fundacao/3-f2", base="develop")
        self.mesclar()
        self.assertTrue(self.mesclado())

    def test_teste_com_revisao_humana_exige_testes_aprovados(self):
        self.epico()
        self.issue(11, "Testes", labels=["teste-aceite", "testes-revisao-humana"], parent=7)
        self.pr(head="teste/11-testes", labels=("pr-aprovado",))
        self.assertIn("falta a label testes-aprovados", self.mesclar().stdout)
        self.pr(head="teste/11-testes", labels=("testes-aprovados",))
        self.mesclar()
        self.assertTrue(self.mesclado())

    def test_ultimo_merge_dispara_integrar_release(self):
        self.epico()
        self.estado["prs"] = {"20": {"head": "teste/11-testes", "base": "epico/7-estoque", "state": "MERGED"},
                              "21": {"head": "docs/13-documentacao", "base": "epico/7-estoque", "state": "MERGED"}}
        self.gravar_estado()
        self.pr()
        r = self.mesclar()
        self.assertIn("Integrar release disparado", r.stdout)
        self.assertIn(["workflow", "run", "bb-integrar-release.yml", "--repo", "dono/repo", "-f", "epico=7", "-f",
                       "simular=false"], self.chamadas())

    def test_simular(self):
        self.epico()
        self.pr()
        self.assertIn("[simulado]", self.mesclar(SIMULAR="true").stdout)
        self.assertFalse(self.mesclado())


if __name__ == "__main__":
    unittest.main()
