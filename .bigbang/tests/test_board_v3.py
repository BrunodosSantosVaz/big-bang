"""v3 single board (epic #227, ADR-0023/0026): label catalog, project fields, state derived from receipts, moves
validated by the core rules, and the controller reacting to issue, PR and schedule events. In-memory GitHub."""
import datetime
import unittest

from _fake_github import FakeGitHub, FakeProject
from _raiz import importar_bb

importar_bb()
from bb import board, claims, controller, gh, names, policy, receipts, states  # noqa: E402
from bb.errors import BbError  # noqa: E402

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def config(mode="normal"):
    return {"project": {"repository": "dono/repo", "owner": "dona", "mode": mode},
            "agents": {"names": ["claude-1"], "tasks_per_agent": 2, "lease_hours": 2},
            "workflow": {"model": "grouping"}, "board": {"labels": "v3", "model": "single", "number": 7,
                                                           "owner": "dona"},
            "security": {"sensitive_paths": []}, "delivery": {"profile": "deploy"}}


class Base(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.client = gh.GitHub("dono/repo", api=self.fake)
        self.project = FakeProject()
        board.ensure_fields(self.project)
        self.fake.add_issue(10, "Login", labels=["type:epic"])
        self.fake.add_issue(11, "Testes", labels=["type:test"], parent=10)
        self.fake.add_issue(12, "Tela", labels=["type:task"], parent=10, blocked_by=[11])

    def move(self, number, target, actor="dona", mode="normal", **kwargs):
        return board.move(self.client, self.project, config(mode), number, target, actor, now=NOW, **kwargs)

    def state(self, number):
        return board.current_state(self.client, number, {"dona"})


class Catalog(Base):
    def test_catalog_covers_every_v3_label_the_rules_read(self):
        catalog = {entry[0] for entry in board.LABELS}
        for label in set(names.LABELS.values()) | set(names.DECISIONS):
            self.assertIn(label, catalog)
        for label in ("risk:low", "risk:critical", "qa:human", "qa:not-applicable", "flag:required",
                      "flag:waived", "blocked", "on-hold", "expedite", "reason:qa", "area:auth"):
            self.assertIn(label, catalog)
        for name, color, description in board.LABELS:
            self.assertRegex(color, r"^[0-9A-F]{6}$", name)
            self.assertTrue(description.strip(), name)
        self.assertEqual(len(catalog), len(board.LABELS))

    def test_labels_command_is_idempotent(self):
        created = board.ensure_labels(self.client)
        self.assertEqual(created, len(board.LABELS) - 3)  # type:epic/test/task already existed in the fake
        self.assertEqual(board.ensure_labels(self.client), 0)

    def test_project_fields_and_fifteen_states(self):
        fields = self.project.fields()
        self.assertEqual([option for option in fields["Status"]["options"]], list(states.STATES))
        for name in ("Priority", "Size", "Sprint", "Awaiting", "QA decision", "Prototype", "Flag", "Executor",
                     "Session", "Lease expires", "Attempt", "Rejected from", "Return to", "Tested SHA", "Candidate"):
            self.assertIn(name, fields)
        board.ensure_fields(self.project)  # idempotent
        self.assertEqual(len(self.project.fields()), len(fields))


class Moves(Base):
    def test_initial_state_by_kind(self):
        self.assertEqual(self.state(10), "Brainstorm")
        self.assertEqual(self.state(11), "Todo")
        self.fake.add_issue(20, "Bug", labels=["type:bug"])
        self.assertEqual(self.state(20), "Brainstorm")

    def approve(self, number, label):
        self.fake.issues[number]["labels"].append({"name": label})

    def test_owner_moves_epic_through_planning_with_receipts_and_board(self):
        self.approve(10, "approved:backlog")
        self.move(10, "Backlog")
        self.assertEqual(self.state(10), "Backlog")
        self.assertEqual(self.project.status(10), "Backlog")
        with self.assertRaises(BbError):  # refinement needs a claim
            self.move(10, "Refinement")
        claims.claim(self.client, config(), 10, "dona", person=True, now=NOW)
        self.move(10, "Refinement")
        kinds = [r["kind"] for r in receipts.parse(self.fake.comments[10], {"dona"})]
        self.assertEqual(kinds, ["transition", "claim", "transition"])

    def test_agent_cannot_pass_an_owner_gate_in_normal_mode(self):
        with self.assertRaises(BbError) as error:
            self.move(10, "Backlog", actor="claude-1")
        self.assertIn("dono", error.exception.message)

    def test_claiming_to_be_the_owner_is_not_an_approval(self):
        with self.assertRaises(BbError):
            self.move(10, "Backlog", actor="dona")  # only a recorded decision approves an owner gate

    def test_flash_sensitive_refinement_goes_to_the_owner(self):
        self.approve(10, "approved:backlog")
        self.move(10, "Backlog", mode="flash")
        claims.claim(self.client, config("flash"), 10, "claude-1", now=NOW)
        self.move(10, "Refinement", actor="claude-1", mode="flash")
        self.fake.issues[10]["labels"] += [{"name": "prototype:waived"}, {"name": "flag:waived"},
                                           {"name": "area:auth"}]
        with self.assertRaises(BbError):  # area:auth makes the refinement critical: owner decision needed
            self.move(10, "Ready", actor="claude-1", mode="flash")
        self.fake.issues[10]["labels"] = [label for label in self.fake.issues[10]["labels"]
                                          if label["name"] != "area:auth"]
        self.move(10, "Ready", actor="claude-1", mode="flash")  # common refinement: delegated in Flash
        self.assertEqual(self.state(10), "Ready")

    def test_qa_rejection_and_epic_cancellation_need_the_owner_decision(self):
        for target in ("Backlog",):
            self.approve(10, "approved:backlog")
            self.move(10, target)
        with self.assertRaises(BbError):
            self.move(10, "Cancelled", actor="claude-1", reason="fora do escopo")
        self.fake.add_issue(40, "Bug", labels=["type:bug"])
        with self.assertRaises(BbError):  # cancelling a reported bug is also the owner's decision
            self.move(40, "Cancelled", actor="claude-1", reason="não reproduz")
        self.approve(10, "approved:cancel")
        self.move(10, "Cancelled", actor="claude-1", reason="fora do escopo")
        self.assertEqual(self.state(10), "Cancelled")

    def test_a_rejection_withdraws_the_decisions_from_the_return_stage_on(self):
        self.approve(10, "approved:backlog")
        self.move(10, "Backlog")
        claims.claim(self.client, config(), 10, "claude-1", now=NOW)
        self.move(10, "Refinement", actor="claude-1")
        self.fake.issues[10]["labels"] += [{"name": "prototype:required"}, {"name": "approved:refinement"}]
        self.move(10, "Prototyping", actor="claude-1")
        self.move(10, "Rejected", actor="claude-1", reason="requirements", return_to="Refinement")
        self.assertNotIn("approved:refinement", self.fake.label_names(10))
        self.move(10, "Refinement", actor="claude-1")
        with self.assertRaises(BbError):  # the old approval does not approve the new cycle
            self.move(10, "Prototyping", actor="claude-1")

    def test_qa_and_publish_risk_come_from_the_changed_paths(self):
        self.fake.issues[10]["labels"] += [{"name": "area:ui"}, {"name": "qa:human"}]
        self.fake.issues[11]["state"] = "closed"
        self.fake.issues[12]["state"] = "closed"
        self.fake.add_pull(70, "feature/12-tela", "develop", state="closed", merged=True)
        self.fake.pulls[70]["files"] = [{"filename": "migrations/0002.sql"}]
        for target in ("Backlog", "Refinement", "Ready", "Selected", "In Progress"):
            from bb import receipts as r
            previous = self.state(10)
            self.client.comment(10, r.render({"kind": "transition", "event_id": f"s-{target}", "issue": 10,
                                              "actor": "dona", "at": "2026-10-10T11:00:00Z", "from": previous,
                                              "to": target, "policy": "x"}))
        self.move(10, "QA", actor="claude-1", mode="flash", facts={"candidate": True})
        self.assertEqual(policy.delivery_risk({"area:ui"}), "high")  # an area never lowers the default
        with self.assertRaises(BbError):  # migrations make the QA critical: the owner homologates
            self.move(10, "Releasing", actor="claude-1", mode="flash")

    def _epic_in_progress(self, labels, path):
        from bb import receipts as r
        self.fake.issues[10]["labels"] += [{"name": label} for label in labels]
        self.fake.issues[11]["state"] = "closed"
        self.fake.issues[12]["state"] = "closed"
        self.fake.add_pull(71, "feature/12-tela", "develop", state="closed", merged=True)
        self.fake.pulls[71]["files"] = [{"filename": path}]
        for target in ("Backlog", "Refinement", "Ready", "Selected", "In Progress"):
            previous = self.state(10)
            self.client.comment(10, r.render({"kind": "transition", "event_id": f"s-{target}", "issue": 10,
                                              "actor": "dona", "at": "2026-10-10T11:00:00Z", "from": previous,
                                              "to": target, "policy": "x"}))

    def test_flash_qa_human_stays_with_the_owner_at_any_risk(self):
        self._epic_in_progress(["qa:human"], "src/app.py")  # medium risk: delegable, but the card asks the owner
        self.move(10, "QA", actor="claude-1", mode="flash", facts={"candidate": True})
        with self.assertRaises(BbError) as error:
            self.move(10, "Releasing", actor="claude-1", mode="flash")
        self.assertIn("qa:approved", error.exception.message)
        self.approve(10, "qa:approved")
        self.move(10, "Releasing", actor="claude-1", mode="flash")

    def test_flash_delegated_qa_needs_an_independent_qa_receipt(self):
        self._epic_in_progress(["qa:agent"], "src/app.py")
        board.record_qa(self.client, config("flash"), 10, candidate="v1.2.0-rc.1", digest="sha256:aa",
                        verdict="approved", approver="claude-1", now=NOW)  # before QA: an old cycle
        self.move(10, "QA", actor="claude-1", mode="flash", facts={"candidate": True})
        with self.assertRaises(BbError):  # no evidence of this cycle
            self.move(10, "Releasing", actor="claude-1", mode="flash")
        board.record_qa(self.client, config("flash"), 10, candidate="v1.2.0-rc.1", digest="sha256:aa",
                        verdict="rejected", approver="codex-1", now=NOW)
        with self.assertRaises(BbError):  # a rejected verdict is not an approval
            self.move(10, "Releasing", actor="claude-1", mode="flash")
        board.record_qa(self.client, config("flash"), 10, candidate="v1.2.0-rc.1", digest="sha256:aa",
                        verdict="approved", approver="claude-1", now=NOW)
        with self.assertRaises(BbError):  # the agent that delivers never homologates its own work
            self.move(10, "Releasing", actor="claude-1", mode="flash")
        board.record_qa(self.client, config("flash"), 10, candidate="v1.2.0-rc.1", digest="sha256:aa",
                        verdict="approved", approver="codex-1", now=NOW)
        self.move(10, "Releasing", actor="claude-1", mode="flash")
        with self.assertRaises(BbError):
            board.record_qa(self.client, config("flash"), 10, candidate="", digest="sha256:aa",
                            verdict="approved", approver="codex-1", now=NOW)

    def test_going_back_without_rejection_also_withdraws_the_decisions(self):
        self.approve(10, "approved:backlog")
        self.move(10, "Backlog")
        self.move(10, "Refinement")
        self.fake.issues[10]["labels"] += [{"name": "prototype:waived"}, {"name": "flag:waived"}]
        self.approve(10, "approved:refinement")
        self.move(10, "Ready")
        self.approve(10, "approved:selection")
        self.move(10, "Selected")
        self.move(10, "Ready", actor="claude-1")
        self.assertNotIn("approved:selection", self.fake.label_names(10))
        with self.assertRaises(BbError):  # the old selection does not select the epic again
            self.move(10, "Selected", actor="claude-1")
        self.move(10, "Refinement", actor="claude-1")
        self.assertNotIn("approved:refinement", self.fake.label_names(10))
        with self.assertRaises(BbError):
            self.move(10, "Ready", actor="claude-1")

    def test_effects_happen_before_the_receipt(self):
        self.fake.failures.add(("PATCH", "issues/11"))
        with self.assertRaises(BbError):
            self.move(11, "Cancelled", reason="duplicada")
        self.assertEqual(self.state(11), "Todo")  # no receipt for an effect that did not happen
        self.fake.failures.clear()
        self.move(11, "Cancelled", reason="duplicada")
        self.assertEqual(self.state(11), "Cancelled")

    def test_attempts_come_from_receipts_and_the_limit_blocks(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        self.move(11, "Coding", actor="claude-1")
        for attempt in range(1, 5):
            self.move(11, "In Review", actor="claude-1", facts={"pr_open": True})
            self.move(11, "Rejected", actor="claude-1", reason="tests", return_to="Coding")
            if attempt < 3:
                self.move(11, "Coding", actor="claude-1")
            else:
                break
        self.assertIn("blocked", self.fake.label_names(11))
        self.assertEqual(board.attempts(self.client, 11, {"dona"}), 3)

    def test_agent_passes_common_gates_in_flash(self):
        self.move(10, "Backlog", actor="claude-1", mode="flash")  # planning risk medium: delegated
        self.assertEqual(self.state(10), "Backlog")

    def test_decision_label_is_the_owner_approval(self):
        self.approve(10, "approved:backlog")
        self.move(10, "Backlog")
        claims.claim(self.client, config(), 10, "claude-1", now=NOW)
        self.move(10, "Refinement", actor="claude-1")
        self.fake.issues[10]["labels"] += [{"name": "prototype:waived"}, {"name": "flag:waived"}]
        with self.assertRaises(BbError):
            self.move(10, "Ready", actor="claude-1")
        self.fake.issues[10]["labels"].append({"name": "approved:refinement"})
        self.move(10, "Ready", actor="claude-1")
        self.assertEqual(self.state(10), "Ready")

    def test_task_done_closes_the_issue_and_cancelled_is_not_planned(self):
        self.fake.issues[11]["labels"].append({"name": "agent:claude-1"})
        self.move(11, "Cancelled", reason="coberto pela #13")
        self.assertEqual((self.fake.issues[11]["state"], self.fake.issues[11]["state_reason"]),
                         ("closed", "not_planned"))
        self.assertEqual(self.state(11), "Cancelled")

    def test_rejection_records_reason_label_and_return(self):
        facts = {"pr_open": True}
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        self.move(11, "Coding", actor="claude-1")
        self.move(11, "In Review", actor="claude-1", facts=facts)
        self.move(11, "Rejected", actor="claude-1", reason="tests", return_to="Todo")
        self.assertEqual(self.state(11), "Rejected")
        claims.unclaim(self.client, config(), {"issue": 11, "name": "claude-1", "session":
                       self.client.locks().current("issue-11")["session"], "generation": 1}, now=NOW)
        self.assertIn("reason:tests", self.fake.label_names(11))
        self.assertEqual(self.project.value(11, "Rejected from"), "In Review")
        self.assertEqual(self.project.value(11, "Return to"), "Todo")
        with self.assertRaises(BbError):
            self.move(11, "Coding", actor="claude-1")
        self.move(11, "Todo", actor="claude-1")
        self.assertEqual(self.project.value(11, "Attempt"), 1)
        self.assertEqual(board.attempts(self.client, 11, {"dona"}), 1)

    def test_replayed_event_writes_nothing_new(self):
        self.approve(10, "approved:backlog")
        self.move(10, "Backlog", event_id="evt-1")
        before = len(self.fake.comments[10])
        result = self.move(10, "Backlog", event_id="evt-1")
        self.assertEqual(len(self.fake.comments[10]), before)
        self.assertEqual(result["to"], "Backlog")

    def test_blocked_task_cannot_start(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)  # the blocker itself can be claimed
        self.fake.refs["refs/heads/feature/12-tela"] = "b" * 40
        with self.assertRaises(BbError):
            claims.claim(self.client, config(), 12, "claude-1", now=NOW)

    def test_facts_from_github(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        facts = board.facts(self.client, config(), 11, now=NOW)
        self.assertTrue(facts["claimed"])
        self.assertTrue(facts["branch"])
        self.assertEqual(facts["blocked_by_open"], 0)
        epic = board.facts(self.client, config(), 10, now=NOW)
        self.assertEqual((epic["subissues_total"], epic["subissues_open"]), (2, 2))


class Controller(Base):
    def event(self, name, **payload):
        return controller.handle(self.client, self.project, config("flash"), name, payload, now=NOW)

    def test_new_issue_enters_the_board_in_its_initial_state(self):
        self.fake.add_issue(30, "Nova ideia", labels=["type:epic"])
        self.event("issues", action="opened", issue={"number": 30})
        self.assertEqual(self.project.status(30), "Brainstorm")

    def test_pr_lifecycle_moves_the_task_and_closes_it_on_merge(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        self.event("push", ref="refs/heads/test/11-testes", created=True)
        self.assertEqual(self.state(11), "Coding")
        pr = {"number": 50, "head": {"ref": "test/11-testes"}, "base": {"ref": "develop"}, "merged": False,
              "draft": False}
        self.event("pull_request", action="opened", pull_request=pr)
        self.assertEqual(self.state(11), "In Review")
        self.event("pull_request", action="closed", pull_request=dict(pr, merged=True))
        self.assertEqual(self.state(11), "Done")
        self.assertEqual(self.fake.issues[11]["state"], "closed")
        self.assertIsNone(self.client.locks().current("issue-11"))
        self.assertNotIn("agent:claude-1", self.fake.label_names(11))

    def test_pr_closed_without_merge_goes_back_to_coding(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        pr = {"number": 51, "head": {"ref": "test/11-testes"}, "base": {"ref": "develop"}, "merged": False}
        self.fake.add_pull(51, "test/11-testes", "develop", state="closed")
        self.event("pull_request", action="opened", pull_request=pr)
        self.event("pull_request", action="closed", pull_request=pr)
        self.assertEqual(self.state(11), "Coding")

    def test_foreign_branches_and_events_are_ignored(self):
        self.assertEqual(self.event("push", ref="refs/heads/main"), [])
        self.assertEqual(self.event("pull_request", action="opened", pull_request={
            "number": 52, "head": {"ref": "dependabot/npm/x"}, "base": {"ref": "develop"}, "merged": False}), [])
        self.assertEqual(self.event("workflow_dispatch"), [])

    def test_backlog_and_selection_decisions_advance_the_epic(self):
        self.fake.issues[10]["labels"].append({"name": "approved:backlog"})
        self.event("issues", action="labeled", issue={"number": 10}, label={"name": "approved:backlog"})
        self.assertEqual(self.state(10), "Backlog")

    def test_merge_refused_keeps_the_claim(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        pr = {"number": 53, "head": {"ref": "test/11-testes"}, "base": {"ref": "develop"}, "merged": False}
        self.event("pull_request", action="opened", pull_request=pr)
        self.fake.issues[11]["labels"].append({"name": "on-hold"})
        self.event("pull_request", action="closed", pull_request=dict(pr, merged=True))
        self.assertEqual(self.state(11), "In Review")
        self.assertIsNotNone(self.client.locks().current("issue-11"))

    def test_retried_merge_event_releases_a_claim_left_behind(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        pr = {"number": 55, "head": {"ref": "test/11-testes"}, "base": {"ref": "develop"}, "merged": True,
              "merged_at": "2026-10-10T12:30:00Z"}
        self.event("pull_request", action="opened", pull_request=dict(pr, merged=False))
        self.move(11, "Done", actor="controller", facts={"pr_merged": True})  # the run died before releasing
        self.assertIsNotNone(self.client.locks().current("issue-11"))
        self.event("pull_request", action="closed", pull_request=pr)
        self.assertIsNone(self.client.locks().current("issue-11"))

    def test_retried_merge_event_keeps_a_claim_taken_after_the_merge(self):
        self.fake.add_issue(20, "Bug", labels=["type:bug"])
        from bb import receipts as r
        for previous, target in (("Brainstorm", "Backlog"), ("Backlog", "Ready"), ("Ready", "Selected"),
                                 ("Selected", "Coding"), ("Coding", "In Review"), ("In Review", "QA")):
            self.client.comment(20, r.render({"kind": "transition", "event_id": f"b-{target}", "issue": 20,
                                              "actor": "dona", "at": "2026-10-10T11:00:00Z", "from": previous,
                                              "to": target, "policy": "x"}))
        later = NOW + datetime.timedelta(hours=1)
        claims.claim(self.client, config(), 20, "claude-1", now=later)  # taken in QA, after the merge
        pr = {"number": 56, "head": {"ref": "fix/20-x"}, "base": {"ref": "develop"}, "merged": True,
              "merged_at": "2026-10-10T12:00:00Z"}
        controller.handle(self.client, self.project, config("flash"), "pull_request",
                          {"action": "closed", "pull_request": pr}, now=later)
        self.assertIsNotNone(self.client.locks().current("issue-20"))

    def test_bugfix_branches_are_read_by_the_controller(self):
        self.assertEqual(controller._issue_of("bugfix/20-x"), 20)

    def test_late_closed_event_of_a_reopened_pr_is_ignored(self):
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        self.fake.refs["refs/heads/test/11-testes"] = "a" * 40
        pr = {"number": 54, "head": {"ref": "test/11-testes"}, "base": {"ref": "develop"}, "merged": False}
        self.fake.add_pull(54, "test/11-testes", "develop")
        self.event("pull_request", action="opened", pull_request=pr)
        self.event("pull_request", action="closed", pull_request=pr)  # arrives after the reopen
        self.assertEqual(self.state(11), "In Review")

    def test_decision_label_advances_the_epic(self):
        self.fake.issues[10]["labels"].append({"name": "approved:backlog"})
        self.move(10, "Backlog")
        claims.claim(self.client, config(), 10, "dona", person=True, now=NOW)
        self.move(10, "Refinement")
        self.fake.issues[10]["labels"] += [{"name": "prototype:required"}, {"name": "approved:refinement"}]
        self.event("issues", action="labeled", issue={"number": 10}, label={"name": "approved:refinement"})
        self.assertEqual(self.state(10), "Prototyping")

    def test_schedule_reconciles_the_board_and_marks_stale_claims(self):
        self.fake.issues[10]["labels"].append({"name": "approved:backlog"})
        self.move(10, "Backlog")
        self.project.set_status(10, "Done")  # someone dragged the card
        claims.claim(self.client, config(), 11, "claude-1", now=NOW)
        controller.handle(self.client, self.project, config("flash"), "schedule", {},
                          now=NOW + datetime.timedelta(hours=3))
        self.assertEqual(self.project.status(10), "Backlog")
        self.assertIn("stale", self.fake.label_names(11))
        self.assertTrue(any("movimento manual" in body for body in self.fake.comment_bodies(10)))


class RecordedGraphQL:
    """Answers the GraphQL calls of ProjectGraphQL by keyword and records them, so the queries are exercised."""

    def __init__(self):
        self.calls = []
        self.fields = [{"id": "F-status", "name": "Status", "dataType": "SINGLE_SELECT",
                        "options": [{"id": "O-todo", "name": "Todo"}]}]
        self.items = []

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if "projectV2(number" in query:
            return {"user": {"projectV2": {"id": "P1"}}}
        if "fields(first" in query:
            return {"node": {"fields": {"nodes": self.fields}}}
        if "createProjectV2Field" in query:
            self.fields.append({"id": "F-" + variables["n"], "name": variables["n"], "dataType": variables["t"],
                                "options": [{"id": "O-" + o["name"], "name": o["name"]} for o in variables.get("o", [])]})
            return {"createProjectV2Field": {"projectV2Field": {"id": "F-" + variables["n"]}}}
        if "updateProjectV2Field" in query:
            for field in self.fields:
                if field["id"] == variables["f"]:
                    field["options"] = [{"id": o.get("id", "O-" + o["name"]), "name": o["name"]} for o in variables["o"]]
            return {}
        if "items(first" in query:
            return {"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": self.items}}}
        if "issue(number" in query:
            return {"repository": {"issue": {"id": "I-" + str(variables["n"])}}}
        if "addProjectV2ItemById" in query:
            return {"addProjectV2ItemById": {"item": {"id": "IT-" + variables["c"]}}}
        if "updateProjectV2ItemFieldValue" in query or "clearProjectV2ItemFieldValue" in query:
            return {}
        raise AssertionError("consulta inesperada: " + query[:80])


class GraphQLAdapter(unittest.TestCase):
    def test_fields_are_created_and_status_options_replaced_keeping_ids(self):
        graphql = RecordedGraphQL()
        project = board.ProjectGraphQL("dona", 7, "dono/repo", graphql)
        board.ensure_fields(project)
        names_created = [variables["n"] for query, variables in graphql.calls if "createProjectV2Field" in query]
        self.assertIn("Priority", names_created)
        self.assertNotIn("Status", names_created)
        update = [variables for query, variables in graphql.calls if "updateProjectV2Field" in query][0]
        self.assertEqual([o["name"] for o in update["o"]], list(states.STATES))
        self.assertEqual(update["o"][list(states.STATES).index("Todo")]["id"], "O-todo")
        for query, _ in graphql.calls:
            self.assertEqual(query.count("{"), query.count("}"), query)

    def test_set_values_by_type(self):
        graphql = RecordedGraphQL()
        project = board.ProjectGraphQL("dona", 7, "dono/repo", graphql)
        board.ensure_fields(project)
        project.set(12, "Status", "Todo")
        project.set(12, "Attempt", 2)
        project.set(12, "Executor", "claude-1")
        project.set(12, "Executor", None)
        mutations = [(q, v) for q, v in graphql.calls if "ProjectV2ItemFieldValue" in q]
        self.assertIn("singleSelectOptionId:$v", mutations[0][0])
        self.assertEqual(mutations[0][1]["v"], "O-todo")
        self.assertIn("$v:Float!", mutations[1][0])
        self.assertIn("text:$v", mutations[2][0])
        self.assertIn("clearProjectV2ItemFieldValue", mutations[3][0])
        self.assertIsNone(project.get(12, "Executor"))

    def test_items_of_other_repositories_are_ignored(self):
        graphql = RecordedGraphQL()
        graphql.items = [
            {"id": "IT-1", "content": {"number": 3, "repository": {"nameWithOwner": "dono/repo"}},
             "fieldValues": {"nodes": [{"name": "Backlog", "field": {"name": "Status"}}]}},
            {"id": "IT-2", "content": {"number": 3, "repository": {"nameWithOwner": "outro/repo"}},
             "fieldValues": {"nodes": [{"name": "Done", "field": {"name": "Status"}}]}}]
        project = board.ProjectGraphQL("dona", 7, "dono/repo", graphql)
        self.assertEqual(project.items(), {3: {"Status": "Backlog"}})


if __name__ == "__main__":
    unittest.main()
