"""configurar-repositorio.sh (Foundation F4, items 3, 4, 5 and 7) against the fake GitHub."""
import os
import shutil
import sys
import unittest

from _raiz import BIGBANG, exemplo_toml
from _scripts import SETUP, CasoDeScript

BB = os.path.join(BIGBANG, "bin", "bb.py")


class ConfigurarRepositorio(CasoDeScript):
    def setUp(self):
        super().setUp()
        projeto = os.path.join(self.pasta, "projeto")
        os.makedirs(os.path.join(projeto, ".bigbang"))
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(projeto, ".bigbang", "VERSION"))
        toml = (exemplo_toml().replace("planejamento = 0", "planejamento = 16").replace("execucao = 0", "execucao = 17")
                .replace("bugs = 0", "bugs = 18"))
        with open(os.path.join(projeto, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(toml)
        self.bb = f"{sys.executable} {BB} --raiz {projeto}"
        self.estado["api"] = {"users/BrunodosSantosVaz": {"id": 42},
                              "repos/dono/repo/environments/producao": {
                                  "protection_rules": [{"type": "required_reviewers"}]}}
        self.estado["comandos"] = {"variable set": "", "repo edit": ""}
        self.gravar_estado()

    def configurar(self, *extra):
        return self.rodar("configurar-repositorio.sh", "dono/repo", *extra, env={"BB": self.bb}, pasta=SETUP)

    def test_simular_nao_muda_nada(self):
        r = self.configurar("--simular")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[simulado] ruleset bb-epicos criado (refs/heads/epico/*)", r.stdout)
        self.assertFalse([c for c in self.chamadas() if "-X" in c and c[c.index("-X") + 1] in ("PUT", "POST", "PATCH")])

    def test_aplica_protecoes(self):
        r = self.configurar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        chamadas = self.chamadas()
        rulesets = [c for c in chamadas if c[:4] == ["api", "-X", "POST", "repos/dono/repo/rulesets"]]
        self.assertEqual(len(rulesets), 3)
        self.assertIn(["api", "-X", "PATCH", "repos/dono/repo", "-f",
                       "security_and_analysis[secret_scanning][status]=enabled", "-f",
                       "security_and_analysis[secret_scanning_push_protection][status]=enabled"], chamadas)
        self.assertIn(["variable", "set", "PROJETO_EXECUCAO", "--repo", "dono/repo", "--body", "17"], chamadas)
        self.assertTrue(any(c[:2] == ["repo", "edit"] and "--delete-branch-on-merge=false" in c for c in chamadas))
        self.assertIn("Pendente do dono (segredos): PROJETO_TOKEN", r.stdout)
        self.assertIn("staging", r.stdout)  # deploy profile

    def test_checks_so_depois_da_esteira(self):
        r = self.configurar()
        self.assertIn("ainda não os checks", r.stdout)
        corpo = [c for c in self.chamadas() if c[:4] == ["api", "-X", "POST", "repos/dono/repo/rulesets"]]
        self.assertTrue(corpo)
        os.makedirs(os.path.join(self.pasta, ".github", "workflows"))
        open(os.path.join(self.pasta, ".github", "workflows", "bb-ci.yml"), "w").close()
        self.assertNotIn("ainda não os checks", self.configurar().stdout)

    def test_avisa_quando_o_plano_nao_aplica_a_aprovacao(self):
        self.estado["api"]["repos/dono/repo/environments/producao"] = {"protection_rules": []}
        self.gravar_estado()
        r = self.configurar()
        self.assertIn("o plano não aplicou a aprovação obrigatória", r.stdout)


if __name__ == "__main__":
    unittest.main()
