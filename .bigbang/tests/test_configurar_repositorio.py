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
        self.assertNotIn("BrokenPipe", r.stderr)  # nobody reads the request body in a simulation
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

    def rulesets_enviados(self):
        return [c["corpo"] for c in self.ler_estado().get("corpos", []) if c["rota"] == "repos/dono/repo/rulesets"]

    def test_checks_so_depois_da_esteira(self):
        r = self.configurar()
        self.assertIn("ainda não os checks", r.stdout)
        antes = self.rulesets_enviados()
        self.assertEqual(len(antes), 3)
        for ruleset in antes:  # GitHub refuses a rule type repeated in a ruleset (422): found by the pilot's F4
            tipos = [regra["type"] for regra in ruleset["rules"]]
            self.assertEqual(sorted(tipos), ["deletion", "non_fast_forward", "pull_request"])
        self.estado["corpos"] = []
        self.gravar_estado()
        os.makedirs(os.path.join(self.pasta, ".github", "workflows"))
        open(os.path.join(self.pasta, ".github", "workflows", "bb-ci.yml"), "w").close()
        r = self.configurar()
        self.assertNotIn("ainda não os checks", r.stdout)
        for ruleset in self.rulesets_enviados():
            tipos = [regra["type"] for regra in ruleset["rules"]]
            self.assertEqual(len(tipos), len(set(tipos)))
            self.assertIn("required_status_checks", tipos)
        self.assertNotIn("BrokenPipe", r.stderr)

    def test_scripts_de_montagem_recusam_repositorio_sem_dono(self):  # found by the pilot's F4
        for script, extra in (("configurar-repositorio.sh", ["--simular"]), ("criar-labels.sh", ["--simular"]),
                              ("criar-paineis.sh", ["Produto", "--simular"])):
            with self.subTest(script=script):
                r = self.rodar(script, "BrunodosSantosVaz", *extra, env={"BB": self.bb}, pasta=SETUP)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("dono/repo", r.stderr)

    def test_lista_so_os_segredos_que_faltam(self):  # found by the pilot: the token was created and still "pending"
        self.estado["segredos"] = ["PROJETO_TOKEN"]
        self.gravar_estado()
        r = self.configurar("--simular")
        self.assertNotIn("Pendente do dono (segredos)", r.stdout)
        self.assertIn("Segredos do dono: todos criados (PROJETO_TOKEN)", r.stdout)

    def test_compilado_pede_os_segredos_de_assinatura(self):
        toml = os.path.join(self.pasta, "projeto", "bigbang.toml")
        with open(toml, encoding="utf-8") as arquivo:
            texto = arquivo.read()
        texto = texto.replace('perfil = "deploy"', 'perfil = "compilado"').replace('alvo = "vps-docker"', 'alvo = ""')
        with open(toml, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        self.estado["segredos"] = ["PROJETO_TOKEN", "BB_ASSINATURA_ALIAS"]
        self.gravar_estado()
        r = self.configurar("--simular")
        self.assertIn("Pendente do dono (segredos): BB_ASSINATURA_ARQUIVO BB_ASSINATURA_SENHA (", r.stdout)

    def test_avisa_quando_o_plano_nao_aplica_a_aprovacao(self):
        self.estado["api"]["repos/dono/repo/environments/producao"] = {"protection_rules": []}
        self.gravar_estado()
        r = self.configurar()
        self.assertIn("o plano não aplicou a aprovação obrigatória", r.stdout)


if __name__ == "__main__":
    unittest.main()
