"""Delivery of the v3 grouping workflow (epics #230/#231, ADR-0022/0023): candidate ready, publish with the release
gate, maintenance publish, correction task after a QA rejection and cleanup. In-memory GitHub."""
import datetime
import os
import tempfile
import unittest

from _fake_github import FakeGitHub, FakeProject
from _raiz import importar_bb
from test_grouping_v3 import FLAGS_V3, cfg

importar_bb()
from bb import board, delivery, gh, locks, receipts  # noqa: E402
from bb.errors import BbError  # noqa: E402

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
TODAY = NOW.date()


class Base(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.client = gh.GitHub("dono/repo", api=self.fake)
        self.project = FakeProject()
        board.ensure_fields(self.project)
        for ref in ("develop", "main"):
            self.fake.refs[f"refs/heads/{ref}"] = ref[0] * 40
        self.fake.refs["refs/heads/release/1.3.0"] = "r" * 40
        self.fake.milestones[1] = {"number": 1, "title": "v1.3.0", "state": "open"}
        self.fake.add_issue(10, "Login", labels=["type:epic", "qa:human", "flag:required"])
        self.fake.add_issue(11, "Esteira", labels=["type:epic", "qa:not-applicable", "flag:waived"])
        self.fake.add_issue(20, "API", labels=["type:task"], parent=10, state="closed")
        self.fake.add_issue(21, "Página", labels=["type:docs"], parent=11, state="closed")
        for number in (10, 11, 20, 21):
            self.fake.issues[number]["milestone"] = 1
        for number in (10, 11):
            self.seed(number, ["Backlog", "Refinement", "Ready", "Selected", "In Progress"])

    def seed(self, number, targets):
        previous = board.current_state(self.client, number, {"dona"})
        for target in targets:
            self.client.comment(number, receipts.render({
                "kind": "transition", "event_id": f"seed-{number}-{target}", "issue": number, "actor": "dona",
                "at": "2026-10-10T11:00:00Z", "from": previous, "to": target, "sha": "0" * 40, "policy": "seed"}))
            previous = target

    def state(self, number):
        return board.current_state(self.client, number, {"dona"})


class CandidateReady(Base):
    def test_epics_go_to_qa_or_releasing_and_the_release_pr_opens_once(self):
        result = delivery.candidate_ready(self.client, self.project, cfg(), "release/1.3.0", "v1.3.0-rc.1", now=NOW)
        self.assertEqual(self.state(10), "QA")
        self.assertEqual(self.state(11), "Releasing")
        self.assertEqual(self.project.value(10, "Candidate"), "v1.3.0-rc.1")
        pulls = [p for p in self.fake.pulls.values() if p["head"]["ref"] == "release/1.3.0"]
        self.assertEqual(len(pulls), 1)
        self.assertEqual(pulls[0]["base"]["ref"], "main")
        self.assertTrue(any("v1.3.0-rc.1" in body for body in self.fake.comment_bodies(10)))
        delivery.candidate_ready(self.client, self.project, cfg(), "release/1.3.0", "v1.3.0-rc.2", now=NOW)
        self.assertEqual(len([p for p in self.fake.pulls.values() if p["head"]["ref"] == "release/1.3.0"]), 1)
        self.assertEqual(result["epics"], [10, 11])

    def test_an_epic_with_open_tasks_does_not_enter_qa(self):
        self.fake.add_issue(22, "Tela", labels=["type:task"], parent=10)
        self.fake.issues[22]["milestone"] = 1
        delivery.candidate_ready(self.client, self.project, cfg(), "release/1.3.0", "v1.3.0-rc.1", now=NOW)
        self.assertEqual(self.state(10), "In Progress")


class Publish(Base):
    def setUp(self):
        super().setUp()
        delivery.candidate_ready(self.client, self.project, cfg(), "release/1.3.0", "v1.3.0-rc.1", now=NOW)
        self.pr = next(p["number"] for p in self.fake.pulls.values() if p["head"]["ref"] == "release/1.3.0")
        self.fake.pulls[self.pr]["head"]["sha"] = "r" * 40  # the release PR's head is the candidate's commit
        self.fake.checks[self.fake.pulls[self.pr]["head"]["sha"]] = [
            {"name": "gate", "status": "completed", "conclusion": "success"}]
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, "flags.toml"), "w", encoding="utf-8") as handle:
            handle.write(FLAGS_V3)
        self.fake.refs["refs/tags/v1.3.0-rc.1"] = "r" * 40
        self.promoted = []

    def promote(self, rc_tag, tag, target_sha):
        self.promoted.append((rc_tag, tag, target_sha))

    def publish(self):
        return delivery.publish(self.client, self.project, cfg(), "1.3.0", self.root, today=TODAY, now=NOW,
                                pending={}, promote=self.promote)

    def test_the_same_candidate_is_promoted_after_the_merge(self):
        self.fake.refs["refs/tags/v1.3.0-rc.2"] = "r" * 40
        self.publish()
        self.assertEqual(self.promoted, [("v1.3.0-rc.2", "v1.3.0", "m" * 40)])

    def test_failed_promotion_concludes_nothing(self):
        def broken(*args):
            raise BbError("promoção falhou")
        with self.assertRaises(BbError):
            delivery.publish(self.client, self.project, cfg(), "1.3.0", self.root, today=TODAY, now=NOW,
                             pending={}, promote=broken)
        self.assertEqual(self.state(11), "Releasing")

    def test_open_blocking_issue_refuses(self):
        self.fake.add_issue(99, "Falha grave", labels=["type:bug", "blocks-production"])
        with self.assertRaises(BbError):
            self.publish()

    def test_release_changed_after_the_candidate_refuses(self):
        self.fake.refs["refs/heads/release/1.3.0"] = "x" * 40
        with self.assertRaises(BbError):
            self.publish()

    def test_dark_epic_ships_but_stays_in_qa_until_approved(self):
        result = self.publish()
        self.assertTrue(self.fake.pulls[self.pr]["merged"])
        self.assertEqual(self.state(11), "Done")  # docs epic, flag waived
        self.assertEqual(self.state(10), "QA")  # shipped dark: flag off in production, homologation pending
        self.assertIn(("develop", "main"), self.fake.merges)  # main returns to develop
        self.assertEqual(self.fake.milestones[1]["state"], "closed")
        self.assertEqual(result["dark"], [10])

    def test_approved_epic_with_flag_on_is_done(self):
        self.fake.issues[10]["labels"].append({"name": "qa:approved"})
        from bb import flags
        with open(os.path.join(self.root, "flags.toml"), "w", encoding="utf-8") as handle:
            handle.write(flags.switch(FLAGS_V3, "novo-login", "production", True, TODAY))
        self.publish()
        self.assertEqual(self.state(10), "Done")
        self.assertEqual(self.fake.issues[10]["state"], "closed")

    def test_gate_refuses_flag_on_without_approval(self):
        from bb import flags
        with open(os.path.join(self.root, "flags.toml"), "w", encoding="utf-8") as handle:
            handle.write(flags.switch(FLAGS_V3, "novo-login", "production", True, TODAY))
        with self.assertRaises(BbError):
            self.publish()
        self.assertFalse(self.fake.pulls[self.pr]["merged"])

    def test_gate_refuses_a_red_release_pr(self):
        self.fake.checks[self.fake.pulls[self.pr]["head"]["sha"]][0]["conclusion"] = "failure"
        with self.assertRaises(BbError):
            self.publish()

    def test_conflict_returning_main_opens_a_sync_pr(self):
        self.fake.conflicts.add(("develop", "main"))
        self.publish()
        self.assertTrue(any(p["head"]["ref"].startswith("sync/") and p["base"]["ref"] == "develop"
                            for p in self.fake.pulls.values()))

    def test_publishing_twice_is_harmless(self):
        self.publish()
        self.publish()
        self.assertEqual(self.fake.merges.count(("develop", "main")), 1)


