"""Ownership gates and two independent CLI processes over a shared GitHub fake and real Git worktrees."""
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from _raiz import BIGBANG
from test_decisao_revisao import ComCli
from test_integrar_publicar import ComGit

sys.path.insert(0, BIGBANG)
from bb import config, ownership, workspaces  # noqa: E402
from bb.errors import BbError, EXIT_INVALID_STATE, EXIT_USAGE  # noqa: E402


class Posse(ComCli):
    def setUp(self):
        super().setUp()
        self.config = config.load(self.projeto)
        self.config["ias"]["espera_confirmacao_segundos"] = 0
        self.issue(12, "Tarefa", labels=["task"])

    def assumir(self, number=12, name="claude-1"):
        try:
            return ownership.claim(self.config, number, name)
        finally:
            self.ler_estado()

    def test_assume_libera_e_preserva_historico(self):
        receipt = self.assumir()
        self.ler_estado()
        self.assertIn("ia:claude-1", self.estado["issues"]["12"]["labels"])
        ownership.release(self.config, 12, receipt["name"], receipt["session"])
        self.ler_estado()
        self.assertNotIn("ia:claude-1", self.estado["issues"]["12"]["labels"])
        self.assertIn("bb:liberada", self.estado["comments"]["12"][0])
        self.assumir(name="codex-1")

    def test_recusa_nome_issue_fechada_e_posse_existente(self):
        with self.assertRaises(BbError) as invalid:
            self.assumir(name="desconhecida")
        self.assertEqual(invalid.exception.code, EXIT_USAGE)
        self.issue(12, "Tarefa", state="closed")
        with self.assertRaises(BbError):
            self.assumir()
        self.issue(12, "Tarefa", labels=["ia:claude-2"])
        with self.assertRaisesRegex(BbError, "claude-2"):
            self.assumir()

    def test_limite_e_comentario_sem_label_ainda_bloqueiam(self):
        self.assumir()
        self.issue(13, "Outra tarefa")
        with self.assertRaisesRegex(BbError, "limite"):
            self.assumir(number=13)
        self.estado["issues"]["12"]["labels"] = []
        self.gravar_estado()
        with self.assertRaisesRegex(BbError, "já está com"):
            self.assumir(name="codex-1")
        with self.assertRaisesRegex(BbError, "limite"):
            self.assumir(number=13)

    def test_recusa_bloqueio_mas_aceita_pr_de_teste_mesclado(self):
        self.issue(11, "Testes", labels=["teste-aceite"])
        self.issue(12, "Tarefa", blocked_by=[11])
        with self.assertRaisesRegex(BbError, "bloqueada pela #11"):
            self.assumir()
        self.estado["prs"] = {"30": {"body": "Refs #110", "head": "teste/110-outra", "base": "epico/7-x",
                                        "state": "MERGED"}}
        self.gravar_estado()
        with self.assertRaises(BbError):
            self.assumir()
        self.estado["prs"]["30"].update(body="Refs #11", head="teste/11-testes")
        self.gravar_estado()
        self.assumir()

    def test_outra_sessao_nao_libera(self):
        acquired = self.assumir()
        with self.assertRaises(BbError):
            ownership.release(self.config, 12, acquired["name"], "outra-sessao")
        self.assertTrue(ownership.active_claims("dono/repo", 12, "dono"))

    def test_falha_na_confirmacao_remove_so_a_propria_marca(self):
        original = ownership.active_claims
        with patch.object(ownership.time, "sleep", side_effect=RuntimeError("rede falhou")):
            with self.assertRaises(RuntimeError):
                self.assumir()
        self.assertFalse(original("dono/repo", 12, "dono"))
        self.assertNotIn("ia:claude-1", self.ler_estado()["issues"]["12"]["labels"])

    def test_desempate_e_rollback_nao_apagam_label_do_mesmo_nome(self):
        acquired = self.assumir()
        existing = ownership.active_claims("dono/repo", 12, "dono")[0]
        # Simulate a second client whose initial snapshot predates the first client's mark.
        with patch.object(ownership, "active_claims", side_effect=[[], [existing], [existing]]), \
                patch.object(ownership, "issue_data", return_value={"state": "open", "labels": []}):
            with self.assertRaisesRegex(BbError, "disputa perdida"):
                self.assumir()
        self.assertIn("ia:claude-1", self.ler_estado()["issues"]["12"]["labels"])
        self.assertEqual(ownership.active_claims("dono/repo", 12, "dono")[0]["session"], acquired["session"])

    def test_comentario_de_terceiro_nao_e_posse(self):
        ownership.api("repos/dono/repo/issues/12/comments", "POST",
                      body="<!-- bb:assumida nome=claude-2 sessao=x -->")
        self.ler_estado()
        self.estado["comment_records"]["12"][0]["user"]["login"] = "terceiro"
        self.gravar_estado()
        self.assumir()


