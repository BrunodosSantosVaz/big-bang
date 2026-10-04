"""Pipeline rules (bb/pipeline.py): each rule accepts the right case and refuses the wrong one."""
import unittest

from _raiz import importar_bb

importar_bb()
from bb import pipeline as p  # noqa: E402


def epico(**campos):
    """Body as GitHub renders an issue form: '### <label>' followed by the answer."""
    padrao = {
        p.FIELD_PROBLEM: "Pedidos saem sem estoque.",
        p.FIELD_GOAL: "Bloquear pedido sem estoque.",
        p.FIELD_ARTIFACT: "Sim",
        p.FIELD_PROTOTYPE: "Não",
        p.FIELD_TEST_REVIEW: "IA",
        p.FIELD_PR_REVIEW: "IA",
        p.FIELD_DEPENDS: "_No response_",
        p.FIELD_SCOPE: "Dentro: pedidos. Fora: compras.",
        p.FIELD_RULES: "RN-0042 (nova)",
        p.FIELD_CRITERIA: "- CA-1: Dado um produto sem estoque, quando faço o pedido, então ele é recusado.\n"
                          "- CA-2: Dado estoque 1, quando peço 2, então o pedido é recusado.",
        p.FIELD_STRIDE: "_No response_",
        p.FIELD_RISKS: "_No response_",
        p.FIELD_TASKS: "- [ ] Regra de estoque no domínio\n- [ ] Endpoint de pedido (depende de: 1)",
    }
    padrao.update(campos)
    return "\n\n".join(f"### {campo}\n\n{valor}" for campo, valor in padrao.items())


PRONTO = ["refinamento-aprovado", "sem-prototipo"]


class Formulario(unittest.TestCase):
    def test_respostas_viram_labels(self):
        add, remove = p.form_label_changes(epico(**{p.FIELD_ARTIFACT: p.ARTIFACT_NO, p.FIELD_PROTOTYPE: "Sim",
                                                     p.FIELD_TEST_REVIEW: "Eu", p.FIELD_PR_REVIEW: "Eu",
                                                     p.FIELD_DEPENDS: "#12"}))
        self.assertEqual(add, {"sem-release", "com-prototipo", "testes-revisao-humana", "revisao-humana",
                               "tem-dependencia"})
        self.assertEqual(remove, {"sem-prototipo", "testes-revisao-ia", "revisao-ia"})

    def test_padroes_da_especificacao(self):
        add, remove = p.form_label_changes("### Problema ou oportunidade\n\nx")
        self.assertEqual(add, {"com-prototipo", "testes-revisao-ia", "revisao-ia"})
        self.assertIn("sem-release", remove)
        self.assertIn("tem-dependencia", remove)

    def test_edicao_so_aplica_o_que_mudou(self):
        antes = epico()
        depois = epico(**{p.FIELD_PROTOTYPE: "Sim", p.FIELD_PROBLEM: "texto novo"})
        self.assertEqual(p.form_label_changes(depois, antes), ({"com-prototipo"}, {"sem-prototipo"}))
        # editing only the text never reverts a review label changed by the AI or by the owner
        self.assertEqual(p.form_label_changes(epico(**{p.FIELD_PROBLEM: "outro"}), antes), (set(), set()))

    def test_dependencia_nao_cria_label_por_numero(self):
        add, _ = p.form_label_changes(epico(**{p.FIELD_DEPENDS: "#12 e #15"}))
        self.assertIn("tem-dependencia", add)
        self.assertFalse(any(label.startswith("#") or label.isdigit() for label in add))
        self.assertEqual(p.dependencies(epico(**{p.FIELD_DEPENDS: "#12 e #15"})), [12, 15])


class Bug(unittest.TestCase):
    def test_severidade(self):
        self.assertEqual(p.severity_label("### Severidade\n\ncrítica"), "severidade:critica")
        self.assertEqual(p.severity_label("### Severidade\n\nMédia"), "severidade:media")
        self.assertIsNone(p.severity_label("### Observado\n\nx"))


