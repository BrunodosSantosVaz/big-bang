"""Guided migration to the v3 (epic #233, plan section 8): four parts (config, labels, board, workflow), each with a
dry run, a snapshot and a way back; nothing is deleted and every part refuses to run out of order. In-memory GitHub."""
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
        with open(os.path.join(CENARIOS, "deploy-vps-docker.toml"), encoding="utf-8") as handle:
            text = handle.read()
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
    def setUp(self):
        super().setUp()
        for name in ("epic", "task", "homologado", "revisao-humana", "tem-dependencia", "qa:approved"):
            self.fake.labels[name] = {"name": name}
        self.fake.add_issue(10, "Épico", labels=["epic", "homologado"])
        self.fake.add_issue(11, "Tarefa", labels=["task", "tem-dependencia"])
        self.snapshot = os.path.join(self.root, "labels.json")

    def test_needs_the_config_part_first(self):
        with self.assertRaises(BbError):
            migrate.labels_part(self.client, self.root, snapshot=self.snapshot)

    def test_renames_keeping_the_issues_copies_when_both_exist_and_creates_the_catalog(self):
        migrate.config_part(self.root)
        report = migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        self.assertIn(("epic", "type:epic"), report["renamed"])
        self.assertEqual(self.fake.label_names(10), ["qa:approved", "type:epic"])  # homologado existed as v3 too
        self.assertIn("homologado", self.fake.labels)  # nothing deleted while the migration is not finished
        self.assertIn("type:bug", self.fake.labels)  # the v3 catalog is complete
        self.assertEqual(report["replaced"], {"tem-dependencia": [11]})
        self.assertEqual(config_module.get(self.config(), "board.labels"), "v3")
        with open(self.snapshot, encoding="utf-8") as handle:
            self.assertIn("epic", json.load(handle)["renamed"])

    def test_rollback_restores_the_names(self):
        migrate.config_part(self.root)
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot)
        migrate.labels_part(self.client, self.root, snapshot=self.snapshot, rollback=True)
        self.assertIn("epic", self.fake.label_names(10))
        self.assertNotIn("type:epic", self.fake.label_names(10))
        self.assertNotIn("qa:approved", self.fake.label_names(10))
        self.assertEqual(config_module.get(self.config(), "board.labels"), "legacy")

    def test_dry_run_changes_nothing(self):
        migrate.config_part(self.root)
        report = migrate.labels_part(self.client, self.root, snapshot=self.snapshot, dry_run=True)
        self.assertIn("epic", self.fake.labels)
        self.assertNotIn("type:epic", self.fake.labels)
        self.assertTrue(report["renamed"])


class Board(Base):
    def setUp(self):
        super().setUp()
        self.fake.add_issue(10, "Épico em refinamento", labels=["type:epic", "approved:refinement"])
        self.fake.add_issue(12, "Épico aprovado", labels=["type:epic", "approved:refinement"])
        self.fake.add_issue(13, "Épico sem aprovação", labels=["type:epic"])
        self.fake.add_issue(14, "Tarefa com posse", labels=["type:task", "ia:claude-1"])
        self.fake.add_issue(15, "Tarefa sem posse", labels=["type:task"])
        self.fake.add_issue(16, "Bug novo", labels=["type:bug"])
        self.fake.add_issue(17, "Tarefa com PR", labels=["type:task"])
        self.fake.add_pull(70, "feature/17-x", "epico/12-aprovado")
        self.old = {28: FakeProject(), 29: FakeProject(), 30: FakeProject()}
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
        text = self.read("bigbang.toml").replace('labels = "legacy"', 'labels = "v3"', 1)
        self.write("bigbang.toml", text)

    def test_needs_the_labels_part_first(self):
        migrate.config_part(self.root)
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
    def ready(self):
        migrate.config_part(self.root)
        text = self.read("bigbang.toml").replace('labels = "legacy"', 'labels = "v3"', 1)
        text = text.replace('model = "three-boards"', 'model = "single"', 1)
        import re
        text = re.sub(r"(?m)^(planning|execution|bugs) = \d+[^\n]*\n", "", text)
        text = text.replace('labels = "v3"', 'labels = "v3"\nnumber = 7', 1)
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


if __name__ == "__main__":
    unittest.main()