class GateHardening(Publish):
    def test_unfinished_epic_without_a_flag_cannot_ship(self):
        self.fake.add_issue(12, "Ajustes", labels=["type:epic", "qa:not-applicable", "flag:waived"])
        self.fake.add_issue(24, "Tarefa aberta", labels=["type:task"], parent=12)
        self.fake.issues[12]["milestone"] = 1
        self.seed(12, ["Backlog", "Refinement", "Ready", "Selected", "In Progress"])
        with self.assertRaises(BbError) as error:
            self.publish()
        self.assertIn("#12", error.exception.message)
        self.assertFalse(self.fake.pulls[self.pr]["merged"])

    def test_any_flag_of_the_epic_on_in_production_counts(self):
        extra = FLAGS_V3.replace('name = "novo-login"', 'name = "novo-login-2"').replace(
            "production = false", "production = true")
        with open(os.path.join(self.root, "flags.toml"), "w", encoding="utf-8") as handle:
            handle.write(FLAGS_V3 + extra)
        with self.assertRaises(BbError) as error:
            self.publish()
        self.assertIn("novo-login-2", error.exception.message)

    def test_expired_flag_blocks_the_release(self):
        late = TODAY.replace(month=12)
        with self.assertRaises(BbError) as error:
            delivery.publish(self.client, self.project, cfg(), "1.3.0", self.root, today=late, now=NOW,
                             pending={}, promote=self.promote)
        self.assertIn("vencida", error.exception.message)

    def test_release_pr_head_must_be_the_candidate(self):
        self.fake.pulls[self.pr]["head"]["sha"] = "z" * 40
        self.fake.checks["z" * 40] = [{"name": "gate", "status": "completed", "conclusion": "success"}]
        with self.assertRaises(BbError):
            self.publish()

    def test_gate_reads_flags_and_pending_from_the_release_content(self):
        from unittest import mock
        from bb import flow_cli
        seen = {}

        def fake_publish(client, project, config, version, root, **kwargs):
            seen["root"] = root
            return {"pr": 1, "done": [], "dark": []}
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--raiz", default=".")
        commands = parser.add_subparsers(dest="command")
        flow_cli.register(commands, commands.add_parser("pipeline").add_subparsers(dest="pipeline_command"))
        args = parser.parse_args(["release", "publish", "--version", "1.3.0", "--dry-run",
                                  "--content-dir", self.root])
        with mock.patch.object(flow_cli, "_context", return_value=(cfg(), self.client, self.project)), \
                mock.patch.object(delivery, "publish", side_effect=fake_publish):
            args.handler(args)
        self.assertEqual(seen["root"], self.root)


