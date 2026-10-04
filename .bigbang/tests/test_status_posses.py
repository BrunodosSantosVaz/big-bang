"""Stale owners, explicit recovery, push and merge automation, and read-only board/flag reporting."""
import contextlib
import datetime
import io
import os
import shutil
import sys
from unittest.mock import patch

from _raiz import BIGBANG
from test_posse import ComPosse
from test_kanban_mesclar import ComBb

sys.path.insert(0, BIGBANG)
from bb import ownership, status  # noqa: E402
from bb.errors import BbError  # noqa: E402


class Inatividade(ComPosse):
    def antiga(self):
        self.assumir()
        self.ler_estado()
        record = self.estado["comment_records"]["12"][0]
        record["created_at"] = record["updated_at"] = "2020-01-01T00:00:00Z"
        self.gravar_estado()

    def test_status_le_so_e_marcacao_e_idempotente(self):
        self.antiga()
        before = len(self.chamadas())
        self.assertTrue(status.possessions(self.config)[0]["stale"])
        with contextlib.redirect_stdout(io.StringIO()):
            status.report(self.projeto, self.config)
            status.mark_stale(self.config)
        mutations = [call for call in self.chamadas()[before:] if "POST" in call or "PATCH" in call or "DELETE" in call]
        self.assertEqual(mutations, [])
        with contextlib.redirect_stdout(io.StringIO()):
            status.mark_stale(self.config, simulate=False)
            status.mark_stale(self.config, simulate=False)
        self.assertEqual(self.ler_estado()["issues"]["12"]["labels"].count("parada"), 1)

    def test_push_renova_mesmo_quando_commit_foi_escrito_antes(self):
        self.antiga()
        self.estado["issues"]["12"]["labels"].append("parada")
        self.gravar_estado()
        ownership.touch(self.config, 12)
        self.assertFalse(status.possessions(self.config)[0]["stale"])
        self.assertNotIn("parada", self.ler_estado()["issues"]["12"]["labels"])
        first = len(self.estado["comments"]["12"])
        ownership.touch(self.config, 12)
        self.assertEqual(first + 1, len(self.ler_estado()["comments"]["12"]))

    def test_push_concorrente_com_liberacao_nao_reabre_sessao(self):
        acquired = self.assumir()
        original = ownership.api
        triggered = False
        def release_before_heartbeat(path, method="GET", **fields):
            nonlocal triggered
            if method == "POST" and "bb:push" in fields.get("body", "") and not triggered:
                triggered = True
                ownership.release(self.config, 12, acquired["name"], acquired["session"])
            return original(path, method, **fields)
        with patch.object(ownership, "api", side_effect=release_before_heartbeat):
            ownership.touch(self.config, 12)
        self.assertEqual(ownership.active_claims("dono/repo", 12, "dono"), [])
        self.assertNotIn("ia:claude-1", self.ler_estado()["issues"]["12"]["labels"])

    def test_push_entre_conferencia_e_marcacao_nao_deixa_label_parada(self):
        self.antiga()
        original = ownership._add_label
        def push_before_label(repo, number, label):
            ownership.touch(self.config, number)
            original(repo, number, label)
        with patch.object(ownership, "_add_label", side_effect=push_before_label), \
                contextlib.redirect_stdout(io.StringIO()):
            status.mark_stale(self.config, simulate=False)
        self.assertFalse(status.possessions(self.config)[0]["stale"])
        self.assertNotIn("parada", self.ler_estado()["issues"]["12"]["labels"])
        # Repair a leftover label from a previous interrupted run as well.
        self.estado["issues"]["12"]["labels"].append("parada")
        self.gravar_estado()
        status.mark_stale(self.config, simulate=False)
        self.assertNotIn("parada", self.ler_estado()["issues"]["12"]["labels"])

    def test_push_durante_retomada_preserva_a_sessao_renovada(self):
        self.antiga()
        original = ownership.api
        def push_after_order(path, method="GET", **fields):
            result = original(path, method, **fields)
            if method == "POST" and "Ordem do dono" in fields.get("body", ""):
                ownership.touch(self.config, 12)
            return result
        with patch.object(ownership, "api", side_effect=push_after_order):
            with self.assertRaisesRegex(BbError, "recebeu push"):
                ownership.recover(self.config, 12, "codex-1", "Retome se continuar parada.")
        live = ownership.active_claims("dono/repo", 12, "dono")
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["name"], "claude-1")

    def test_forcar_exige_ordem_e_posse_vencida(self):
        self.assumir()
        with self.assertRaisesRegex(BbError, "--frase"):
            ownership.recover(self.config, 12, "codex-1", "")
        with self.assertRaisesRegex(BbError, "ainda ativa"):
            ownership.recover(self.config, 12, "codex-1", "Retome a tarefa.")
        self.ler_estado()
        self.estado["comment_records"]["12"][0]["created_at"] = "2020-01-01T00:00:00Z"
        self.gravar_estado()
        acquired = ownership.recover(self.config, 12, "codex-1", "Retome a tarefa.")
        self.assertEqual(acquired["name"], "codex-1")
        comments = self.ler_estado()["comments"]["12"]
        self.assertIn("bb:liberada", comments[0])
        self.assertIn("> Retome a tarefa.", comments[1])
        self.assertIn("ia:codex-1", self.estado["issues"]["12"]["labels"])

    def test_sem_nome_valido_nao_deve_revogar_a_posse(self):
        self.antiga()
        with self.assertRaises(BbError):
            ownership.recover(self.config, 12, "intrusa", "Retome.")
        self.assertTrue(ownership.active_claims("dono/repo", 12, "dono"))

    def test_bb_status_e_somente_leitura(self):
        shutil.copytree(BIGBANG, os.path.join(self.projeto, ".bigbang"), dirs_exist_ok=True)
        before = len(self.chamadas())
        code, _ = self.bb("status")
        self.assertEqual(code, 0)
        self.assertFalse(any("POST" in c or "PATCH" in c or "DELETE" in c for c in self.chamadas()[before:]))


