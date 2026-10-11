"""Guided migration to the v3 (epic #233, plan section 8): four parts in order (config, board, workflow, labels; the
legacy pipeline only understands the Portuguese labels, so they change last), each with a dry run, a snapshot and a
way back; nothing is deleted and every part refuses to run out of order. In-memory GitHub."""
import datetime
import json
import os
import shutil
import tempfile
import unittest

from _cenarios import CENARIOS
from _fake_github import FakeGitHub, FakeProject
from _raiz import importar_bb

importar_bb()
from bb import board, config as config_module, gh, migrate, receipts  # noqa: E402
from bb.errors import BbError  # noqa: E402
from unittest.mock import patch
from bb import cli

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
FRAMEWORK_SECTION = """
## Projeto

Esta seção pertence ao projeto.

> **Se este é o repositório `BrunodosSantosVaz/big-bang`** (o próprio framework, não um sistema criado a partir
> dele): não rode a Fundação.

### Modo do próprio framework

Flash aprovado pelo dono em 06/10/2026 (ADR-0017). Continue o plano autorizado.

### Comandos

npm test
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        from _raiz import RAIZ
        os.makedirs(os.path.join(self.root, ".bigbang"))
        shutil.copy(os.path.join(RAIZ, ".bigbang", "VERSION"), os.path.join(self.root, ".bigbang", "VERSION"))
        with open(os.path.join(CENARIOS, "deploy-vps-docker.toml"), encoding="utf-8") as handle:
            text = handle.read()
        with open(os.path.join(RAIZ, ".bigbang", "VERSION"), encoding="utf-8") as handle:
            version = handle.read().strip()
        text = text.replace('versao = "0.9.0"', f'versao = "{version}"', 1)
        text = text.replace("planejamento = 0", "planejamento = 28").replace("execucao = 0", "execucao = 29") \
            .replace("bugs = 0", "bugs = 30")
        self.write("bigbang.toml", text)
        self.write("AGENTS.md", "<!-- bigbang:inicio v2.0.1 -->\nbloco\n<!-- bigbang:fim -->\n" + FRAMEWORK_SECTION)
        self.fake = FakeGitHub(self.read_config_repository())
        self.fake.author = "BrunodosSantosVaz"  # the trusted account (project.owner) writes the receipts
        self.client = gh.GitHub(self.read_config_repository(), api=self.fake)

    def write(self, name, text):
        with open(os.path.join(self.root, name), "w", encoding="utf-8") as handle:
            handle.write(text)

    def read(self, name):
        with open(os.path.join(self.root, name), encoding="utf-8") as handle:
            return handle.read()

    def read_config_repository(self):
        return config_module.get(config_module.load(self.root), "project.repository")

    def config(self):
        return config_module.load(self.root)


class Config(Base):
    def test_real_three_line_framework_quote_is_removed_and_rollback_is_exact(self):
        agents = """<!-- bigbang:inicio v3.0.0 -->
generated instructions
<!-- bigbang:fim -->

## Projeto

Esta seção pertence ao projeto.

> **Se este é o repositório `BrunodosSantosVaz/big-bang`** (o próprio framework, não um sistema criado a partir
> dele): não rode a Fundação. Siga `.bigbang/docs/especificacao.md`, trabalhe um épico por vez (seção 17) e registre
> as decisões do framework em `.bigbang/docs/decisoes/`.

### Comandos

npm test
"""
        self.write("AGENTS.md", agents)
        before = (self.read("bigbang.toml"), agents)
        snapshot = os.path.join(self.root, "config.json")
        migrate.config_part(self.root, snapshot=snapshot, dry_run=True)
        self.assertEqual((self.read("bigbang.toml"), self.read("AGENTS.md")), before)
        self.assertFalse(os.path.exists(snapshot))
        migrate.config_part(self.root, snapshot=snapshot)
        cleaned = self.read("AGENTS.md")
        self.assertNotIn("BrunodosSantosVaz/big-bang", cleaned)
        self.assertNotIn("não rode a Fundação", cleaned)
        self.assertNotIn("as decisões do framework", cleaned)
        self.assertIn("generated instructions", cleaned)
        self.assertIn("## Projeto\n\nEsta seção pertence ao projeto.", cleaned)
        self.assertIn("### Comandos\n\nnpm test\n", cleaned)
        migrate.config_part(self.root, snapshot=snapshot, rollback=True)
        self.assertEqual((self.read("bigbang.toml"), self.read("AGENTS.md")), before)

    def test_single_line_framework_quote_preserves_following_project_subsection(self):
        agents = """## Projeto

