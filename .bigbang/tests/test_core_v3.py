"""v3 core (epic #225, ADR-0023/0025): states, policy, receipts and atomic locks. Pure rules, tested before the
pipeline uses them. The lock tests run against an in-memory GitHub with the real ref semantics: creating an existing
ref fails, and a non-fast-forward update fails, both with HTTP 422."""
import datetime
import hashlib
import json
import unittest

from _fake_github import FakeGitHub
from _raiz import importar_bb

importar_bb()
from bb import locks, policy, receipts, states  # noqa: E402
from bb.errors import BbError  # noqa: E402

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def facts(**values):
    base = {"labels": set(), "claimed": False, "branch": False, "pr_open": False, "pr_merged": False,
            "subissues_total": 0, "subissues_open": 0, "blocked_by_open": 0, "candidate": False,
            "qa": "pending", "qa_decision": "pending", "prototype": "pending", "flag": "pending", "flag_on": False,
            "delivery": {"deploy"}, "merged_permanent": False, "delivered": False, "accepted": False,
            "selected": False, "ready_problems": [], "triaged": False}
    base.update(values)
    return base


class States(unittest.TestCase):
    def test_fifteen_states_and_types(self):
        self.assertEqual(len(states.STATES), 15)
        for state in states.STATES:
            self.assertTrue(states.ALLOWED[state])
        self.assertEqual(states.ALLOWED["Todo"], {"task"})
        self.assertIn("bug", states.ALLOWED["Coding"])
        self.assertEqual(states.ALLOWED["Rejected"], {"epic", "task", "bug"})

    def test_kind_from_labels_in_both_dialects(self):
        self.assertEqual(states.kind({"type:epic"}), "epic")
        self.assertEqual(states.kind({"epic"}), "epic")
        self.assertEqual(states.kind({"teste-aceite"}), "task")
        self.assertEqual(states.kind({"type:docs"}), "task")
        self.assertEqual(states.kind({"bug", "severidade:alta"}), "bug")
        self.assertIsNone(states.kind({"enhancement"}))
        self.assertIsNone(states.kind({"type:epic", "type:task"}))  # contradictory: refused

    def test_unknown_or_wrong_type_state(self):
        self.assertIn("estado desconhecido", states.problems("epic", "Backlog", "Somewhere", facts())[0])
        self.assertIn("não existe para tarefa", states.problems("task", "Todo", "Refinement", facts())[0])
        self.assertIn("transição não permitida", states.problems("epic", "Brainstorm", "Done", facts())[0])

    def test_epic_planning_route(self):
        self.assertTrue(states.problems("epic", "Brainstorm", "Backlog", facts()))
        self.assertEqual(states.problems("epic", "Brainstorm", "Backlog", facts(accepted=True)), [])
        self.assertTrue(states.problems("epic", "Backlog", "Refinement", facts()))
        self.assertEqual(states.problems("epic", "Backlog", "Refinement", facts(claimed=True)), [])
        approved = {"approved:refinement"}
        self.assertTrue(states.problems("epic", "Refinement", "Ready", facts(labels=approved, prototype="pending")))
        self.assertTrue(states.problems("epic", "Refinement", "Ready", facts(labels=approved, prototype="waived")))
        self.assertEqual(states.problems("epic", "Refinement", "Ready",
                                         facts(labels=approved, prototype="waived", flag="required")), [])
        self.assertEqual(states.problems("epic", "Refinement", "Prototyping",
                                         facts(labels=approved, prototype="required")), [])
        self.assertTrue(states.problems("epic", "Refinement", "Ready",
                                        facts(labels=approved, prototype="waived", flag="waived",
                                              ready_problems=["faltam critérios"])))
        self.assertTrue(states.problems("epic", "Prototyping", "Ready", facts(flag="waived")))
        self.assertEqual(states.problems("epic", "Prototyping", "Ready",
                                         facts(labels={"approved:prototype"}, flag="waived")), [])

    def test_legacy_decision_labels_count(self):
        self.assertEqual(states.problems("epic", "Refinement", "Ready",
                                         facts(labels={"refinamento-aprovado"}, prototype="waived", flag="waived")),
                         [])

    def test_selection_and_plan(self):
        self.assertTrue(states.problems("epic", "Ready", "Selected", facts(selected=True, blocked_by_open=1)))
        self.assertEqual(states.problems("epic", "Ready", "Selected", facts(selected=True)), [])
        self.assertTrue(states.problems("epic", "Selected", "In Progress", facts()))
        self.assertEqual(states.problems("epic", "Selected", "In Progress", facts(subissues_total=3,
                                                                                   subissues_open=3)), [])

    def test_delivery_routes(self):
        done_tasks = dict(subissues_total=3, subissues_open=0)
        self.assertTrue(states.problems("epic", "In Progress", "QA", facts(subissues_total=3, subissues_open=1,
                                                                          qa="human", candidate=True)))
        self.assertEqual(states.problems("epic", "In Progress", "QA", facts(qa="human", candidate=True,
                                                                           **done_tasks)), [])
        self.assertTrue(states.problems("epic", "In Progress", "QA", facts(qa="not-applicable", candidate=True,
                                                                          **done_tasks)))
        self.assertEqual(states.problems("epic", "In Progress", "Releasing",
                                         facts(qa="not-applicable", delivery={"docs"}, **done_tasks)), [])
        self.assertTrue(states.problems("epic", "In Progress", "Releasing",
                                        facts(qa="human", delivery={"docs"}, **done_tasks)))
        self.assertEqual(states.problems("epic", "In Progress", "Done",
                                         facts(qa="not-applicable", delivery={"repository"}, merged_permanent=True,
                                               **done_tasks)), [])
        self.assertTrue(states.problems("epic", "In Progress", "Done",
                                        facts(qa="not-applicable", delivery={"repository"}, **done_tasks)))
        self.assertTrue(states.problems("epic", "In Progress", "Done",
                                        facts(qa="not-applicable", delivery={"deploy"}, merged_permanent=True,
                                              **done_tasks)))

    def test_qa_and_release(self):
        self.assertTrue(states.problems("epic", "QA", "Releasing", facts()))
        self.assertEqual(states.problems("epic", "QA", "Releasing", facts(labels={"qa:approved"})), [])
        self.assertEqual(states.problems("epic", "QA", "Releasing", facts(qa_decision="automatic")), [])
        self.assertTrue(states.problems("epic", "Releasing", "Done", facts(delivered=True, flag="required")))
        self.assertEqual(states.problems("epic", "Releasing", "Done",
                                         facts(delivered=True, flag="required", flag_on=True)), [])
        self.assertEqual(states.problems("epic", "Releasing", "Done", facts(delivered=True, flag="waived")), [])

    def test_task_route(self):
        self.assertTrue(states.problems("task", "Todo", "Coding", facts(claimed=True)))
        self.assertTrue(states.problems("task", "Todo", "Coding", facts(claimed=True, branch=True,
                                                                        blocked_by_open=1)))
        self.assertEqual(states.problems("task", "Todo", "Coding", facts(claimed=True, branch=True)), [])
        self.assertTrue(states.problems("task", "Coding", "In Review", facts()))
        self.assertEqual(states.problems("task", "Coding", "In Review", facts(pr_open=True)), [])
        self.assertTrue(states.problems("task", "In Review", "Done", facts(pr_open=True)))
        self.assertEqual(states.problems("task", "In Review", "Done", facts(pr_merged=True)), [])
        self.assertEqual(states.problems("task", "Coding", "Todo", facts(claimed=False)), [])

    def test_bug_route(self):
        self.assertTrue(states.problems("bug", "Backlog", "Ready", facts()))
        self.assertEqual(states.problems("bug", "Backlog", "Ready", facts(triaged=True)), [])
        self.assertEqual(states.problems("bug", "Selected", "Coding", facts(claimed=True, branch=True)), [])
        self.assertEqual(states.problems("bug", "In Review", "QA", facts(pr_merged=True, qa="human")), [])
        self.assertEqual(states.problems("bug", "In Review", "Done",
                                         facts(pr_merged=True, qa="not-applicable", delivery={"repository"})), [])

    def test_bug_without_qa_but_with_publication_goes_to_releasing(self):
        self.assertEqual(states.problems("bug", "In Review", "Releasing",
                                         facts(pr_merged=True, qa="not-applicable", delivery={"deploy"})), [])
        self.assertTrue(states.problems("bug", "In Review", "Releasing",
                                        facts(pr_merged=True, qa="human", delivery={"deploy"})))

    def test_leaving_rejected_respects_impediments(self):
        self.assertTrue(states.problems("task", "Rejected", "Todo", facts(labels={"blocked"}), return_to="Todo"))

    def test_impediments_block_forward_but_not_reject_or_cancel(self):
        blocked = facts(labels={"blocked"}, pr_open=True)
        self.assertIn("impedimento", states.problems("task", "Coding", "In Review", blocked)[0])
        self.assertEqual(states.problems("task", "In Review", "Rejected", facts(labels={"blocked"}),
                                         reason="code", return_to="Todo"), [])
        self.assertEqual(states.problems("task", "Coding", "Cancelled", blocked, reason="duplicada"), [])

    def test_rejection_needs_reason_and_allowed_return(self):
        self.assertIn("motivo", states.problems("epic", "QA", "Rejected", facts(), return_to="In Progress")[0])
        self.assertTrue(states.problems("epic", "QA", "Rejected", facts(), reason="nonsense",
                                        return_to="In Progress"))
        self.assertEqual(states.problems("epic", "QA", "Rejected", facts(), reason="qa", return_to="In Progress"), [])
        self.assertIn("retorno", states.problems("epic", "QA", "Rejected", facts(), reason="qa",
                                                 return_to="Backlog")[0])
        self.assertEqual(states.problems("epic", "Prototyping", "Rejected", facts(), reason="prototype",
                                         return_to="Refinement"), [])
        self.assertTrue(states.problems("epic", "Backlog", "Rejected", facts(), reason="requirements",
                                        return_to="Backlog"))  # nothing was validated yet
        self.assertEqual(states.problems("task", "In Review", "Rejected", facts(), reason="tests",
                                         return_to="Todo"), [])
        self.assertTrue(states.problems("task", "In Review", "Rejected", facts(), reason="tests",
                                        return_to="Coding"))  # coding again needs a valid claim
        self.assertEqual(states.problems("task", "In Review", "Rejected", facts(claimed=True), reason="tests",
                                         return_to="Coding"), [])

    def test_leaving_rejected_only_to_the_recorded_return(self):
        self.assertEqual(states.problems("epic", "Rejected", "In Progress", facts(), return_to="In Progress"), [])
        self.assertTrue(states.problems("epic", "Rejected", "QA", facts(), return_to="In Progress"))
        self.assertTrue(states.problems("epic", "Rejected", "In Progress", facts()))

    def test_terminal_states(self):
        self.assertTrue(states.problems("epic", "Done", "Backlog", facts()))
        self.assertTrue(states.problems("task", "Cancelled", "Todo", facts()))
        self.assertIn("motivo", states.problems("epic", "Backlog", "Cancelled", facts())[0])

    def test_allowed_targets(self):
        self.assertEqual(states.targets("task", "Todo"), {"Coding", "Cancelled"})
        self.assertIn("Rejected", states.targets("epic", "QA"))
        self.assertEqual(states.targets("epic", "Done"), set())