class DefinitionOfReady(unittest.TestCase):
    def test_epico_pronto(self):
        self.assertEqual(p.readiness_problems(epico(), PRONTO), [])

    def test_recusa_cada_falta(self):
        casos = {
            "sem refinamento": (epico(), ["sem-prototipo"], "refinamento-aprovado"),
            "protótipo não aprovado": (epico(), ["refinamento-aprovado", "com-prototipo"], "prototipo-aprovado"),
            "sem tarefas": (epico(**{p.FIELD_TASKS: "_No response_"}), PRONTO, "Tarefas previstas"),
            "sem critérios": (epico(**{p.FIELD_CRITERIA: "a definir"}), PRONTO, "CA-n"),
            "critério sem Dado/Quando/Então": (epico(**{p.FIELD_CRITERIA: "- CA-1: recusa pedido"}), PRONTO,
                                               "Dado/Quando/Então"),
            "sem escopo": (epico(**{p.FIELD_SCOPE: "_No response_"}), PRONTO, "Escopo"),
            "dependência inexistente": (epico(**{p.FIELD_TASKS: "- [ ] A (depende de: 3)"}), PRONTO, "inexistente"),
            "sensível sem STRIDE": (epico(), PRONTO + ["revisao-humana"], "STRIDE"),
            "resposta inválida": (epico(**{p.FIELD_PR_REVIEW: "Talvez"}), PRONTO, "resposta inválida"),
        }
        for nome, (corpo, labels, trecho) in casos.items():
            with self.subTest(caso=nome):
                problemas = p.readiness_problems(corpo, labels)
                self.assertTrue(any(trecho in problema for problema in problemas), problemas)

    def test_sensivel_com_stride_passa(self):
        corpo = epico(**{p.FIELD_STRIDE: "S: … T: … R: … I: … D: … E: …"})
        self.assertEqual(p.readiness_problems(corpo, PRONTO + ["revisao-humana"]), [])

    def test_tarefas_e_dependencias(self):
        corpo = epico(**{p.FIELD_TASKS: "1. Domínio\n- Tela\n* [x] API (depende de: 1, 2)\n\ntexto solto"})
        self.assertEqual(p.planned_tasks(corpo), [("Domínio", []), ("Tela", []), ("API", [1, 2])])


