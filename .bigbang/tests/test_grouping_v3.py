"""Grouping workflow of v3 (epic #228, ADR-0022): feature flags, branch rules, release gate, sprint start,
branches from develop, merge rules and release cut. In-memory GitHub."""
import datetime
import os
import tempfile
import unittest

from _fake_github import FakeGitHub, FakeProject
from _raiz import importar_bb

importar_bb()
from bb import board, flags, flows, gh, pipeline  # noqa: E402
from bb.errors import BbError  # noqa: E402

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
TODAY = NOW.date()
FLAGS_V3 = """
[[flag]]
name = "novo-login"
owner = "dona"
reason = "Épico #10 ainda em homologação"
epic = "#10"
created = 2026-10-01
expires = 2026-11-01

[flag.state]
staging = true
production = false
"""
FLAGS_LEGACY = FLAGS_V3.replace("name =", "nome =").replace("owner =", "dono =").replace("reason =", "motivo =") \
    .replace("epic =", "epico =").replace("created =", "criada_em =").replace("expires =", "expira_em =") \
    .replace("[flag.state]", "[flag.estado]").replace("production =", "producao =")


class Flags(unittest.TestCase):
    def test_both_languages_read_the_same(self):
        self.assertEqual(flags.parse(FLAGS_V3, TODAY), flags.parse(FLAGS_LEGACY, TODAY))
        flag = flags.parse(FLAGS_V3, TODAY)[0]
        self.assertEqual((flag["name"], flag["epic"], flag["production"], flag["staging"]),
                         ("novo-login", 10, False, True))

    def test_invalid_entries_are_refused(self):
        for text in (FLAGS_V3.replace('epic = "#10"', 'epic = "dez"'),
                     FLAGS_V3.replace("expires = 2026-11-01", "expires = 2026-09-01"),
                     FLAGS_V3.replace("production = false", 'production = "no"'),
                     FLAGS_V3 + FLAGS_V3, "flag = 1"):
            with self.subTest(text=text[:40]), self.assertRaises(BbError):
                flags.parse(text, TODAY)

    def test_switch_keeps_the_file_and_its_language(self):
        changed = flags.switch(FLAGS_LEGACY, "novo-login", "production", True, TODAY)
        self.assertIn("producao = true", changed)
        self.assertTrue(flags.parse(changed, TODAY)[0]["production"])
        with self.assertRaises(BbError):
            flags.switch(FLAGS_V3, "inexistente", "production", True, TODAY)

    def test_release_gate(self):
        parsed = flags.parse(FLAGS_V3, TODAY)
        self.assertEqual(flags.release_problems({10: "pending"}, parsed), [])  # flag off: may ship dark
        self.assertEqual(flags.release_problems({11: "approved"}, parsed), [])
        self.assertTrue(flags.release_problems({11: "pending"}, parsed))  # no flag and not approved
        on = flags.parse(flags.switch(FLAGS_V3, "novo-login", "production", True, TODAY), TODAY)
        self.assertTrue(flags.release_problems({10: "pending"}, on))  # flag on but not approved

    def test_pending_acceptance_only_for_dark_epics(self):
        parsed = flags.parse(FLAGS_V3, TODAY)
        self.assertEqual(flags.pending_problems({21: 10}, parsed), [])
        self.assertTrue(flags.pending_problems({22: 11}, parsed))
        self.assertTrue(flags.pending_problems({23: None}, parsed))


class BranchRules(unittest.TestCase):
    def test_v3_targets(self):
        ok = (("test/11-x", "develop"), ("feature/12-x", "develop"), ("docs/13-x", "develop"),
              ("fix/14-x", "release/1.2.1"), ("fix/14-x", "develop"), ("hotfix/15-x", "release/1.2.2"),
              ("maintenance/16-x", "main"), ("release/1.3.0", "main"), ("sync/main-to-develop", "develop"),
              ("foundation/1-x", "develop"), ("framework/v3.0.0", "develop"),
              ("dependabot/github_actions/x", "develop"), ("dependabot/npm/x", "main"))
        for head, base in ok:
            with self.subTest(head=head, base=base):
                self.assertIsNone(pipeline.v3_branch_problem(head, base))
        bad = (("feature/12-x", "main"), ("test/11-x", "release/1.0.0"), ("maintenance/16-x", "develop"),
               ("epico/7-x", "develop"), ("feature/12-x", "epico/7-x"), ("qualquer", "develop"))
        for head, base in bad:
            with self.subTest(head=head, base=base):
                self.assertIsNotNone(pipeline.v3_branch_problem(head, base))


def cfg():
    return {"project": {"repository": "dono/repo", "owner": "dona", "mode": "flash", "name": "Sistema"},
            "agents": {"names": ["claude-1"], "tasks_per_agent": 2, "lease_hours": 2},
            "workflow": {"model": "grouping"}, "board": {"labels": "v3", "model": "single", "number": 7,
                                                           "owner": "dona"},
            "security": {"sensitive_paths": []}, "delivery": {"profile": "deploy", "artifact_paths": ["src/"]}}


