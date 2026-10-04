"""Traceability (RN <-> acceptance tests) and the stack guard: each gate refuses the wrong case and accepts the
right one."""
import os
import shutil
import tempfile
import unittest

from _raiz import importar_bb

importar_bb()
from bb import stack_guard, traceability  # noqa: E402

PY = r"def test_"
JS = r"(it|test)\("


def rn(numero, situacao="vigente"):
    return f"id: RN-{numero}\ntitulo: x\nsituacao: {situacao}\nsubstituida_por:\norigem: \"#7\"\n\n## Descrição\n"


class Projeto(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz)

    def escrever(self, caminho, texto):
        destino = os.path.join(self.raiz, *caminho.split("/"))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)


class Rastreabilidade(Projeto):
    def test_tudo_rastreado(self):
        self.escrever("docs/negocio/regras/RN-0042-bloqueia.md", rn("0042"))
        self.escrever("docs/negocio/regras/RN-0040-antiga.md", rn("0040", "substituida"))
        self.escrever("tests/aceite/7-e/test_a.py", "def test_rn0042_bloqueia_pedido(self):\n    pass\n")
        self.escrever("tests/aceite/7-e/a.test.js", 'it("RN-0042 bloqueia", () => {});\n')
        self.assertEqual(traceability.problems(self.raiz, PY), [])
        self.assertEqual(traceability.problems(self.raiz, JS), [])

    def test_recusa_cada_falha(self):
        self.escrever("docs/negocio/regras/RN-0042-bloqueia.md", rn("0042"))
        self.escrever("tests/aceite/7-e/test_a.py", "def test_bloqueia_pedido(self):\n    pass\n"
                                                    "def test_rn0099_inexistente(self):\n    pass\n")
        problemas = traceability.problems(self.raiz, PY, ["docs/negocio/regras/RN-0041-apagada.md"])
        self.assertTrue(any("sem o ID de uma regra" in p for p in problemas))
        self.assertTrue(any("cita RN-0099, que não existe" in p for p in problemas))
        self.assertTrue(any("RN-0042 está vigente e nenhum teste" in p for p in problemas))
        self.assertTrue(any("RN-0041-apagada.md: regra de negócio apagada" in p for p in problemas))

    def test_projeto_sem_regras_nem_testes(self):
        self.assertEqual(traceability.problems(self.raiz, PY), [])

    def test_citacao_nao_confunde_palavras(self):
        self.escrever("docs/negocio/regras/RN-0042-x.md", rn("0042"))
        self.escrever("tests/aceite/7-e/test_a.py", "def test_turn0042(self):\n    pass\n")
        self.assertTrue(any("sem o ID" in p for p in traceability.problems(self.raiz, PY)))


STACK = """# Stack

<!-- bb:dependencias:inicio -->
| Pacote | Ecossistema | Faixa de versão | Para quê | ADR |
| --- | --- | --- | --- | --- |
| express | npm | ^4.21 | API | ADR-0001 |
| Django | PyPI | >=5,<6 | web | ADR-0001 |
| github.com/go-chi/chi/v5 | go | v5 | rotas | ADR-0001 |
| serde | cargo | 1 | json | ADR-0001 |
| org.postgresql:postgresql | maven | 42 | banco | ADR-0001 |
| monolog/monolog | composer | 3 | log | ADR-0001 |
| Dapper | nuget | 2 | dados | ADR-0001 |
<!-- bb:dependencias:fim -->
"""


class GuardaDaStack(Projeto):
    def setUp(self):
        super().setUp()
        self.escrever("STACK.md", STACK)

    def test_dependencias_aprovadas_em_cada_ecossistema(self):
        self.escrever("package.json", '{"dependencies": {"express": "^4.21.0"}, "devDependencies": {"jest": "29"}}')
        self.escrever("pyproject.toml", '[project]\nname = "x"\ndependencies = ["django>=5.0"]\n')
        self.escrever("requirements-dev.txt", "pytest==8\n")
        self.escrever("go.mod", "module x\n\nrequire (\n\tgithub.com/go-chi/chi/v5 v5.0.0\n\tgolang.org/x/sys v0.1.0 // indirect\n)\n")
        self.escrever("Cargo.toml", '[dependencies]\nserde = "1"\n\n[dev-dependencies]\ntokio-test = "0.4"\n')
        self.escrever("pom.xml", "<project><dependencies><dependency><groupId>org.postgresql</groupId>"
                                 "<artifactId>postgresql</artifactId></dependency><dependency><groupId>junit</groupId>"
                                 "<artifactId>junit</artifactId><scope>test</scope></dependency></dependencies></project>")
        self.escrever("composer.json", '{"require": {"php": "^8.3", "ext-json": "*", "monolog/monolog": "^3"}}')
        self.escrever("app/App.csproj", '<Project><ItemGroup><PackageReference Include="Dapper" Version="2" />'
                                        '</ItemGroup></Project>')
        self.escrever("node_modules/x/package.json", '{"dependencies": {"qualquer": "1"}}')  # ignored
        self.assertEqual(stack_guard.problems(self.raiz), [])

    def test_recusa_dependencia_nova(self):
        self.escrever("package.json", '{"dependencies": {"express": "4", "left-pad": "1"}}')
        self.escrever("requirements.txt", "requests==2.32\n")
        problemas = stack_guard.problems(self.raiz)
        self.assertEqual(len(problemas), 2)
        self.assertTrue(any("left-pad (npm)" in p for p in problemas))
        self.assertTrue(any("requests (pypi)" in p for p in problemas))

    def test_ecossistema_nao_suportado_falha_explicitamente(self):
        self.escrever("Gemfile", "gem 'rails'\n")
        self.assertTrue(any("não suportado" in p for p in stack_guard.problems(self.raiz)))

    def test_antes_da_stack(self):
        os.remove(os.path.join(self.raiz, "STACK.md"))
        self.assertEqual(stack_guard.problems(self.raiz), [])
        self.escrever("package.json", '{"dependencies": {"express": "4"}}')
        self.assertTrue(any("Fundação F2" in p for p in stack_guard.problems(self.raiz)))

    def test_nomes_python_normalizados(self):
        self.escrever("requirements.txt", "django_extensions==3\n")
        self.escrever("STACK.md", STACK.replace("| Django | PyPI |", "| django-extensions | pypi |"))
        self.assertEqual(stack_guard.problems(self.raiz), [])


if __name__ == "__main__":
    unittest.main()