class GeneratedWorkflows(unittest.TestCase):
    def test_no_expression_is_interpolated_into_a_shell_script(self):
        import re
        from _raiz import RAIZ
        base = os.path.join(RAIZ, ".bigbang", "pipeline")
        offenders = []
        for folder, _, files in os.walk(base):
            for name in files:
                if not re.search(r"\.ya?ml(\.tmpl)?$", name):
                    continue
                lines = open(os.path.join(folder, name), encoding="utf-8").read().split("\n")
                in_run, indent = False, 0
                for number, line in enumerate(lines, 1):
                    stripped = line.lstrip()
                    current = len(line) - len(stripped)
                    if in_run and stripped and current <= indent:
                        in_run = False
                    match = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", line)
                    if match:
                        indent = len(match.group(1))
                        if match.group(2).strip() in ("|", ">", "|-", ">-"):
                            in_run = True
                        elif "${{" in match.group(2):
                            offenders.append(f"{name}:{number}")
                        continue
                    if in_run and "${{" in line:
                        offenders.append(f"{name}:{number}")
        self.assertEqual(offenders, [])

    def test_publish_reads_the_release_content_and_buttons_simulate_first(self):
        from _raiz import RAIZ
        flows_dir = os.path.join(RAIZ, ".bigbang", "pipeline", "core", "files", ".github", "workflows")
        publish = open(os.path.join(flows_dir, "bb-publish.yml.tmpl"), encoding="utf-8").read()
        self.assertEqual(publish.count('--content-dir "$RUNNER_TEMP/release"'), 4)
        self.assertIn("^[0-9]+\\.[0-9]+\\.[0-9]+$", publish)
        for name in ("bb-qa-reject.yml", "bb-publish-maintenance.yml"):
            text = open(os.path.join(flows_dir, name), encoding="utf-8").read()
            self.assertIn("dry_run:", text)
            self.assertIn("default: true", text)


