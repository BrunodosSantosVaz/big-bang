"""v3 modes in the gates (epic #232, ADR-0025/0027): normal keeps every gate with the owner, Flash delegates common
work, autonomous acts only inside a valid autonomy.toml read from the trusted branch; the bootstrap refuses an
account that cannot enforce the controls; every gated receipt says who approved. In-memory GitHub."""
import datetime
import os
import tempfile
import unittest

from _fake_github import FakeGitHub, FakeProject
from _raiz import importar_bb
from test_delivery_v3 import NOW, TODAY, Publish

importar_bb()
from bb import autonomy, board, claims, delivery, gh, receipts  # noqa: E402
from bb.errors import BbError  # noqa: E402

CONTRACT = """version = 1
targets = ["production"]
risk = ["low", "medium"]
gates = ["backlog", "refinement", "prototype", "selection", "tests", "pr", "qa", "publish", "flag"]
flags = "agent"
wip = 1
attempts = 2
max_cost_usd = 20
publish_window = "09:00-18:00"
expires = "2026-12-31"
"""


def config(mode="autonomous", contract=CONTRACT, root=None):
    data = {"project": {"repository": "dono/repo", "owner": "dona", "mode": mode},
            "agents": {"names": ["claude-1", "codex-1"], "tasks_per_agent": 2, "lease_hours": 2},
            "workflow": {"model": "grouping"}, "board": {"labels": "v3", "model": "single", "number": 7,
                                                         "owner": "dona"},
            "security": {"sensitive_paths": []}, "delivery": {"profile": "deploy"}}
    if root is None:
        root = tempfile.mkdtemp()
    if contract is not None:
        with open(os.path.join(root, "autonomy.toml"), "w", encoding="utf-8") as handle:
            handle.write(contract)
    return autonomy.attach(data, root)


class Contract(unittest.TestCase):
    def test_loaded_only_in_autonomous_mode_and_validated(self):
        self.assertIsNone(autonomy.contract_of(config(mode="flash")))
        self.assertEqual(autonomy.contract_of(config())["wip"], 1)
        broken = config(contract="version = 1\nrisk = [\"low\"]\n")
        self.assertTrue(autonomy.problems(broken, TODAY))
        self.assertEqual(autonomy.problems(config(contract=None), TODAY),
                         ["modo autonomous sem autonomy.toml: nada é delegado (tudo bloqueado)"])

    def test_contract_limits_replace_the_defaults(self):
        from bb import policy
        self.assertEqual(policy.limits(config())["attempts"], 2)
        self.assertEqual(policy.limits(config())["epics_in_progress"], 1)
        self.assertEqual(policy.limits(config(mode="flash"))["attempts"], 3)

    def test_publish_needs_the_window_and_the_target(self):
        inside = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=datetime.timezone.utc)
        outside = datetime.datetime(2026, 10, 10, 20, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(autonomy.publish_problems(config(), "production", inside), [])
        self.assertTrue(autonomy.publish_problems(config(), "production", outside))
        self.assertTrue(autonomy.publish_problems(config(), "staging", inside))
        self.assertEqual(autonomy.publish_problems(config(mode="normal"), "production", outside), [])
        self.assertTrue(autonomy.publish_problems(config(contract=None), "production", inside))


class Gates(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.client = gh.GitHub("dono/repo", api=self.fake)
        self.project = FakeProject()
        board.ensure_fields(self.project)
        self.fake.add_issue(10, "Login", labels=["type:epic"])

    def move(self, target, cfg, actor="claude-1"):
        return board.move(self.client, self.project, cfg, 10, target, actor, now=NOW)

    def test_inside_the_contract_the_agent_approves_and_the_receipt_says_so(self):
        cfg = config()
        receipt = self.move("Backlog", cfg)
        self.assertEqual(receipt["approval"], {"gate": "backlog", "by": "agent:claude-1", "risk": "medium",
                                               "mode": "autonomous"})

    def test_without_a_valid_contract_everything_is_blocked(self):
        for cfg in (config(contract=None), config(contract=CONTRACT.replace("2026-12-31", "2026-01-01"))):
            with self.assertRaises(BbError) as error:
                self.move("Backlog", cfg)
            self.assertIn("bloqueado", error.exception.message)

    def test_risk_outside_the_contract_is_blocked_not_delegated(self):
        self.fake.issues[10]["labels"].append({"name": "area:auth"})  # planning risk high, contract stops at medium
        with self.assertRaises(BbError) as error:
            self.move("Backlog", config())
        self.assertIn("bloqueado", error.exception.message)

    def test_owner_decision_is_recorded_as_the_owner(self):
        self.fake.issues[10]["labels"].append({"name": "approved:backlog"})
        receipt = self.move("Backlog", config(mode="normal"), actor="dona")
        self.assertEqual(receipt["approval"]["by"], "owner:dona")
        self.assertEqual(receipt["approval"]["mode"], "normal")


class AutonomousPublish(Publish):
    def test_publish_outside_the_window_is_refused_in_autonomous_mode(self):
        cfg = config(root=self.root)
        late = datetime.datetime(2026, 10, 10, 20, 0, tzinfo=datetime.timezone.utc)
        with self.assertRaises(BbError) as error:
            delivery.publish(self.client, self.project, cfg, "1.3.0", self.root, today=TODAY, now=late,
                             pending={}, promote=self.promote)
        self.assertIn("janela", error.exception.message)
        self.assertEqual(self.promoted, [])


class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.client = gh.GitHub("dono/repo", api=self.fake)
        self.fake.repo = {"private": False, "visibility": "public", "owner": {"login": "dona", "type": "User"}}
        self.fake.branch_rules = {"main": [{"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": "gate"}]}}], "develop": [{"type": "required_status_checks",
                                                                            "parameters": {"required_status_checks": [{"context": "gate"}]}}]}
        self.fake.environments = {"production": {"name": "production", "deployment_branch_policy": {
            "protected_branches": False, "custom_branch_policies": True}}}
        self.fake.environment_branches = {"production": [{"name": "main"}]}

    def test_controls_in_place_pass(self):
        self.assertEqual(autonomy.bootstrap_problems(self.client), [])

    def test_missing_gate_rule_or_open_environment_refuse(self):
        self.fake.branch_rules["develop"] = []
        self.fake.environment_branches["production"] = [{"name": "main"}, {"name": "*"}]
        found = autonomy.bootstrap_problems(self.client)
        self.assertTrue(any("develop" in item for item in found))
        self.assertTrue(any("production" in item for item in found))

    def test_private_repository_on_a_free_personal_plan_refuses(self):
        self.fake.repo = {"private": True, "visibility": "private", "owner": {"login": "dona", "type": "User"}}
        self.fake.user = {"login": "dona", "plan": {"name": "free"}}
        found = autonomy.bootstrap_problems(self.client)
        self.assertTrue(any("Free" in item for item in found))

    def test_missing_environment_refuses(self):
        self.fake.environments = {}
        self.assertTrue(any("production" in item for item in autonomy.bootstrap_problems(self.client)))


