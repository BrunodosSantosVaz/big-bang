"""faxina.sh: deletes merged branches whose work is over, reports what was left behind (pilot ScreenFakeCam: framework/*
and fundacao/* branches and local leftovers stayed after the publications)."""
import unittest

from test_integrar_publicar import ComGit


class Faxina(ComGit):
    def preparar(self):
        self.git("fetch", "-q", "origin")
        self.branch("framework/v1.0.0", "develop", "f.txt", "f\n")
        self.git("checkout", "-q", "-B", "develop", "origin/develop")
        self.git("merge", "-q", "--no-ff", "origin/framework/v1.0.0", "-m", "merge framework")
        self.git("push", "-q", "origin", "develop")
        self.git("checkout", "-q", "main")
        self.git("push", "-q", "origin", "main:fundacao/1-f0")  # contained in main
        self.git("push", "-q", "origin", "main:feature/12-feita")  # issue closed
        self.git("push", "-q", "origin", "main:epico/7-aberto")  # epic open: kept
        self.git("push", "-q", "origin", "main:epico/8-fechado")  # epic closed: deleted
        self.branch("feature/13-em-curso", "main", "x.txt", "x\n")  # not merged, issue open, recent: kept quietly
        self.branch("framework/v2.0.0", "develop", "g.txt", "g\n")  # open PR: kept
        self.git("push", "-q", "origin", "main:estranha")
        self.issue(7, "Épico aberto", labels=["epic"])
        self.issue(8, "Épico fechado", labels=["epic"], state="closed")
        self.issue(12, "Feita", labels=["task"], state="closed")
        self.issue(13, "Em curso", labels=["task"])
        self.estado["milestones"] = [{"number": 1, "title": "v0.1.0", "state": "closed"}]
        self.issue(20, "Esquecida", labels=["task"], milestone="v0.1.0")
        self.issue(21, "Com posse", labels=["task", "ia:claude-1"])
        self.estado["prs"] = {"40": {"head": "framework/v2.0.0", "base": "develop", "state": "OPEN", "title": "x",
                                     "createdAt": "2026-10-05T00:00:00Z"}}
        self.gravar_estado()

    def test_apaga_o_que_terminou_e_avisa_o_resto(self):
        self.preparar()
        r = self.script("faxina.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        apagadas = set(self.estado.get("apagadas", []))
        self.assertEqual(apagadas, {"framework/v1.0.0", "fundacao/1-f0", "feature/12-feita", "epico/8-fechado"})
        self.assertIn("estranha: branch fora do padrão", r.stdout)
        self.assertIn("#20 aberta no milestone v0.1.0", r.stdout)
        self.assertIn("posses abertas: #21", r.stdout)
        self.assertNotIn("feature/13-em-curso", r.stdout)

    def test_simular_nao_apaga(self):
        self.preparar()
        r = self.script("faxina.sh", SIMULAR="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[simulado] apagar framework/v1.0.0", r.stdout)
        self.assertFalse(self.estado.get("apagadas"))


if __name__ == "__main__":
    unittest.main()
