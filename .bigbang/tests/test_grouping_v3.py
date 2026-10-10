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


class MergeAndRelease(Flows):
    def green(self, sha):
        self.fake.checks[sha] = [{"name": "gate", "status": "completed", "conclusion": "success"}]

    def test_merge_needs_approval_and_a_green_gate_on_the_exact_head(self):
        self.fake.add_issue(30, "Tarefa", labels=["type:task"], parent=10)
        self.fake.add_pull(60, "feature/30-tarefa", "develop", title="feat: tarefa")
        with self.assertRaises(BbError) as error:
            flows.merge_pr(self.client, cfg(), 60)
        self.assertIn("aprov", error.exception.message)
        self.fake.pulls[60]["labels"].append({"name": "pr:approved"})
        with self.assertRaises(BbError):
            flows.merge_pr(self.client, cfg(), 60)  # gate not green
        self.green(self.fake.pulls[60]["head"]["sha"])
        flows.merge_pr(self.client, cfg(), 60)
        self.assertTrue(self.fake.pulls[60]["merged"])
        self.assertEqual(self.fake.pulls[60]["merge_method"], "merge")

    def test_legacy_spelling_of_the_approval_counts(self):
        self.fake.add_pull(61, "feature/31-x", "develop", labels=["pr-aprovado"])
        self.green(self.fake.pulls[61]["head"]["sha"])
        flows.merge_pr(self.client, cfg(), 61)
        self.assertTrue(self.fake.pulls[61]["merged"])

    def test_never_into_main_and_never_outside_the_branch_model(self):
        for number, head, base in ((62, "release/1.0.0", "main"), (63, "feature/32-x", "main"),
                                   (64, "epico/7-x", "develop")):
            self.fake.add_pull(number, head, base, labels=["pr:approved"])
            self.green(self.fake.pulls[number]["head"]["sha"])
            with self.subTest(head=head, base=base), self.assertRaises(BbError):
                flows.merge_pr(self.client, cfg(), number)
            self.assertFalse(self.fake.pulls[number]["merged"])

    def test_human_test_review_needs_the_owner_decision(self):
        self.fake.add_issue(33, "Testes", labels=["type:test", "tests-review:human"], parent=10)
        self.fake.add_pull(65, "test/33-testes", "develop", labels=["pr:approved"])
        self.green(self.fake.pulls[65]["head"]["sha"])
        with self.assertRaises(BbError):
            flows.merge_pr(self.client, cfg(), 65)
        self.fake.pulls[65]["labels"].append({"name": "approved:tests"})
        flows.merge_pr(self.client, cfg(), 65)
        self.assertTrue(self.fake.pulls[65]["merged"])

    def test_cut_release_from_develop_with_version_lock_and_milestone(self):
        self.fake.refs["refs/tags/v1.2.0"] = "1" * 40
        self.fake.add_issue(40, "API", labels=["type:task"], parent=10, state="closed")
        self.fake.add_pull(70, "feature/40-api", "develop", title="feat: api de login", state="closed", merged=True)
        self.fake.add_pull(71, "docs/41-docs", "develop", title="docs: guia", state="closed", merged=True)
        self.fake.compares[("main", "develop")] = ["Merge pull request #70 from dono/feature/40-api",
                                                   "feat: api de login", "Merge pull request #71 from dono/docs/41"]
        release = flows.cut_release(self.client, cfg(), now=NOW)
        self.assertEqual(release["version"], "1.3.0")
        self.assertEqual(self.fake.refs["refs/heads/release/1.3.0"], "d" * 40)
        self.assertIn("refs/bigbang/locks/version-1.3.0", self.fake.refs)
        self.assertEqual([m["title"] for m in self.fake.milestones.values()], ["v1.3.0"])
        self.assertEqual(release["epics"], [10])
        self.assertEqual(self.fake.issues[10]["milestone"], 1)
        with self.assertRaises(BbError):  # the same version cannot be cut twice
            flows.cut_release(self.client, cfg(), now=NOW)

    def test_nothing_to_release(self):
        self.fake.compares[("main", "develop")] = []
        self.assertIsNone(flows.cut_release(self.client, cfg(), now=NOW))

    def test_release_gate_reads_flags_and_pending_marks(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "flags.toml"), "w", encoding="utf-8") as handle:
                handle.write(FLAGS_V3)
            self.fake.add_issue(42, "Outro épico", labels=["type:epic"])
            self.assertEqual(flows.release_gate(self.client, cfg(), root, [10], today=TODAY, pending={}), [])
            self.assertTrue(flows.release_gate(self.client, cfg(), root, [10, 42], today=TODAY, pending={}))
            self.fake.issues[42]["labels"].append({"name": "qa:approved"})
            self.assertEqual(flows.release_gate(self.client, cfg(), root, [10, 42], today=TODAY, pending={}), [])
            self.fake.add_issue(43, "Testes do 42", labels=["type:test"], parent=42)
            self.assertTrue(flows.release_gate(self.client, cfg(), root, [10, 42], today=TODAY, pending={43: ["x"]}))


if __name__ == "__main__":
    unittest.main()


class PrRules(unittest.TestCase):
    def rules(self, head="feature/12-tela", base="develop", title="feat: tela", body="Refs #12", labels=(),
              paths=("src/app.py",), diff="", issue_labels=("type:task",), epic_labels=("type:epic", "flag:required")):
        return pipeline.v3_pr_rules(head, base, title, body, set(labels), list(paths), diff, ["src/"],
                                    ["src/**/auth/**"], "test.failing", set(issue_labels), set(epic_labels))

    def test_clean_task_pr(self):
        errors, add, remove = self.rules()
        self.assertEqual(errors, [])
        self.assertEqual(add, set())
        self.assertIn("no-release", remove)

    def test_branch_title_and_refs(self):
        self.assertTrue(self.rules(base="main")[0])
        self.assertTrue(self.rules(title="tela nova")[0])
        self.assertTrue(self.rules(body="sem referência")[0])
        self.assertTrue(self.rules(body="Refs #12\nCloses #12")[0])

    def test_artifact_code_needs_the_epic_flag_decision(self):
        errors, _, _ = self.rules(epic_labels=("type:epic",))
        self.assertTrue(any("flag" in error for error in errors))
        self.assertEqual(self.rules(epic_labels=("type:epic", "flag:waived"))[0], [])
        self.assertEqual(self.rules(paths=("docs/guia.md",), epic_labels=("type:epic",))[0], [])

    def test_no_release_follows_the_artifact_paths(self):
        _, add, remove = self.rules(paths=("docs/guia.md",))
        self.assertIn("no-release", add)
        self.assertNotIn("no-release", remove)

    def test_sensitive_paths_ask_for_the_owner_unless_he_said_otherwise(self):
        _, add, _ = self.rules(paths=("src/api/auth/login.py",))
        self.assertIn("review:human", add)
        _, add, _ = self.rules(paths=("src/api/auth/login.py",), issue_labels=("type:task", "owner:ai-review"))
        self.assertNotIn("review:human", add)

    def test_acceptance_lock(self):
        diff = ("diff --git a/tests/aceite/test_rn.py b/tests/aceite/test_rn.py\n--- a/tests/aceite/test_rn.py\n"
                "+++ b/tests/aceite/test_rn.py\n@@ -1 +1 @@\n-assert total == 10\n+assert total == 11\n")
        self.assertTrue(self.rules(head="test/11-testes", body="Refs #11", diff=diff, issue_labels=("type:test",))[0])
        self.assertEqual(self.rules(head="test/11-testes", body="Refs #11", diff=diff, labels=("approved:test-change",),
                                    issue_labels=("type:test",))[0], [])
