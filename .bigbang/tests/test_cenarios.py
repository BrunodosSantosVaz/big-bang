"""Pronto quando do E3: the example configurations generate exactly the expected results."""
import os
import tempfile
import unittest

from _cenarios import NOMES, esperado, montar


class Cenarios(unittest.TestCase):
    def test_geracao_igual_ao_esperado(self):
        for cenario in NOMES:
            with self.subTest(cenario=cenario), tempfile.TemporaryDirectory() as pasta:
                plano = montar(cenario, os.path.join(pasta, "projeto"))
                previsto = esperado(cenario)
                self.assertTrue(previsto, "rode .bigbang/tests/atualizar_esperado.py")
                self.assertEqual(sorted(plano.expected), sorted(previsto))
                for caminho, conteudo in previsto.items():
                    self.assertEqual(plano.expected[caminho], conteudo, caminho)

    def test_cenarios_diferem_onde_devem(self):
        deploy, compilado = (esperado(nome) for nome in NOMES)
        self.assertIn("**Perfil de entrega:** `deploy` · **Alvo:** `vps-docker`", deploy["STACK.md"])
        self.assertIn("**Perfil de entrega:** `compilado`\n", compilado["STACK.md"])
        self.assertIn("# Instruções para IAs — Controle Fictício", compilado["AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