class Flags(ComPosse):
    def escrever_flags(self, text):
        with open(os.path.join(self.projeto, "flags.toml"), "w", encoding="utf-8") as handle:
            handle.write(text)

    def exemplo(self, created="2026-09-01", expires="2026-09-30", production="true"):
        return (f'[[flag]]\nnome="nova-tela"\ndono="dono"\nmotivo="Dependência"\nepico="#7"\n'
                f'criada_em={created}\nexpira_em={expires}\n[flag.estado]\nstaging=true\nproducao={production}\n')

    def test_vencida_producao_antiga_e_ativa(self):
        today = datetime.date(2026, 10, 4)
        self.escrever_flags(self.exemplo())
        self.assertTrue(status.flags(self.projeto, self.config, today)[0]["expired"])
        self.escrever_flags(self.exemplo(expires="2026-11-01"))
        self.assertTrue(status.flags(self.projeto, self.config, today)[0]["old"])
        self.escrever_flags(self.exemplo(created="2026-10-01", expires="2026-10-31"))
        self.assertEqual(status.flags(self.projeto, self.config, today), [])
        self.escrever_flags(self.exemplo(expires="2026-11-01", production="false"))
        self.assertEqual(status.flags(self.projeto, self.config, today), [])

    def test_flag_invalida_nao_desaparece_do_relatorio(self):
        for bad in ('[[flag]]\nnome="x"\n', '[flag]\nnome="x"\n', '[[flag]]\nnome = [\n', 'flag=[1]'):
            self.escrever_flags(bad)
            with self.assertRaises(BbError):
                status.flags(self.projeto, self.config)


class Automacao(ComBb):
    def test_merge_libera_label_e_preserva_comentario(self):
        self.issue(12, "Tarefa", labels=["task", "ia:codex-1", "parada"])
        self.estado["comment_records"] = {"12": [{"id": 1,
            "body": "<!-- bb:assumida nome=codex-1 sessao=x -->", "user": {"login": "dono"},
            "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z"}]}
        self.estado["comments"] = {"12": [self.estado["comment_records"]["12"][0]["body"]]}
        self.gravar_estado()
        result = self.kanban(EVENT="pull_request", ACTION="closed", MERGED="true", HEAD_REF="feature/12-tarefa",
                             BASE_REF="epico/7-x")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.estado["issues"]["12"]["labels"], ["task"])
        self.assertIn("bb:liberada", self.estado["comments"]["12"][0])