class Policy(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(policy.MODES, ("normal", "flash", "autonomous"))
        self.assertEqual(policy.mode({"project": {"mode": "flash"}}), "flash")
        self.assertEqual(policy.mode({"projeto": {"modo": "padrao"}}), "normal")

    def test_normal_owner_decides_every_gate(self):
        for gate in policy.GATES:
            with self.subTest(gate=gate):
                self.assertEqual(policy.approver("normal", gate, "low"), "owner")

    def test_flash_delegates_common_work_but_not_critical_or_selection(self):
        self.assertEqual(policy.approver("flash", "pr", "low"), "agent")
        self.assertEqual(policy.approver("flash", "refinement", "medium"), "agent")
        self.assertEqual(policy.approver("flash", "refinement", "critical"), "owner")
        self.assertEqual(policy.approver("flash", "selection", "low"), "owner")
        self.assertEqual(policy.approver("flash", "publish", "low"), "agent")
        self.assertEqual(policy.approver("flash", "publish", "high"), "owner")

    def test_autonomous_needs_a_contract_and_never_widens_it(self):
        self.assertEqual(policy.approver("autonomous", "publish", "low"), "blocked")  # no contract
        contract = {"risk": ["low", "medium"], "gates": list(policy.GATES), "flags": "agent"}
        self.assertEqual(policy.approver("autonomous", "publish", "low", contract), "agent")
        self.assertEqual(policy.approver("autonomous", "publish", "critical", contract), "blocked")
        self.assertEqual(policy.approver("autonomous", "flag", "low", dict(contract, flags="owner")), "owner")
        self.assertEqual(policy.approver("autonomous", "qa", "low", dict(contract, gates=["pr"])), "blocked")

    def test_risk_floor_cannot_be_lowered(self):
        zones = ["src/**/auth/**"]
        self.assertEqual(policy.risk_floor(["docs/guia.md"], zones), "low")
        self.assertEqual(policy.risk_floor(["src/app.py"], zones), "medium")
        self.assertEqual(policy.risk_floor(["package.json"], zones), "high")
        self.assertEqual(policy.risk_floor(["src/api/auth/login.py"], zones), "critical")
        self.assertEqual(policy.risk_floor([".github/workflows/x.yml"], zones), "critical")
        self.assertEqual(policy.risk_floor(["migrations/0001.sql"], zones), "critical")
        self.assertEqual(policy.risk_floor(["AGENTS.md"], zones), "high")
        self.assertEqual(policy.risk_floor([".bigbang/bb/cli.py"], zones), "critical")
        self.assertEqual(policy.planning_risk({"area:auth"}), "critical")
        self.assertEqual(policy.planning_risk(set()), "medium")
        self.assertEqual(policy.delivery_risk(set()), "high")  # no paths, no area: fail closed for QA/publish
        self.assertEqual(policy.effective_risk({"risk:low"}, "high"), "high")
        self.assertEqual(policy.effective_risk({"risk:critical"}, "low"), "critical")

    def test_contract_validation(self):
        good = {"version": 1, "targets": ["staging", "production"], "risk": ["low"], "gates": ["pr", "publish"],
                "flags": "owner", "wip": 2, "attempts": 3, "max_cost_usd": 10, "publish_window": "08:00-18:00",
                "expires": "2026-12-31"}
        self.assertEqual(policy.contract_problems(good, today=NOW.date()), [])
        self.assertTrue(policy.contract_problems(dict(good, risk=["critical", "weird"]), today=NOW.date()))
        self.assertTrue(policy.contract_problems(dict(good, expires="2026-01-01"), today=NOW.date()))
        self.assertTrue(policy.contract_problems(dict(good, unknown=1), today=NOW.date()))
        self.assertTrue(policy.contract_problems(dict(good, publish_window="25:00-26:00"), today=NOW.date()))
        self.assertTrue(policy.in_window("08:00-18:00", NOW))
        self.assertFalse(policy.in_window("13:00-18:00", NOW))

    def test_snapshot_is_canonical(self):
        one = policy.snapshot({"mode": "flash", "limits": {"attempts": 3}})
        two = policy.snapshot({"limits": {"attempts": 3}, "mode": "flash"})
        self.assertEqual(one, two)
        self.assertEqual(len(one[1]), 12)
        self.assertNotEqual(one[1], policy.snapshot({"mode": "normal", "limits": {"attempts": 3}})[1])

    def test_limits(self):
        limits = policy.limits({})
        self.assertEqual(limits["attempts"], 3)
        self.assertEqual(limits["expedite"], 1)
        self.assertEqual(limits["epics_in_progress"], 2)
        self.assertEqual(policy.limits({"agents": {"tasks_per_agent": 2}})["tasks_per_session"], 2)

    def test_promotion_reuses_valid_evidence(self):
        self.assertFalse(policy.suite_on_promotion("normal", evidence_valid=True))
        self.assertTrue(policy.suite_on_promotion("normal", evidence_valid=False))
        self.assertFalse(policy.suite_on_promotion("autonomous", evidence_valid=False))  # same artifact


class Receipts(unittest.TestCase):
    def receipt(self, **values):
        base = {"kind": "transition", "event_id": "e-1", "issue": 12, "from": "Coding", "to": "In Review",
                "actor": "claude-1", "session": "s-1", "sha": "a" * 40, "policy": "abc123def456",
                "at": "2026-10-10T12:00:00Z"}
        base.update(values)
        return base

    def test_round_trip_and_comment_safety(self):
        receipt = self.receipt(evidence=["bb test --full -- ok"])
        body = receipts.render(receipt)
        self.assertNotIn("--full", body.split("\n", 1)[0].split("<!--", 1)[1].rsplit("-->", 1)[0])
        comments = [{"user": {"login": "dona"}, "body": body, "id": 1}]
        self.assertEqual(receipts.parse(comments, {"dona"}), [receipt])

    def test_only_trusted_authors(self):
        body = receipts.render(self.receipt())
        self.assertEqual(receipts.parse([{"user": {"login": "intruso"}, "body": body, "id": 1}], {"dona"}), [])

    def test_malformed_and_incomplete_are_ignored(self):
        bad = [{"user": {"login": "dona"}, "body": "<!-- bb:receipt {not json} -->", "id": 1},
               {"user": {"login": "dona"}, "body": receipts.render(self.receipt()).replace('"policy"', '"policyx"'),
                "id": 2}]
        self.assertEqual(receipts.parse(bad, {"dona"}), [])

    def test_transition_without_a_known_sha(self):
        receipt = self.receipt()
        del receipt["sha"]
        self.assertEqual(receipts.problems(receipt), [])

    def test_required_fields_per_kind(self):
        self.assertTrue(receipts.problems({"kind": "test"}))
        self.assertTrue(receipts.problems(self.receipt(kind="nope")))
        self.assertEqual(receipts.problems(self.receipt()), [])
        rejection = self.receipt(kind="rejection", to="Rejected", reason="qa", return_to="In Progress",
                                 evidence=["candidata rc.2 reprovada"])
        self.assertEqual(receipts.problems(rejection), [])
        self.assertTrue(receipts.problems(dict(rejection, reason="")))

    def test_idempotency(self):
        stored = [self.receipt(event_id="e-1"), self.receipt(event_id="e-2")]
        self.assertEqual(receipts.find(stored, "e-2")["event_id"], "e-2")
        self.assertIsNone(receipts.find(stored, "e-3"))

    def test_test_receipt_reuse(self):
        test = {"kind": "test", "event_id": "t-1", "sha": "a" * 40, "tree": "b" * 40, "base": "c" * 40,
                "policy": "abc123def456", "lockfiles": "d" * 64, "toolchain": "python-3.12", "selector": "1",
                "commands": ["bb test --full"], "result": "success", "runner": "ubuntu-24.04",
                "at": "2026-10-10T12:00:00Z", "actor": "ci", "issue": 12}
        self.assertEqual(receipts.problems(test), [])
        same = dict(tree="b" * 40, policy="abc123def456", lockfiles="d" * 64)
        self.assertEqual(receipts.reuse_problems(test, **same), [])
        self.assertTrue(receipts.reuse_problems(test, **dict(same, tree="e" * 40)))
        self.assertTrue(receipts.reuse_problems(test, **dict(same, lockfiles="f" * 64)))
        self.assertTrue(receipts.reuse_problems(dict(test, result="failure"), **same))


class Locks(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub()
        self.locks = locks.Locks("dono/repo", api=self.github)

    def test_resource_names(self):
        for bad in ("", "../x", "Issue 1", "a" * 101, "refs/heads/main"):
            with self.subTest(name=bad), self.assertRaises(BbError):
                self.locks.acquire(bad, "claude-1", "s1", hours=1, now=NOW)

    def test_one_winner_and_the_loser_learns_the_holder(self):
        first = self.locks.acquire("issue-12", "claude-1", "s1", hours=2, now=NOW)
        self.assertEqual((first["owner"], first["generation"]), ("claude-1", 1))
        with self.assertRaises(locks.LockHeld) as held:
            self.locks.acquire("issue-12", "codex-1", "s2", hours=2, now=NOW)
        self.assertEqual(held.exception.record["owner"], "claude-1")
        self.assertEqual(self.locks.current("issue-12")["session"], "s1")

    def test_expired_lock_is_taken_over_only_on_request(self):
        self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        later = NOW + datetime.timedelta(hours=2)
        with self.assertRaises(locks.LockHeld):  # an expired claim is not silently taken
            self.locks.acquire("issue-12", "codex-1", "s2", hours=1, now=later)
        record = self.locks.acquire("issue-12", "codex-1", "s2", hours=1, now=later, take_expired=True)
        self.assertEqual((record["owner"], record["generation"]), ("codex-1", 2))

    def test_take_over_needs_the_same_mark_for_an_expired_lock(self):
        self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        head = self.github.refs["refs/bigbang/locks/issue-12"]
        later = NOW + datetime.timedelta(hours=2)
        with self.assertRaises(locks.LockHeld):
            self.locks.take_over("issue-12", head, "codex-1", "s2", hours=1, now=later)
        self.assertEqual(self.locks.take_over("issue-12", head, "codex-1", "s2", hours=1, now=later,
                                              take_expired=True)["generation"], 2)

    def test_listing_only_the_requested_locks(self):
        self.locks.acquire("issue-1", "claude-1", "s1", hours=1, now=NOW)
        self.locks.acquire("issue-2", "claude-1", "s2", hours=1, now=NOW)
        self.github.calls.clear()
        self.assertEqual(sorted(self.locks.all(resources=["issue-2"])), ["issue-2"])
        commit_reads = [c for c in self.github.calls if "/git/commits/" in c[1]]
        self.assertEqual(len(commit_reads), 1)

    def test_take_over_refuses_a_live_lock(self):
        self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        head = self.github.refs["refs/bigbang/locks/issue-12"]
        with self.assertRaises(locks.LockHeld):
            self.locks.take_over("issue-12", head, "codex-1", "s2", hours=1, now=NOW)

    def test_release_keeps_a_tombstone_so_a_late_release_cannot_delete_another_lock(self):
        first = self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        self.locks.release("issue-12", "s1", first["generation"], now=NOW)
        self.assertIn("refs/bigbang/locks/issue-12", self.github.refs)  # tombstone, never deleted
        second = self.locks.acquire("issue-12", "codex-1", "s2", hours=1, now=NOW)
        self.assertEqual(second["generation"], 2)  # generations only grow
        with self.assertRaises(locks.LockLost):  # the old session cannot touch the new lock
            self.locks.release("issue-12", "s1", first["generation"], now=NOW)
        self.assertEqual(self.locks.current("issue-12")["session"], "s2")

    def test_expired_lock_cannot_be_renewed(self):
        record = self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        with self.assertRaises(locks.LockLost):
            self.locks.renew("issue-12", "s1", record["generation"], hours=1, now=NOW + datetime.timedelta(hours=2))

    def test_unexpected_422_is_an_error_not_a_loop(self):
        def api(method, path, payload=None):
            if method == "POST" and path.endswith("git/refs"):
                return 422, {"message": "Object does not exist"}
            if method == "GET" and "/git/ref/" in path:
                return 404, {}
            return self.github(method, path, payload)
        with self.assertRaises(BbError):
            locks.Locks("dono/repo", api=api).acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)

    def test_lock_commits_use_the_empty_tree_constant(self):
        self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        self.assertNotIn(("POST", "repos/dono/repo/git/trees"), self.github.calls)

    def test_concurrent_takeover_has_one_winner(self):
        self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        later = NOW + datetime.timedelta(hours=2)
        stale_head = self.github.refs["refs/bigbang/locks/issue-12"]
        self.locks.acquire("issue-12", "codex-1", "s2", hours=1, now=later, take_expired=True)
        # A second taker that read the same expired head must fail on the non-fast-forward update.
        with self.assertRaises(locks.LockHeld):
            self.locks.take_over("issue-12", stale_head, "codex-2", "s3", hours=1, now=later, take_expired=True)

    def test_renew_only_by_the_holder_and_generation(self):
        record = self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        renewed = self.locks.renew("issue-12", "s1", record["generation"], hours=1,
                                   now=NOW + datetime.timedelta(minutes=50))
        self.assertGreater(renewed["expires"], record["expires"])
        with self.assertRaises(locks.LockLost):
            self.locks.renew("issue-12", "s2", record["generation"], hours=1, now=NOW)
        with self.assertRaises(locks.LockLost):
            self.locks.renew("issue-12", "s1", record["generation"] + 1, hours=1, now=NOW)

    def test_expired_session_cannot_renew_after_takeover(self):
        record = self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        self.locks.acquire("issue-12", "codex-1", "s2", hours=1, now=NOW + datetime.timedelta(hours=2),
                           take_expired=True)
        with self.assertRaises(locks.LockLost):
            self.locks.renew("issue-12", "s1", record["generation"], hours=1, now=NOW + datetime.timedelta(hours=2))

    def test_release_only_by_the_holder(self):
        record = self.locks.acquire("issue-12", "claude-1", "s1", hours=1, now=NOW)
        with self.assertRaises(locks.LockLost):
            self.locks.release("issue-12", "s2", record["generation"], now=NOW)
        self.locks.release("issue-12", "s1", record["generation"], now=NOW)
        self.assertIsNone(self.locks.current("issue-12"))
        self.assertEqual(self.locks.acquire("issue-12", "codex-1", "s2", hours=1, now=NOW)["generation"], 2)

    def test_listing_and_expiry(self):
        self.locks.acquire("issue-1", "claude-1", "s1", hours=1, now=NOW)
        self.locks.acquire("version-3.0.0", "controller", "s9", hours=4, now=NOW)
        listed = self.locks.all()
        self.assertEqual(sorted(listed), ["issue-1", "version-3.0.0"])
        later = NOW + datetime.timedelta(hours=2)
        self.assertEqual(sorted(name for name, record in listed.items() if locks.expired(record, later)),
                         ["issue-1"])

    def test_foreign_ref_content_is_never_trusted_as_a_lock(self):
        self.github.commits["f" * 40] = {"message": "not a lock", "parents": []}
        self.github.refs["refs/bigbang/locks/issue-7"] = "f" * 40
        self.assertIsNone(locks.decode("not a lock"))
        with self.assertRaises(BbError):
            self.locks.acquire("issue-7", "claude-1", "s1", hours=1, now=NOW)


class GhAdapter(unittest.TestCase):
    """The real adapter reads the HTTP status from `gh api -i`, so 422 (ref exists / not fast-forward) is data."""

    def run_with(self, stdout):
        import os
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            fake = os.path.join(folder, "gh.py")
            with open(fake, "w", encoding="utf-8") as handle:
                handle.write("import sys\nsys.stdin.read()\nsys.stdout.write(" + repr(stdout) + ")\n")
            previous = os.environ.get("BB_GH")
            os.environ["BB_GH"] = f'"{sys.executable}" "{fake}"'
            try:
                return locks.gh_api("POST", "repos/dono/repo/git/refs", {"ref": "x", "sha": "y"})
            finally:
                if previous is None:
                    os.environ.pop("BB_GH")
                else:
                    os.environ["BB_GH"] = previous

    def test_status_and_body(self):
        self.assertEqual(self.run_with('HTTP/2.0 422 Unprocessable Entity\r\nX: y\r\n\r\n{"message": "Reference '
                                       'already exists"}'), (422, {"message": "Reference already exists"}))
        self.assertEqual(self.run_with("HTTP/2.0 204 No Content\n\n"), (204, None))

    def test_no_http_status_is_an_error(self):
        with self.assertRaises(BbError):
            self.run_with("gh: not logged in")


if __name__ == "__main__":
    unittest.main()