class Processos(ComGit):
    def setUp(self):
        super().setUp()
        self.escrever("bigbang.toml", open_toml(self.trabalho).replace(
            "BrunodosSantosVaz/meu-sistema", "dono/repo").replace('dono = "BrunodosSantosVaz"', 'dono = "dono"').replace(
                "espera_confirmacao_segundos = 10", "espera_confirmacao_segundos = 1"))
        self.commit("chore: configure ownership")
        self.git("push", "-q", "origin", "main")
        self.branch("feature/12-tarefa", "main", "docs/tarefa.md", "# Tarefa\n")
        self.issue(12, "Tarefa", labels=["task"])
        self.estado["refs"]["heads/feature/12-tarefa"] = self.git_origin("rev-parse", "feature/12-tarefa")
        self.gravar_estado()
        self.env = {**os.environ, "BB_GH": os.path.join(self.bin, "gh"), "FAKE_GH_STATE": self.estado_arquivo,
                    "FAKE_GH_LOG": self.log, "GITHUB_REPOSITORY": "dono/repo"}

    def command(self, *args, root=None):
        return [sys.executable, os.path.join(BIGBANG, "bin", "bb.py"), "--raiz", root or self.trabalho, *args]

    def test_dois_processos_so_um_dono_e_uma_pasta(self):
        gate = os.path.join(self.pasta, "barreira")
        os.mkdir(gate)
        processes = []
        for name in ("claude-1", "codex-1"):
            env = {**self.env, "FAKE_GH_INITIAL_GATE": gate, "FAKE_GH_ACTOR": name}
            processes.append(subprocess.Popen(self.command("assumir", "12", name, "--pasta", os.path.join(
                self.pasta, name)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env))
        results = [(*p.communicate(timeout=20), p.returncode) for p in processes]
        self.assertEqual(sorted(r[2] for r in results), [0, EXIT_INVALID_STATE], results)
        self.ler_estado()
        claims = [c for c in self.estado["comment_records"]["12"] if "bb:assumida" in c["body"]]
        self.assertEqual(len(claims), 1)
        owned = [label for label in self.estado["issues"]["12"]["labels"] if label.startswith("ia:")]
        self.assertEqual(len(owned), 1)
        self.assertIn("nome=" + owned[0][3:], claims[0]["body"])
        self.assertEqual(sum(os.path.isdir(os.path.join(self.pasta, name)) for name in ("claude-1", "codex-1")), 1)
        winner_root = os.path.join(self.pasta, owned[0][3:])
        self.assertEqual(workspaces.receipt(winner_root)["issue"], 12)
        release = subprocess.run(self.command("liberar", "12", root=winner_root), capture_output=True,
                                 text=True, env=self.env, check=False)
        self.assertEqual(release.returncode, 0, release.stdout + release.stderr)
        self.assertFalse(any(x.startswith("ia:") for x in self.ler_estado()["issues"]["12"]["labels"]))
        self.assertTrue(os.path.isdir(winner_root))

    def test_falha_no_worktree_desfaz_a_posse(self):
        result = subprocess.run(self.command("assumir", "12", "codex-1", "--pasta", self.trabalho),
                                capture_output=True, text=True, env=self.env, check=False)
        self.assertEqual(result.returncode, EXIT_INVALID_STATE, result.stdout + result.stderr)
        self.assertNotIn("ia:codex-1", self.ler_estado()["issues"]["12"]["labels"])
        self.assertIn("bb:liberada", self.estado["comments"]["12"][0])


def open_toml(root):
    with open(os.path.join(root, "bigbang.toml"), encoding="utf-8") as handle:
        return handle.read()