class DryRuns(Base):
    def test_qa_reject_dry_run_checks_and_changes_nothing(self):
        delivery.candidate_ready(self.client, self.project, cfg(), "release/1.3.0", "v1.3.0-rc.1", now=NOW)
        self.fake.issues[10]["labels"].append({"name": "qa:rejected"})
        before = len(self.fake.issues)
        delivery.correction_task(self.client, self.project, cfg(), 10, "x", actor="dona", now=NOW, dry_run=True)
        self.assertEqual(len(self.fake.issues), before)
        self.assertEqual(self.state(10), "QA")
        self.fake.issues[10]["labels"] = [l for l in self.fake.issues[10]["labels"] if l["name"] != "qa:rejected"]
        with self.assertRaises(BbError):
            delivery.correction_task(self.client, self.project, cfg(), 10, "x", actor="dona", now=NOW, dry_run=True)

    def test_maintenance_dry_run_merges_nothing(self):
        self.fake.add_pull(80, "maintenance/30-readme", "main", title="docs: readme", labels=["pr:approved"])
        self.fake.checks[self.fake.pulls[80]["head"]["sha"]] = [
            {"name": "gate", "status": "completed", "conclusion": "success"}]
        delivery.publish_maintenance(self.client, cfg(), 80, changed_paths=["README.md"], dry_run=True)
        self.assertFalse(self.fake.pulls[80]["merged"])


class Maintenance(Base):
    def test_maintenance_merges_into_main_without_artifact_changes(self):
        self.fake.add_issue(30, "Ajuste do README", labels=["type:task"])
        self.fake.add_pull(80, "maintenance/30-readme", "main", title="docs: readme", labels=["pr:approved"])
        self.fake.checks[self.fake.pulls[80]["head"]["sha"]] = [
            {"name": "gate", "status": "completed", "conclusion": "success"}]
        delivery.publish_maintenance(self.client, cfg(), 80, changed_paths=["README.md"])
        self.assertTrue(self.fake.pulls[80]["merged"])
        self.assertIn(("develop", "main"), self.fake.merges)

    def test_artifact_change_needs_a_release(self):
        self.fake.add_pull(81, "maintenance/31-x", "main", labels=["pr:approved"])
        self.fake.checks[self.fake.pulls[81]["head"]["sha"]] = [
            {"name": "gate", "status": "completed", "conclusion": "success"}]
        with self.assertRaises(BbError):
            delivery.publish_maintenance(self.client, cfg(), 81, changed_paths=["src/app.py"])


class Correction(Base):
    def test_qa_rejection_creates_a_correction_task_on_the_release_branch(self):
        delivery.candidate_ready(self.client, self.project, cfg(), "release/1.3.0", "v1.3.0-rc.1", now=NOW)
        with self.assertRaises(BbError):  # the rejection is the owner's decision
            delivery.correction_task(self.client, self.project, cfg(), 10, "x", actor="claude-1", now=NOW)
        self.fake.issues[10]["labels"].append({"name": "qa:rejected"})
        task = delivery.correction_task(self.client, self.project, cfg(), 10, "O botão some no celular",
                                        actor="dona", now=NOW)
        self.assertEqual(self.state(10), "In Progress")
        history = board.history(self.client, 10, {"dona"})
        self.assertEqual([m["to"] for m in history][-2:], ["Rejected", "In Progress"])
        self.assertIn("reason:qa", self.fake.label_names(10))
        issue = self.fake.issues[task]
        self.assertIn("type:task", self.fake.label_names(task))
        self.assertEqual(self.client.parent(task)["number"], 10)
        self.assertIn(f"refs/heads/fix/{task}-correcao-o-botao-some-no-celular", self.fake.refs)
        self.assertEqual(self.fake.refs[f"refs/heads/fix/{task}-correcao-o-botao-some-no-celular"], "r" * 40)
        self.assertEqual(issue["milestone"], 1)