if __name__ == "__main__":
    unittest.main()


class Commands(Bootstrap):
    def run_cli(self, cfg, *argv):
        import argparse
        from unittest import mock
        from bb import flow_cli
        parser = argparse.ArgumentParser()
        parser.add_argument("--raiz", default=".")
        commands = parser.add_subparsers(dest="command")
        pipeline_sub = commands.add_parser("pipeline").add_subparsers(dest="pipeline_command")
        flow_cli.register(commands, pipeline_sub)
        args = parser.parse_args(["--raiz", self.root] + list(argv))
        with mock.patch.object(flow_cli.config_module, "load", return_value=cfg), \
                mock.patch.object(flow_cli.gh, "GitHub", return_value=self.client), \
                mock.patch.object(flow_cli.gh, "graphql", side_effect=AssertionError("no GraphQL here")):
            return args.handler(args)

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp()

    def test_every_command_sees_the_contract_of_the_checkout(self):
        from bb import flow_cli
        with open(os.path.join(self.root, "autonomy.toml"), "w", encoding="utf-8") as handle:
            handle.write(CONTRACT)
        from unittest import mock
        plain = {k: v for k, v in config(contract=None).items() if k != autonomy.KEY}
        with mock.patch.object(flow_cli.config_module, "load", return_value=plain):
            self.assertEqual(autonomy.contract_of(flow_cli._load(self.root))["wip"], 1)

    def test_autonomy_check_reports_contract_and_bootstrap(self):
        plain = {k: v for k, v in config(contract=None).items() if k != autonomy.KEY}
        self.fake.branch_rules["main"] = []
        with self.assertRaises(BbError) as error:
            self.run_cli(plain, "autonomy", "check")
        self.assertIn("autonomy.toml", error.exception.message)
        self.assertIn("main", error.exception.message)

    def test_board_create_refuses_autonomous_mode_without_the_controls(self):
        plain = {k: v for k, v in config(contract=None).items() if k != autonomy.KEY}
        self.fake.environments = {}
        with self.assertRaises(BbError) as error:
            self.run_cli(plain, "board", "create", "--title", "Sistema")
        self.assertIn("production", error.exception.message)