EPIC_BODY = """### Problema ou oportunidade
Entrar é difícil.

### Objetivo e resultado esperado
Login simples.

### Escopo
Tela e API.

### Regras de negócio envolvidas
RN-0001

### Critérios de aceite
CA-1: Dado um usuário, quando entra, então vê o painel.

### Tarefas previstas
- API de login
- Tela de login (depende de: 1)
"""


class Flows(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.client = gh.GitHub("dono/repo", api=self.fake)
        self.project = FakeProject()
        board.ensure_fields(self.project)
        self.fake.refs["refs/heads/develop"] = "d" * 40
        self.fake.refs["refs/heads/main"] = "m" * 40
        self.fake.add_issue(10, "Login", labels=["type:epic", "approved:refinement", "prototype:waived",
                                                 "flag:required", "review:ai"], body=EPIC_BODY)
        for target in ("Backlog", "Refinement", "Ready", "Selected"):
            self.record(10, target)

    def record(self, number, target):
        from bb import receipts
        previous = board.current_state(self.client, number, {"dona"})
        self.client.comment(number, receipts.render({
            "kind": "transition", "event_id": f"seed-{number}-{target}", "issue": number, "actor": "dona",
            "at": "2026-10-10T11:00:00Z", "from": previous, "to": target, "sha": "0" * 40, "policy": "seed"}))

    def start(self, **kwargs):
        return flows.start_sprint(self.client, self.project, cfg(), date=TODAY, now=NOW, **kwargs)

    def children(self, epic):
        return {issue["title"]: issue for issue in self.client.sub_issues(epic)}

    def test_start_sprint_creates_children_dependencies_and_test_branch(self):
        plan = self.start()
        self.assertEqual([item["epic"] for item in plan], [10])
        children = self.children(10)
        self.assertEqual(sorted(children), ["API de login", "Documentação: Login", "Tela de login",
                                            "Testes de aceite: Login"])
        test, api, ui, docs = (children[name]["number"] for name in
                               ("Testes de aceite: Login", "API de login", "Tela de login", "Documentação: Login"))
        self.assertIn("type:test", children["Testes de aceite: Login"]["labels"])
        self.assertIn("review:ai", children["API de login"]["labels"])  # inherited
        self.assertEqual({b["number"] for b in self.client.blocked_by(api)}, {test})
        self.assertEqual({b["number"] for b in self.client.blocked_by(ui)}, {test, api})
        self.assertEqual({b["number"] for b in self.client.blocked_by(docs)}, {api, ui})
        self.assertIn(f"refs/heads/test/{test}-testes-de-aceite-login", self.fake.refs)
        self.assertEqual(self.fake.refs[f"refs/heads/test/{test}-testes-de-aceite-login"], "d" * 40)
        self.assertNotIn("refs/heads/epico", " ".join(self.fake.refs))
        self.assertEqual(board.current_state(self.client, 10, {"dona"}), "In Progress")
        self.assertEqual(self.project.status(api), "Todo")
        self.assertTrue(self.project.value(10, "Sprint").startswith("Sprint 1 · 2026-10-10"))

    def test_start_sprint_is_idempotent(self):
        self.start()
        before = (len(self.fake.issues), dict(self.fake.refs))
        self.record(10, "Selected") if False else None
        self.assertEqual(self.start(), [])  # epic already In Progress
        self.assertEqual((len(self.fake.issues), self.fake.refs), before)

    def test_epic_without_readiness_is_refused_with_reasons(self):
        self.fake.issues[10]["body"] = "### Problema ou oportunidade\nx\n"
        plan = self.start()
        self.assertEqual(plan, [])
        self.assertTrue(any("Tarefas previstas" in body for body in self.fake.comment_bodies(10)))

    def test_create_branches_from_develop_when_unblocked(self):
        self.start()
        children = self.children(10)
        test, api = children["Testes de aceite: Login"]["number"], children["API de login"]["number"]
        self.assertEqual(flows.create_branches(self.client, cfg()), [])  # api blocked by the open test issue
        self.fake.issues[test]["state"] = "closed"
        self.fake.refs["refs/heads/develop"] = "e" * 40
        created = flows.create_branches(self.client, cfg())
        self.assertEqual(created, [f"feature/{api}-api-de-login"])
        self.assertEqual(self.fake.refs[f"refs/heads/feature/{api}-api-de-login"], "e" * 40)
        self.assertEqual(flows.create_branches(self.client, cfg()), [])  # idempotent

    def test_docs_branch_only_after_every_task(self):
        self.start()
        children = self.children(10)
        for name in ("Testes de aceite: Login", "API de login", "Tela de login"):
            self.fake.issues[children[name]["number"]]["state"] = "closed"
        docs = children["Documentação: Login"]["number"]
        self.assertIn(f"docs/{docs}-documentacao-login", flows.create_branches(self.client, cfg()))


if __name__ == "__main__":
    unittest.main()
