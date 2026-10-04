"""Issue forms (spec 6.5): the epic form fields are exactly the headings the pipeline parses."""
import os
import re
import unittest

from _raiz import BIGBANG, importar_bb

importar_bb()
from bb import pipeline  # noqa: E402

FORMS = os.path.join(BIGBANG, "esteira", "nucleo", "arquivos", ".github", "ISSUE_TEMPLATE")


def rotulos(nome):
    with open(os.path.join(FORMS, nome), encoding="utf-8") as arquivo:
        texto = arquivo.read()
    return re.findall(r"^\s+label: (.+)$", texto, re.M), texto


class Formularios(unittest.TestCase):
    def test_epico_na_ordem_da_especificacao(self):
        campos, texto = rotulos("bb-epico.yml")
        self.assertEqual(campos, [pipeline.FIELD_PROBLEM, pipeline.FIELD_GOAL, pipeline.FIELD_ARTIFACT,
                                  pipeline.FIELD_PROTOTYPE, pipeline.FIELD_TEST_REVIEW, pipeline.FIELD_PR_REVIEW,
                                  pipeline.FIELD_DEPENDS, pipeline.FIELD_SCOPE, pipeline.FIELD_RULES,
                                  pipeline.FIELD_CRITERIA, pipeline.FIELD_STRIDE, pipeline.FIELD_RISKS,
                                  pipeline.FIELD_TASKS])
        self.assertIn('labels: ["epic"]', texto)

    def test_opcoes_dos_dropdowns_batem_com_as_regras(self):
        _, texto = rotulos("bb-epico.yml")
        for campo, (opcoes, padrao) in pipeline.DROPDOWNS.items():
            bloco = texto.split(f"label: {campo}", 1)[1].split("- type:", 1)[0]
            with self.subTest(campo=campo):
                self.assertEqual(re.findall(r'^\s+- "(.+)"$', bloco, re.M), list(opcoes))
                self.assertEqual(list(opcoes)[0], padrao)

    def test_label_de_cada_formulario(self):
        for nome, label in (("bb-bug.yml", "bug"), ("bb-tarefa.yml", "task"), ("bb-fundacao.yml", "fundacao"),
                            ("bb-teste-aceite.yml", "teste-aceite"), ("bb-documentacao.yml", "documentacao")):
            with self.subTest(formulario=nome):
                self.assertIn(f'labels: ["{label}"]', rotulos(nome)[1])

    def test_bug_avisa_que_comando_colado_nao_e_executado(self):
        self.assertIn("nunca são executados", rotulos("bb-bug.yml")[1])


if __name__ == "__main__":
    unittest.main()