class Nomes(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(p.branch_name("feature", 12, "Bloquear pedido sem estoque!"),
                         "feature/12-bloquear-pedido-sem-estoque")
        self.assertEqual(p.slug("Ação " * 20), ("acao-" * 8).strip("-"))
        self.assertEqual(p.slug("!!!"), "tarefa")

    def test_modelo_de_branches(self):
        certos = [("feature/12-x", "epico/7-y"), ("teste/13-x", "epico/7-y"), ("docs/14-x", "epico/7-y"),
                  ("bugfix/20-x", "main"), ("hotfix/21-x", "main"), ("release/1.2.3", "main"),
                  ("epico/7-y", "develop"), ("epico/7-y", "release/1.2.0"), ("fundacao/2-f1", "develop"),
                  ("framework/v1.2.0", "develop"), ("sync/7-y", "epico/7-y"),
                  ("dependabot/github_actions/actions/checkout-7", "develop"),
                  ("dependabot/npm_and_yarn/lodash-4", "main")]
        for head, base in certos:
            with self.subTest(head=head, base=base):
                self.assertIsNone(p.branch_problem(head, base))
        errados = [("feature/12-x", "develop"), ("feature/12-x", "main"), ("bugfix/20-x", "develop"),
                   ("release/1.2.3", "develop"), ("sync/7-y", "epico/8-z"), ("minha-branch", "develop"),
                   ("feature/sem-numero", "epico/7-y"), ("Feature/12-X", "epico/7-y"),
                   ("dependabot/npm_and_yarn/lodash-4", "develop"), ("fundacao/2-f1", "main")]
        for head, base in errados:
            with self.subTest(head=head, base=base):
                self.assertIsNotNone(p.branch_problem(head, base))

    def test_issue_da_branch(self):
        self.assertEqual(p.branch_issue("teste/13-testes-do-epico"), ("teste", 13))
        self.assertEqual(p.branch_issue("release/1.0.0"), (None, None))

    def test_titulo_conventional(self):
        for certo in ("feat(pedidos): bloqueia pedido sem estoque", "fix: corrige total", "feat!: troca a API",
                      "chore(deps): atualiza ações"):
            with self.subTest(titulo=certo):
                self.assertIsNone(p.title_problem(certo))
        for errado in ("Bloqueia pedido", "feat:sem espaço", "feature: x", "feat(pedidos) x", ""):
            with self.subTest(titulo=errado):
                self.assertIsNotNone(p.title_problem(errado))


class Versao(unittest.TestCase):
    def test_classificacao(self):
        self.assertEqual(p.next_version("1.4.2", ["fix: a", "docs: b"]), "1.4.3")
        self.assertEqual(p.next_version("1.4.2", ["fix: a", "feat(x): b"]), "1.5.0")
        self.assertEqual(p.next_version("1.4.2", ["feat!: troca"]), "2.0.0")
        self.assertEqual(p.next_version("1.4.2", ["fix: a"], ["corpo\n\nBREAKING CHANGE: muda"]), "2.0.0")
        self.assertEqual(p.next_version("0.3.1", ["feat!: troca"]), "0.4.0")  # before 1.0, the middle one
        self.assertEqual(p.next_version("0.0.0", ["feat: primeira"]), "0.1.0")

    def test_versao_informada_confere(self):
        self.assertTrue(p.bump_kind("1.0.0", "1.1.0", ["feat: x"]))
        self.assertFalse(p.bump_kind("1.0.0", "1.0.1", ["feat: x"]))

    def test_arquivo_de_versao(self):
        self.assertEqual(p.with_version('{\n  "name": "x",\n  "version": "0.1.0"\n}\n', "1.2.3"),
                         '{\n  "name": "x",\n  "version": "1.2.3"\n}\n')
        self.assertEqual(p.with_version('__version__ = "0.1.0"\n', "0.2.0"), '__version__ = "0.2.0"\n')
        self.assertEqual(p.with_version('[project]\nversion = "2.0.0"\nrequires = "3.11.0"\n', "2.1.0"),
                         '[project]\nversion = "2.1.0"\nrequires = "3.11.0"\n')
        with self.assertRaises(ValueError):
            p.with_version("sem versão\n", "1.0.0")
        with self.assertRaises(ValueError):
            p.with_version('version = "1.0.0"', "1.0")


class Changelog(unittest.TestCase):
    ITENS = [(41, "feat(pedidos): bloqueia pedido sem estoque", []), (42, "fix: corrige total", []),
             (43, "fix(auth): limita tentativas de login", ["seguranca"]), (44, "docs: atualiza guia", []),
             (45, "refactor!: troca formato da API", [])]

    def test_secao_nova_com_rascunho(self):
        atual = p.CHANGELOG_HEADER + "\n### Adicionado\n\n- Relatório de estoque por loja\n\n## [0.1.0] - 2026-09-01\n\n- antigo\n"
        novo = p.changelog_with_release(atual, "0.2.0", "2026-10-03", self.ITENS)
        self.assertIn("## [Não publicado]\n\n## [0.2.0] - 2026-10-03\n\n### Adicionado\n\n"
                      "- Bloqueia pedido sem estoque (#41)\n- Relatório de estoque por loja\n", novo)
        self.assertIn("### Alterado\n\n- **Quebra de compatibilidade:** Troca formato da API (#45)", novo)
        self.assertIn("### Corrigido\n\n- Corrige total (#42)", novo)
        self.assertIn("### Segurança\n\n- Limita tentativas de login (#43)", novo)
        self.assertNotIn("atualiza guia", novo)
        self.assertTrue(novo.endswith("## [0.1.0] - 2026-09-01\n\n- antigo\n"))
        self.assertEqual(novo.count("Relatório de estoque por loja"), 1)  # draft moved, not copied

    def test_idempotente_e_arquivo_novo(self):
        novo = p.changelog_with_release(None, "1.0.0", "2026-10-03", self.ITENS[:1])
        self.assertTrue(novo.startswith("# Changelog\n"))
        self.assertEqual(p.changelog_with_release(novo, "1.0.0", "2026-10-03", self.ITENS), novo)
        self.assertTrue(p.changelog_has_version(novo, "1.0.0"))

    def test_so_manutencao(self):
        novo = p.changelog_with_release(None, "1.0.1", "2026-10-03", [(1, "build: atualiza dependências", [])])
        self.assertIn("Manutenção sem mudança visível", novo)


class Caminhos(unittest.TestCase):
    def test_artefato(self):
        padroes = ["src/", "migrations/", "Dockerfile", "packaging/**/*.py"]
        caminhos = ["src/a.py", "src/x/y.ts", "migrations/001.sql", "Dockerfile", "docs/a.md", "srcx/a.py",
                    "packaging/windows/build.py", "packaging/readme.md", "tests/test_a.py"]
        self.assertEqual(p.artifact_paths(caminhos, padroes),
                         ["src/a.py", "src/x/y.ts", "migrations/001.sql", "Dockerfile", "packaging/windows/build.py"])

    def test_zonas_sensiveis(self):
        zonas = ["src/**/auth/**", "migrations/**"]
        caminhos = ["src/app/auth/login.py", "src/auth/x.py", "src/pedidos/a.py", "migrations/1.sql",
                    ".github/workflows/meu.yml", "STACK.md", "docs/STACK.md", "package.json",
                    "web/package-lock.json", "requirements-dev.txt", "app.csproj", "tests/aceite/7-x/test_a.py",
                    "tests/unidade/test_a.py"]
        self.assertEqual(p.sensitive_paths(caminhos, zonas),
                         ["src/app/auth/login.py", "src/auth/x.py", "migrations/1.sql", ".github/workflows/meu.yml",
                          "STACK.md", "package.json", "web/package-lock.json", "requirements-dev.txt", "app.csproj",
                          "tests/aceite/7-x/test_a.py"])
        self.assertNotIn("tests/aceite/7-x/test_a.py",
                         p.sensitive_paths(caminhos, zonas, acceptance_allowed=True))


if __name__ == "__main__":
    unittest.main()
