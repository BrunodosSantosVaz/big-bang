"""publicar-producao.sh and promover.sh (compiled): the gate refuses each wrong case; the promotion publishes the
same bytes under the production name."""
import hashlib
import os
import subprocess

from _raiz import importar_bb

importar_bb()

from test_candidata import BaseCompilado
from test_kanban_mesclar import ComBb

from bb.checklist import ITEMS  # noqa: E402

CHECKLIST_OK = "\n".join(f"- [x] {item} — verificação: `nao-se-aplica: projeto fictício`" for item in ITEMS) + "\n"
VERDE = [{"name": "check", "status": "completed", "conclusion": "success"},
         {"name": "regras", "status": "completed", "conclusion": "success"}]


class PublicarEmProducao(BaseCompilado):
    def setUp(self):
        super().setUp()
        self.git("checkout", "-q", "-b", "release/0.2.0")
        self.escrever("src/app.js", "v2\n")
        self.escrever("CHANGELOG.md", "# Changelog\n\n## [Não publicado]\n\n## [0.2.0] - 2026-10-04\n\n### Adicionado\n\n"
                                      "- Saudação formal (#14)\n\n## [0.1.0] - 2026-09-01\n\n- início\n")
        self.escrever("docs/operacao/checklist-producao.md", CHECKLIST_OK)
        self.commit("chore(release): v0.2.0")
        self.git("commit", "-q", "--allow-empty", "-m", "Merge pull request #21 from dono/docs/13-documentacao")
        self.git("tag", "v0.2.0-rc.1")
        self.git("push", "-q", "origin", "release/0.2.0", "v0.2.0-rc.1")
        self.git("checkout", "-q", "main")
        sha = self.git("rev-parse", "release/0.2.0", saida=True)
        rc = os.path.join(self.pasta, "rc")
        os.makedirs(rc)
        self.binario = b"binario de verdade"
        with open(os.path.join(rc, "meu-sistema-v0.2.0-rc.1-linux-x64"), "wb") as arquivo:
            arquivo.write(self.binario)
        self.hash = hashlib.sha256(self.binario).hexdigest()
        with open(os.path.join(rc, "SHA256SUMS-linux-x64.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(f"{self.hash}  meu-sistema-v0.2.0-rc.1-linux-x64\n")
        self.estado.update({
            "milestones": [{"number": 1, "title": "v0.2.0", "state": "open"}],
            "prs": {"30": {"head": "release/0.2.0", "base": "main", "state": "OPEN", "sha": sha,
                           "title": "chore(release): v0.2.0"}},
            "checks": {sha: VERDE}, "releases": ["v0.2.0-rc.1"], "release_dirs": {"v0.2.0-rc.1": rc},
            "hooks": {"pr_merge": f"cd {self.trabalho} && git fetch -q origin && git checkout -q main && "
                                  "git merge -q --no-ff origin/release/0.2.0 -m 'chore(release): merge v0.2.0' && "
                                  "git push -q origin main"}})
        self.gravar_estado()
        self.issue(7, "Saudação", labels=["epic", "homologado"], milestone="v0.2.0")
        self.issue(13, "Documentação", labels=["documentacao"], milestone="v0.2.0")

    def publicar(self, **env):
        return self.script("publicar-producao.sh", VERSAO="0.2.0", **env)

    def test_publica_os_mesmos_bytes(self):
        r = self.publicar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.estado["prs"]["30"]["state"], "MERGED")
        self.assertEqual(sorted(self.estado["release_assets"]["v0.2.0"]),
                         ["SHA256SUMS-linux-x64.txt", "meu-sistema-v0.2.0-linux-x64"])
        info = self.estado["release_info"]["v0.2.0"]
        self.assertTrue(info["latest"])
        self.assertEqual(info["target"], self.git_origin("rev-parse", "main"))
        self.assertIn("chore(release): merge v0.2.0", self.git_origin("log", "-1", "--format=%s", "main"))
        self.assertEqual(self.estado["issues"]["7"]["state"], "closed")  # cleanup ran
        main = self.git_origin("rev-parse", "main")
        self.assertEqual(subprocess.run(["git", "--git-dir", self.origin, "merge-base", "--is-ancestor", main,
                                         "develop"]).returncode, 0)  # main returned to develop

    def test_mesmo_sha256_da_candidata(self):
        self.publicar()
        pasta = self.estado["release_dirs"]["v0.2.0"]
        with open(os.path.join(pasta, "meu-sistema-v0.2.0-linux-x64"), "rb") as arquivo:
            self.assertEqual(hashlib.sha256(arquivo.read()).hexdigest(), self.hash)
        with open(os.path.join(pasta, "SHA256SUMS-linux-x64.txt"), encoding="utf-8") as arquivo:
            self.assertEqual(arquivo.read(), f"{self.hash}  meu-sistema-v0.2.0-linux-x64\n")

    def test_simular_nao_muda_nada(self):
        r = self.publicar(SIMULAR="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Portão aprovado", r.stdout)
        self.assertEqual(self.estado["prs"]["30"]["state"], "OPEN")
        self.assertNotIn("v0.2.0", self.estado["releases"])

    def test_portao_recusa_cada_caso(self):
        casos = {
            "não homologado": lambda: self.issue(7, "Saudação", labels=["epic"], milestone="v0.2.0"),
            "reprovado": lambda: self.issue(7, "Saudação", labels=["epic", "homologado", "reprovado"],
                                            milestone="v0.2.0"),
            "bloqueia-produção": lambda: self.issue(40, "Falha", labels=["bug", "bloqueia-producao"]),
            "check vermelho": lambda: self.estado["checks"].update(
                {self.estado["prs"]["30"]["sha"]: [VERDE[0], {**VERDE[1], "conclusion": "failure"}]}),
            "conflito": lambda: self.estado["prs"]["30"].update(mergeable="CONFLICTING"),
            "sem PR": lambda: self.estado["prs"]["30"].update(state="CLOSED"),
            "achado de segurança alto": lambda: self.issue(41, "[Segurança] x",
                                                         labels=["bug", "seguranca", "severidade:alta"]),
        }
        for nome, estragar in casos.items():
            with self.subTest(caso=nome):
                self.setUp()
                estragar()
                self.gravar_estado()
                r = self.publicar(SIMULAR="true")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("RECUSADA", r.stdout)

    def test_release_mudou_depois_da_candidata(self):
        self.git("checkout", "-q", "release/0.2.0")
        self.escrever("src/app.js", "mudou\n")
        self.commit("fix: depois da candidata")
        self.git("push", "-q", "origin", "release/0.2.0")
        self.git("checkout", "-q", "main")
        r = self.publicar(SIMULAR="true")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mudou depois da candidata", r.stdout)

    def test_retomada_quando_ja_publicada(self):
        self.assertEqual(self.publicar().returncode, 0)
        r = self.publicar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("retomada", r.stdout)
        self.assertEqual(self.estado["releases"].count("v0.2.0"), 1)



class TarefaDeCorrecao(ComBb):
    def test_cria_a_tarefa_no_epico_reprovado(self):
        self.estado["refs"] = {"heads/epico/7-saudacao": "ep1"}
        self.gravar_estado()
        self.issue(7, "[Épico] Saudação", labels=["epic", "reprovado", "revisao-humana"], milestone="v0.2.0", sub=[11])
        self.issue(11, "Testes", labels=["teste-aceite"], parent=7)
        self.cartao(1, 7, "Em desenvolvimento", Sprint="Sem sprint")
        r = self.rodar("tarefa-de-correcao.sh", env={"BB": self.bb, "EPICO": "7",
                                                      "MOTIVO": "A vírgula sai antes do nome.\nVer captura."})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        nova = max(int(n) for n in self.estado["issues"])
        issue = self.estado["issues"][str(nova)]
        self.assertEqual(issue["title"], "Correção: A vírgula sai antes do nome.")
        self.assertEqual(set(issue["labels"]), {"task", "revisao-humana"})
        self.assertEqual(issue["milestone"], "v0.2.0")
        self.assertEqual(issue["parent"], 7)
        self.assertIn("A vírgula sai antes do nome.", issue["body"])
        self.assertEqual(self.status(2, nova), "Feature")
        self.assertIn(f"heads/feature/{nova}-correcao-a-virgula-sai-antes-do-nome", self.estado["refs"])

    def test_recusa_epico_nao_reprovado(self):
        self.issue(7, "Saudação", labels=["epic"])
        r = self.rodar("tarefa-de-correcao.sh", env={"BB": self.bb, "EPICO": "7", "MOTIVO": "x"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("não está reprovado", r.stdout)