class Cleanup(Base):
    def test_deletes_only_merged_branches_of_closed_issues_and_reports_old_claims(self):
        self.fake.refs["refs/heads/feature/20-api"] = "a" * 40            # closed issue, merged
        self.fake.add_issue(23, "Aberta", labels=["type:task"], parent=10)
        self.fake.refs["refs/heads/feature/23-aberta"] = "b" * 40         # open issue: kept
        self.fake.refs["refs/heads/docs/21-pagina"] = "c" * 40            # closed but not merged: kept
        self.fake.compares[("develop", "docs/21-pagina")] = ["docs: draft"]
        self.fake.compares[("main", "docs/21-pagina")] = ["docs: draft"]
        self.fake.refs["refs/heads/qualquer-coisa"] = "d" * 40            # outside the model: reported
        lock_api = self.client.locks()
        lock_api.acquire("issue-23", "claude-1", "s1", hours=1, now=NOW)
        report = delivery.cleanup(self.client, cfg(), now=NOW + datetime.timedelta(days=8), dry_run=False)
        self.assertEqual(report["deleted"], ["feature/20-api"])
        self.assertIn("refs/heads/feature/23-aberta", self.fake.refs)
        self.assertIn("refs/heads/docs/21-pagina", self.fake.refs)
        self.assertIn("qualquer-coisa", report["outside"])
        self.assertEqual(report["locks"], ["issue-23"])
        self.assertIn("refs/bigbang/locks/issue-23", self.fake.refs)  # lock refs are never deleted
        for protected in ("main", "develop", "release/1.3.0"):
            self.assertIn(f"refs/heads/{protected}", self.fake.refs)

    def test_dry_run_changes_nothing(self):
        self.fake.refs["refs/heads/feature/20-api"] = "a" * 40
        before = dict(self.fake.refs)
        report = delivery.cleanup(self.client, cfg(), now=NOW, dry_run=True)
        self.assertEqual(report["deleted"], ["feature/20-api"])
        self.assertEqual(self.fake.refs, before)


if __name__ == "__main__":
    unittest.main()


class QaVerdict(Base):
    def run_cli(self, *argv):
        import argparse
        from unittest import mock
        from bb import flow_cli
        parser = argparse.ArgumentParser()
        parser.add_argument("--raiz", default=".")
        commands = parser.add_subparsers(dest="command")
        pipeline_sub = commands.add_parser("pipeline").add_subparsers(dest="pipeline_command")
        flow_cli.register(commands, pipeline_sub)
        args = parser.parse_args(list(argv))
        config = cfg()
        config["agents"]["names"] = ["claude-1", "codex-1"]
        with mock.patch.object(flow_cli, "_context", return_value=(config, self.client, self.project)):
            return args.handler(args)

    def test_independent_agent_records_the_verdict_of_a_candidate(self):
        self.run_cli("qa", "verdict", "10", "--candidate", "v1.3.0-rc.1", "--digest", "sha256:aa",
                     "--verdict", "approved", "--agent", "codex-1")
        found = [r for r in receipts.parse(self.fake.comments.get(10, []), {"dona"}) if r["kind"] == "qa"]
        self.assertEqual([(r["approver"], r["verdict"]) for r in found], [("codex-1", "approved")])

    def test_unknown_agent_cannot_record_a_verdict(self):
        with self.assertRaises(BbError):
            self.run_cli("qa", "verdict", "10", "--candidate", "v1.3.0-rc.1", "--digest", "sha256:aa",
                         "--verdict", "approved", "--agent", "intruso")


class ContentAsData(unittest.TestCase):
    def test_links_leaving_the_pr_content_are_refused_before_any_read(self):
        from bb import flow_cli
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as content:
            secret = os.path.join(outside, "token.txt")
            with open(secret, "w", encoding="utf-8") as handle:
                handle.write("SEGREDO_FAKE\n")
            os.symlink(secret, os.path.join(content, "requirements.txt"))
            os.makedirs(os.path.join(content, "docs"))
            os.symlink("../README.md", os.path.join(content, "docs", "inside.md"))  # stays inside: allowed
            found = flow_cli._content_problems(None, cfg(), content, [], "feature/12-x")
            self.assertEqual(len(found), 1)
            self.assertIn("requirements.txt", found[0])
            self.assertNotIn("SEGREDO_FAKE", "".join(found))
