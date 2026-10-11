"""v3 modes in the gates (epic #232, ADR-0025): normal keeps every gate with the owner, Flash delegates common
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

    def test_outside_the_contract_only_the_owner_decision_unblocks(self):
        self.fake.issues[10]["labels"] += [{"name": "area:auth"}, {"name": "approved:backlog"}]
        receipt = self.move("Backlog", config(), actor="claude-1")
        self.assertEqual(receipt["approval"]["by"], "owner:dona")

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


class GeneratedMode(unittest.TestCase):
    def test_autonomous_agents_md_explains_the_contract(self):
        from test_grouping_v3 import GeneratedV3
        from bb import generator
        helper = GeneratedV3()
        with tempfile.TemporaryDirectory() as folder:
            root = helper.project(folder)
            path = os.path.join(root, "bigbang.toml")
            text = open(path, encoding="utf-8").read()
            self.assertIn("[project]\n", text)
            text = text.replace("[project]\n", '[project]\nmode = "autonomous"\n', 1)
            open(path, "w", encoding="utf-8").write(text)
            generator.apply(generator.build_plan(root, install_pipeline=True), root)
            agents = open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read()
            self.assertIn("Modo autônomo", agents)
            self.assertIn("autonomy.toml", agents)
            self.assertIn("bb autonomy check", agents)


class Hardening(unittest.TestCase):
    def rules(self, paths, mode="autonomous", labels=(), flags_by_agent=False):
        from bb import pipeline
        return pipeline.v3_pr_rules("feature/12-x", "develop", "chore: x", "Refs #12", set(labels), list(paths), "",
                                    ["src/"], [], "test.failing", {"type:task"}, {"type:epic", "flag:waived"},
                                    mode, flags_by_agent=flags_by_agent)

    def test_owner_files_always_need_the_owner_review(self):
        for mode in ("normal", "flash", "autonomous"):
            for path in ("autonomy.toml", "bigbang.toml", "PRODUTO.md", "STACK.md", "DESIGN.md", "flags.toml"):
                _, add, _ = self.rules([path], mode=mode)
                self.assertIn("review:human", add, f"{mode} {path}")
        _, add, _ = self.rules(["autonomy.toml"], labels=["owner:ai-review"])
        self.assertIn("review:human", add)  # the contract itself is never delegated

    def test_contract_flags_agent_lets_the_agent_switch_flags(self):
        _, add, _ = self.rules(["flags.toml"], flags_by_agent=True)
        self.assertNotIn("review:human", add)

    def test_wrong_types_block_with_a_message_instead_of_crashing(self):
        for bad in ('risk = 5', 'gates = 5', 'targets = [1]', 'version = true', 'version = 1.0'):
            key = bad.split(" = ")[0]
            text = "\n".join(line for line in CONTRACT.splitlines() if not line.startswith(key + " ")) + "\n" + bad
            cfg = config(contract=text)
            self.assertTrue(autonomy.problems(cfg, TODAY), bad)
            self.assertIsNone(autonomy.usable(cfg, TODAY))
            self.assertTrue(autonomy.publish_problems(cfg, "production", NOW), bad)

    def test_unreadable_contract_blocks(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "autonomy.toml"))
        cfg = autonomy.attach({k: v for k, v in config(contract=None).items() if k != autonomy.KEY}, root)
        self.assertTrue(autonomy.problems(cfg, TODAY))

    def test_limits_come_only_from_a_usable_contract(self):
        from bb import policy
        expired = config(contract=CONTRACT.replace("2026-12-31", "2026-01-01").replace("wip = 1", "wip = 99"))
        self.assertEqual(policy.limits(expired)["epics_in_progress"], 2)


class WipAndBootstrap(Bootstrap):
    def test_wip_of_the_contract_limits_epics_in_progress(self):
        project = FakeProject()
        board.ensure_fields(project)
        for number in (10, 11):
            self.fake.add_issue(number, f"Épico {number}", labels=["type:epic"])
            self.fake.add_issue(number + 10, "Tarefa", labels=["type:task"], parent=number)
            previous = "Brainstorm"
            for target in ("Backlog", "Refinement", "Ready", "Selected"):
                self.client.comment(number, receipts.render({
                    "kind": "transition", "event_id": f"s-{number}-{target}", "issue": number, "actor": "dona",
                    "at": "2026-10-10T11:00:00Z", "from": previous, "to": target, "policy": "x"}))
                previous = target
        cfg = config()  # wip = 1
        board.move(self.client, project, cfg, 10, "In Progress", "claude-1", now=NOW)
        with self.assertRaises(BbError) as error:
            board.move(self.client, project, cfg, 11, "In Progress", "claude-1", now=NOW)
        self.assertIn("WIP", error.exception.message)

    def test_unknown_plan_of_a_private_repository_refuses(self):
        self.fake.repo = {"private": True, "visibility": "private", "owner": {"login": "dona", "type": "User"}}
        self.fake.user = {"login": "outra"}  # token of someone else, or no plan visible
        self.assertTrue(any("plano" in item for item in autonomy.bootstrap_problems(self.client)))

    def test_a_tag_policy_named_main_is_not_the_main_branch(self):
        self.fake.environment_branches["production"] = [{"name": "main", "type": "tag"}]
        self.assertTrue(any("production" in item for item in autonomy.bootstrap_problems(self.client)))

    def test_a_ruleset_with_bypass_actors_does_not_count(self):
        for branch in ("main", "develop"):
            for rule in self.fake.branch_rules[branch]:
                rule["ruleset_id"] = 5
        self.fake.rulesets = {5: {"id": 5, "bypass_actors": [{"actor_type": "Integration", "actor_id": 1}]}}
        found = autonomy.bootstrap_problems(self.client)
        self.assertTrue(any("bypass" in item for item in found))


class ReviewOfOwnerFiles(unittest.TestCase):
    def blockers(self, paths, pr_labels=(), issue_labels=(), mode="flash", **kwargs):
        from bb import decisions
        return decisions.review_blockers(set(pr_labels), set(issue_labels), "feature/12-x", list(paths), "", [],
                                         "test.failing", mode, **kwargs)

    def test_the_contract_is_never_approved_by_an_agent(self):
        for labels in ((), ("owner:ai-review",), ("dono:revisao-ia",)):
            for mode in ("padrao", "flash"):
                self.assertTrue(self.blockers(["autonomy.toml"], pr_labels=labels, mode=mode), (labels, mode))

    def test_owner_files_of_a_v3_project_need_the_owner_unless_he_delegated_this_pr(self):
        self.assertTrue(self.blockers(["STACK.md"], owner_files=True))
        self.assertTrue(self.blockers(["STACK.md"], issue_labels=("owner:ai-review",), owner_files=True))  # inherited
        self.assertEqual(self.blockers(["STACK.md"], pr_labels=("owner:ai-review",), owner_files=True), [])
        self.assertEqual(self.blockers(["flags.toml"], owner_files=True, flags_by_agent=True), [])
        self.assertEqual(self.blockers(["STACK.md"]), [])  # legacy flash projects keep their behavior

    def test_merge_with_human_review_needs_the_recorded_owner_decision(self):
        from _fake_github import FakeGitHub as Fake
        from bb import flows
        fake = Fake()
        client = gh.GitHub("dono/repo", api=fake)
        fake.add_issue(60, "PR (issues and PRs share numbers)")
        fake.add_pull(60, "feature/30-tarefa", "develop", title="feat: tarefa", labels=["pr:approved", "review:human"])
        fake.checks[fake.pulls[60]["head"]["sha"]] = [{"name": "gate", "status": "completed", "conclusion": "success"}]
        cfg = config(mode="normal")
        with self.assertRaises(BbError) as error:
            flows.merge_pr(client, cfg, 60)
        self.assertIn("review:human", error.exception.message)
        fake.author = "dona"
        client.comment(60, "**Decisão do dono:** `pr:approved`\n\n> pode mesclar\n\nRegistrada por `claude-1`.")
        flows.merge_pr(client, cfg, 60)
        self.assertTrue(fake.pulls[60]["merged"])


class BootstrapResiduals(Bootstrap):
    def test_unseen_bypass_list_refuses(self):
        for branch in ("main", "develop"):
            for rule in self.fake.branch_rules[branch]:
                rule["ruleset_id"] = 6
        self.fake.rulesets = {6: {"id": 6}}  # bypass_actors only shown to who can edit the ruleset
        self.assertTrue(any("bypass" in item for item in autonomy.bootstrap_problems(self.client)))

    def test_private_repository_of_a_free_or_unknown_organization_refuses(self):
        self.fake.repo = {"private": True, "visibility": "private", "owner": {"login": "org", "type": "Organization"}}
        self.assertTrue(any("plano" in item for item in autonomy.bootstrap_problems(self.client)))


class FrameworkContract(unittest.TestCase):
    """The real autonomy.toml of the repository (#305): valid, and it must not make the framework unpublishable."""

    def test_root_contract_is_valid_and_lets_the_owner_publish(self):
        import tomllib
        from _raiz import RAIZ
        from bb import policy
        with open(os.path.join(RAIZ, "autonomy.toml"), "rb") as handle:
            contract = tomllib.load(handle)
        self.assertEqual(policy.contract_problems(contract, datetime.date(2026, 10, 11)), [])
        loaded = config(root=RAIZ, contract=None)
        loaded["_autonomy"] = contract
        self.assertEqual(autonomy.publish_problems(loaded, "production", NOW), [])
        self.assertIn("publish", contract["gates"])
        self.assertEqual(contract["flags"], "owner")
        self.assertNotIn("high", contract["risk"])
        self.assertNotIn("critical", contract["risk"])