Descrição do projeto.

> **Se este é o repositório `BrunodosSantosVaz/big-bang`**: não rode a Fundação.

### Comandos

npm test
"""
        expected = """## Projeto

Descrição do projeto.

### Comandos

npm test
"""
        self.write("AGENTS.md", agents)
        migrate.config_part(self.root)
        self.assertEqual(self.read("AGENTS.md"), expected)

    def test_framework_quote_preserves_later_subsections_and_unrelated_quote(self):
        prefix = "## Projeto\n\nDescrição do projeto.\n\n"
        quote = ("> **Se este é o repositório `BrunodosSantosVaz/big-bang`**: instrução herdada\n"
                 "> continuação do framework\n> última linha herdada\n")
        following = """### Comandos

npm test

> Nota específica do projeto.
> Preserve esta continuação.

### Operação

Preserve as instruções do projeto.
"""
        # Even without a blank line, the next heading ends the inherited quote.
        self.write("AGENTS.md", prefix + quote + following)
        migrate.config_part(self.root)
        self.assertEqual(self.read("AGENTS.md"), prefix + following)

    def test_existing_snapshot_is_never_overwritten(self):
        snapshot = os.path.join(self.root, "config.json")
        self.write("config.json", "precious backup")
        before = self.read("bigbang.toml")
        with self.assertRaises(BbError):
            migrate.config_part(self.root, snapshot=snapshot)
        self.assertEqual(self.read("config.json"), "precious backup")
        self.assertEqual(self.read("bigbang.toml"), before)

    def test_snapshot_restores_config_and_agents_exactly(self):
        before = (self.read("bigbang.toml"), self.read("AGENTS.md"))
        snapshot = os.path.join(self.root, "config.json")
        migrate.config_part(self.root, snapshot=snapshot)
        migrate.config_part(self.root, snapshot=snapshot, rollback=True)
        self.assertEqual((self.read("bigbang.toml"), self.read("AGENTS.md")), before)

    def test_dry_run_changes_nothing(self):
        before = self.read("bigbang.toml")
        report = migrate.config_part(self.root, dry_run=True)
        self.assertEqual(self.read("bigbang.toml"), before)
        self.assertTrue(report["changes"])

    def test_rewrites_in_english_keeping_the_behavior(self):
        legacy_view = self.config()
        migrate.config_part(self.root)
        text = self.read("bigbang.toml")
        self.assertIn("[project]", text)
        self.assertNotIn("[projeto]", text)
        migrated = self.config()
        self.assertEqual(config_module.get(migrated, "workflow.model"), "epic-branch")
        self.assertEqual(config_module.get(migrated, "board.model"), "three-boards")
        self.assertEqual(config_module.get(migrated, "board.labels"), "legacy")
        self.assertEqual(config_module.get(migrated, "project.repository"),
                         config_module.get(legacy_view, "project.repository"))

    def test_removes_the_inherited_framework_section_and_keeps_the_project_part(self):
        migrate.config_part(self.root)
        agents = self.read("AGENTS.md")
        self.assertNotIn("Modo do próprio framework", agents)
        self.assertNotIn("BrunodosSantosVaz/big-bang", agents)
        self.assertIn("### Comandos", agents)
        self.assertIn("Esta seção pertence ao projeto.", agents)

    def test_second_run_is_a_no_op(self):
        migrate.config_part(self.root)
        self.assertFalse(migrate.config_part(self.root)["changes"])


class Labels(Base):
    def test_rollback_after_a_partial_rename_is_idempotent(self):
        self.ready()
        self.fake.failures.add(("PATCH", "labels/revisao-humana"))
        with self.assertRaises(BbError):
            migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        self.fake.failures.clear()
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot, rollback=True)
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot, rollback=True)
        self.assertIn('epic', self.fake.label_names(10))

    def test_copying_existing_labels_includes_pull_requests(self):
        self.ready()
        self.fake.labels['review:human'] = {'name': 'review:human'}
        self.fake.add_issue(70, labels=['revisao-humana'])
        self.fake.issues[70]['pull_request'] = {}
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        self.assertIn('review:human', self.fake.label_names(70))

    def test_foreign_snapshot_refuses_before_any_write(self):
        self.ready()
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        data = json.loads(self.read("labels.json"))
        data["repository"] = "another/project"
        self.write("labels.json", json.dumps(data))
        before = dict(self.fake.labels)
        with self.assertRaises(BbError):
            migrate.labels_part(self.client, self.root, snapshot=self.snapshot, rollback=True)
        self.assertEqual(self.fake.labels, before)

    def setUp(self):
        super().setUp()
        for name in ("epic", "task", "homologado", "revisao-humana", "tem-dependencia", "qa:approved"):
            self.fake.labels[name] = {"name": name}
        self.fake.add_issue(10, "Épico", labels=["epic", "homologado"])
        self.fake.add_issue(11, "Tarefa", labels=["task", "tem-dependencia"])
        self.snapshot = os.path.join(self.root, "labels.json")

    def test_needs_the_workflow_part_first(self):
        migrate.config_part(self.root)
        with self.assertRaises(BbError):
            migrate.labels_part(self.client, self.root, snapshot=self.snapshot)

    def ready(self):
        migrate.config_part(self.root)
        import re
        text = self.read("bigbang.toml").replace('model = "three-boards"', 'model = "single"', 1)
        text = re.sub(r"(?m)^(planning|execution|bugs) = \d+[^\n]*\n", "", text)
        text = text.replace('labels = "legacy"', 'labels = "legacy"\nnumber = 7', 1)
        text = text.replace('model = "epic-branch"', 'model = "grouping"', 1)
        self.write("bigbang.toml", text)

    def test_renames_keeping_the_issues_copies_when_both_exist_and_creates_the_catalog(self):
        self.ready()
        report = migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        self.assertIn(("epic", "type:epic"), report["renamed"])
        self.assertEqual(self.fake.label_names(10), ["homologado", "qa:approved", "type:epic"])
        self.assertIn("homologado", self.fake.labels)  # nothing deleted while the migration is not finished
        self.assertIn("type:bug", self.fake.labels)  # the v3 catalog is complete
        self.assertEqual(report["replaced"], {"tem-dependencia": [11]})
        self.assertEqual(config_module.get(self.config(), "board.labels"), "v3")
        with open(self.snapshot, encoding="utf-8") as handle:
            self.assertIn("epic", json.load(handle)["renamed"])

    def test_rollback_restores_the_names(self):
        self.ready()
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot, rollback=True)
        self.assertIn("epic", self.fake.label_names(10))
        self.assertNotIn("type:epic", self.fake.label_names(10))
        self.assertNotIn("qa:approved", self.fake.label_names(10))
        self.assertEqual(config_module.get(self.config(), "board.labels"), "legacy")

    def test_dry_run_changes_nothing(self):
        self.ready()
        report = migrate.labels_part(self.client, self.root, snapshot=self.snapshot, dry_run=True)
        self.assertIn("epic", self.fake.labels)
        self.assertNotIn("type:epic", self.fake.labels)
        self.assertTrue(report["renamed"])


class Board(Base):
    def test_remigration_after_rollback_uses_current_legacy_evidence(self):
        self.ready()
        self.run_part()
        self.run_part(rollback=True)
        self.old[28].set(12, 'Status', 'Backlog Refinement')
        self.snapshot = os.path.join(self.root, 'board-again.json')
        report = self.run_part()
        self.assertEqual(report['mapped'][12], 'Refinement')
        self.assertEqual(self.new.get(12, 'Status'), 'Refinement')
        self.assertEqual(board.current_state(self.client, 12, {'BrunodosSantosVaz'}), 'Refinement')

    def test_closed_epic_without_release_does_not_advance_to_done(self):
        self.ready()
        self.fake.issues[12]['state'] = 'closed'
        self.old[28].set(12, 'Status', 'Concluída')
        self.assertEqual(self.run_part()['mapped'][12], 'Releasing')

    def test_closed_epic_with_its_stable_tag_is_done(self):
        self.ready()
        self.fake.issues[12]['state'] = 'closed'
        self.fake.issues[12]['milestone'] = {'title': 'v1.2.3'}
        self.fake.refs['refs/tags/v1.2.3'] = 'a' * 40
        self.old[28].set(12, 'Status', 'Concluída')
        self.assertEqual(self.run_part()['mapped'][12], 'Done')

    def test_bug_without_candidate_does_not_advance_to_qa(self):
        self.ready()
        self.old[30].set(16, 'Status', 'Homologação')
        self.assertEqual(self.run_part()['mapped'][16], 'In Review')

    def test_stale_or_unverified_claim_does_not_advance_to_coding(self):
        self.ready()
        self.fake.comments[14][0]['created_at'] = '2020-01-01T00:00:00Z'
        self.assertEqual(self.run_part()['mapped'][14], 'Todo')

    def test_ready_task_waits_for_workflow_migration_even_with_merged_pr(self):
        self.ready()
        self.fake.pulls[70]['state'] = 'closed'
        self.fake.pulls[70]['merged'] = True
        self.fake.issues[17]['state'] = 'closed'
        self.old[29].set(17, 'Status', 'Pronto')
        self.assertEqual(self.run_part()['mapped'][17], 'In Review')

    def test_bug_without_claim_uses_a_state_allowed_by_the_runtime(self):
        self.ready()
        self.old[30].ensure_field("Status", "SINGLE_SELECT", ["Novo", "Em correção", "CI/PR"])
        for column in ("Em correção", "CI/PR"):
            with self.subTest(column=column):
                self.old[30].set(16, "Status", column)
                report = self.run_part(dry_run=True)
                target = report["mapped"][16]
                self.assertEqual(target, "Selected")
                from bb import states
                self.assertIn("bug", states.ALLOWED[target])

    def test_initial_cards_also_receive_a_migration_receipt(self):
        self.ready()
        self.run_part()
        for number in (15, 16):
            history = receipts.parse(self.client.comments(number), {"BrunodosSantosVaz"})
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["actor"], migrate.MIGRATION_ACTOR)

    def test_legacy_labels_are_mapped_before_the_label_migration(self):
        self.ready()
        from bb import names
        for issue in self.fake.issues.values():
            issue["labels"] = [{"name": names.label(label["name"], "legacy")} for label in issue["labels"]]
        report = self.run_part()
        self.assertEqual(report["mapped"][12], "Selected")
        self.assertEqual(report["mapped"][14], "Coding")
        self.assertEqual(config_module.get(self.config(), "board.labels"), "legacy")

    def setUp(self):
        super().setUp()
        self.fake.add_issue(10, "Épico em refinamento", labels=["type:epic", "approved:refinement"])
        self.fake.add_issue(12, "Épico aprovado", labels=["type:epic", "approved:refinement"])
        self.fake.add_issue(13, "Épico sem aprovação", labels=["type:epic"])
        self.fake.add_issue(14, "Tarefa com posse", labels=["type:task", "ia:claude-1"])
        self.client.comment(14, '<!-- bb:assumida nome=claude-1 sessao=active-session -->')
        self.fake.comments[14][0]['created_at'] = '2026-10-11T11:00:00Z'
        self.fake.add_issue(15, "Tarefa sem posse", labels=["type:task"])
        self.fake.add_issue(16, "Bug novo", labels=["type:bug"])
        self.fake.add_issue(17, "Tarefa com PR", labels=["type:task"])
        self.fake.add_pull(70, "feature/17-x", "epico/12-aprovado")
        self.old = {28: FakeProject(), 29: FakeProject(), 30: FakeProject()}
        for project in self.old.values():
            project.ensure_field("Status", "SINGLE_SELECT", ["Backlog Refinement", "Próxima sprint", "Code", "CI/PR",
                                                             "Novo", "Concluída", "Homologação", "Pronto"])
        for number, column in ((10, "Backlog Refinement"), (12, "Próxima sprint"), (13, "Próxima sprint")):
            self.old[28].set(number, "Status", column)
        for number, column in ((14, "Code"), (15, "Code"), (17, "CI/PR")):
            self.old[29].set(number, "Status", column)
        self.old[30].set(16, "Status", "Novo")
        self.new = FakeProject()
        self.snapshot = os.path.join(self.root, "board.json")

    def run_part(self, **kwargs):
        return migrate.board_part(self.client, self.root, open_project=lambda number: self.old[number],
                                  create_project=lambda: (7, self.new), snapshot=self.snapshot, now=NOW, **kwargs)

    def ready(self):
        migrate.config_part(self.root)

    def test_needs_the_config_part_first(self):
        with self.assertRaises(BbError):
            self.run_part()

    def test_maps_every_card_by_evidence_with_a_migration_receipt(self):
        self.ready()
        report = self.run_part()
        expected = {10: "Refinement", 12: "Selected", 13: "Refinement", 14: "Coding", 15: "Todo", 16: "Brainstorm",
                    17: "In Review"}
        self.assertEqual(report["mapped"], expected)
        for number, state in expected.items():
            self.assertEqual(board.current_state(self.client, number, {"BrunodosSantosVaz"}), state)
            self.assertEqual(self.new.get(number, "Status"), state)
        history = receipts.parse(self.fake.comments[12], {"BrunodosSantosVaz"})
        self.assertEqual(history[-1]["actor"], "migration")
        config = self.config()
        self.assertEqual(config_module.get(config, "board.model"), "single")
        self.assertEqual(config_module.get(config, "board.number"), 7)

    def test_snapshot_keeps_the_old_boards_and_rollback_restores_them(self):
        self.ready()
        self.run_part()
        with open(self.snapshot, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["boards"], {"planning": 28, "execution": 29, "bugs": 30})
        self.assertEqual(data["items"]["28"]["12"]["Status"], "Próxima sprint")
        self.run_part(rollback=True)
        config = self.config()
        self.assertEqual(config_module.get(config, "board.model"), "three-boards")
        self.assertEqual(config_module.get(config, "board.planning"), 28)

    def test_dry_run_writes_nothing(self):
        self.ready()
        report = self.run_part(dry_run=True)
        self.assertEqual(report["mapped"][12], "Selected")
        self.assertNotIn(12, self.fake.comments)
        self.assertEqual(config_module.get(self.config(), "board.model"), "three-boards")

    def test_second_run_does_not_duplicate_receipts(self):
        self.ready()
        self.run_part()
        count = len(self.fake.comments[12])
        text = self.read("bigbang.toml")
        self.run_part()
        self.assertEqual(len(self.fake.comments[12]), count)
        self.assertEqual(self.read("bigbang.toml"), text)


class Workflow(Base):
    def test_snapshot_rollback_restores_the_original_configuration(self):
        self.ready()
        before = self.read("bigbang.toml")
        snapshot = os.path.join(self.root, "workflow.json")
        migrate.workflow_part(self.client, self.root, snapshot=snapshot)
        migrate.workflow_part(self.client, self.root, snapshot=snapshot, rollback=True)
        self.assertEqual(self.read("bigbang.toml"), before)

    def ready(self):
        migrate.config_part(self.root)
        text = self.read("bigbang.toml").replace('model = "three-boards"', 'model = "single"', 1)
        import re
        text = re.sub(r"(?m)^(planning|execution|bugs) = \d+[^\n]*\n", "", text)
        text = text.replace('labels = "legacy"', 'labels = "legacy"\nnumber = 7', 1)
        self.write("bigbang.toml", text)
        self.fake.refs["refs/heads/develop"] = "d" * 40

    def test_needs_the_board_part_first(self):
        migrate.config_part(self.root)
        with self.assertRaises(BbError):
            migrate.workflow_part(self.client, self.root)

    def test_refuses_while_epic_branches_carry_unmerged_work(self):
        self.ready()
        self.fake.refs["refs/heads/epico/12-login"] = "e" * 40
        self.fake.compares[("develop", "epico/12-login")] = ["feat: a", "feat: b", "feat: c"]
        with self.assertRaises(BbError) as error:
            migrate.workflow_part(self.client, self.root)
        self.assertIn("epico/12-login", error.exception.message)

    def test_switches_to_grouping_and_lists_the_owner_steps(self):
        self.ready()
        report = migrate.workflow_part(self.client, self.root)
        self.assertEqual(config_module.get(self.config(), "workflow.model"), "grouping")
        self.assertTrue(any("gate" in step for step in report["owner_steps"]))
        self.assertTrue(any("production" in step for step in report["owner_steps"]))
        self.assertTrue(any("PROJECT_TOKEN" in step for step in report["owner_steps"]))
        migrate.workflow_part(self.client, self.root, rollback=True)
        self.assertEqual(config_module.get(self.config(), "workflow.model"), "epic-branch")


class CLI(Base):
    def test_config_alias_dry_run_never_writes_or_contacts_github(self):
        before = self.read("bigbang.toml")
        with patch("bb.gh.GitHub", side_effect=AssertionError("GitHub inesperado")):
            self.assertEqual(cli.main(["--root", self.root, "migrar", "config", "--dry-run"]), 0)
        self.assertEqual(self.read("bigbang.toml"), before)

    def test_github_parts_default_to_the_plan_without_yes(self):
        for part in ("board", "labels"):
            with self.subTest(part=part), patch("bb.migrate." + part + "_part", return_value={}) as action:
                self.assertEqual(cli.main(["--root", self.root, "migrate", part]), 0)
                self.assertTrue(action.call_args.kwargs["dry_run"])

    def test_real_run_without_snapshot_refuses_before_mutation(self):
        with patch("bb.migrate.labels_part") as action:
            self.assertNotEqual(cli.main(["--root", self.root, "migrate", "labels", "--yes"]), 0)
            action.assert_not_called()

    def test_config_roundtrip_from_cli(self):
        before = self.read("bigbang.toml")
        snapshot = os.path.join(self.root, "config.json")
        args = ["--root", self.root, "migrate", "config", "--snapshot", snapshot]
        self.assertEqual(cli.main(args), 0)
        self.assertIn("[project]", self.read("bigbang.toml"))
        self.assertEqual(cli.main(args + ["--rollback"]), 0)
        self.assertEqual(self.read("bigbang.toml"), before)


class RollbackOrder(Workflow):
    """Undoing an earlier part while a later one is applied would orphan the later work (audit of #263/#265/#266)."""

    def applied(self):
        self.ready()  # config + single board
        snapshot = os.path.join(self.root, "workflow.json")
        migrate.workflow_part(self.client, self.root, snapshot=snapshot)
        return snapshot

    def test_config_and_board_rollbacks_are_refused_while_the_workflow_is_applied(self):
        self.applied()
        before = self.read("bigbang.toml")
        for call in (lambda: migrate.config_part(self.root, snapshot="x.json", rollback=True),
                     lambda: migrate.board_part(self.client, self.root, open_project=None, create_project=None,
                                                snapshot="x.json", rollback=True)):
            with self.assertRaises(BbError) as error:
                call()
            self.assertIn("desfaça antes", error.exception.message)
        self.assertEqual(self.read("bigbang.toml"), before)

    def test_workflow_rollback_is_refused_while_the_labels_are_migrated(self):
        snapshot = self.applied()
        self.write("bigbang.toml", self.read("bigbang.toml").replace('labels = "legacy"', 'labels = "v3"', 1)
                   .replace('model = "grouping"', 'model = "grouping"', 1))
        with self.assertRaises(BbError) as error:
            migrate.workflow_part(self.client, self.root, snapshot=snapshot, rollback=True)
        self.assertIn("desfaça antes", error.exception.message)

    def test_rolling_back_in_reverse_order_works(self):
        snapshot = self.applied()
        migrate.workflow_part(self.client, self.root, snapshot=snapshot, rollback=True)
        self.assertEqual(config_module.get(self.config(), "workflow.model"), "epic-branch")


if __name__ == "__main__":
    unittest.main()
