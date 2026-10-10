"""v3 claims on atomic locks (epic #226, ADR-0023): one protocol for people and agents, at any stage, with lease,
renewal and a generation that fences replaced sessions. Runs against the in-memory GitHub."""
import datetime
import unittest

from _fake_github import FakeGitHub
from _raiz import importar_bb

importar_bb()
from bb import claims, gh, locks, receipts  # noqa: E402
from bb.errors import BbError  # noqa: E402

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
CONFIG = {"project": {"repository": "dono/repo", "owner": "dona", "mode": "flash"},
          "agents": {"names": ["claude-1", "codex-1"], "tasks_per_agent": 1, "lease_hours": 2},
          "workflow": {"model": "grouping"}, "board": {"labels": "v3"}}


class Claims(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.client = gh.GitHub("dono/repo", api=self.fake)
        self.fake.add_issue(10, "Épico", labels=["type:epic"])
        self.fake.add_issue(11, "Testes", labels=["type:test"], parent=10)
        self.fake.add_issue(12, "Login", labels=["type:task"], parent=10, blocked_by=[11])
        self.fake.add_issue(13, "Docs", labels=["type:docs"], parent=10)

    def claim(self, number, name="claude-1", now=NOW, person=False):
        return claims.claim(self.client, CONFIG, number, name, person=person, now=now)

    def test_agent_claim_locks_labels_and_records(self):
        receipt = self.claim(11)
        self.assertEqual((receipt["issue"], receipt["name"], receipt["generation"]), (11, "claude-1", 1))
        self.assertIn("agent:claude-1", self.fake.label_names(11))
        self.assertIn("refs/bigbang/locks/issue-11", self.fake.refs)
        recorded = receipts.parse(self.fake.comments[11], {"dona"})
        self.assertEqual([r["kind"] for r in recorded], ["claim"])
        self.assertEqual(recorded[0]["session"], receipt["session"])

    def test_person_claim_uses_the_login(self):
        receipt = self.claim(13, name="dona", person=True)
        self.assertIn("person:dona", self.fake.label_names(13))
        self.assertEqual(receipt["name"], "dona")

    def test_unknown_agent_and_closed_or_pr_issues_are_refused(self):
        with self.assertRaises(BbError):
            self.claim(11, name="intruso")
        self.fake.issues[13]["state"] = "closed"
        with self.assertRaises(BbError):
            self.claim(13)
        with self.assertRaises(BbError):
            self.claim(99)

    def test_blocked_task_is_refused_until_the_blocker_closes(self):
        with self.assertRaises(BbError) as error:
            self.claim(12)
        self.assertIn("#11", error.exception.message)
        self.fake.issues[11]["state"] = "closed"
        self.assertEqual(self.claim(12)["issue"], 12)

    def test_second_claim_on_the_same_issue_loses_with_the_holder_named(self):
        self.claim(11)
        with self.assertRaises(locks.LockHeld) as held:
            self.claim(11, name="codex-1")
        self.assertEqual(held.exception.record["owner"], "claude-1")
        self.assertNotIn("agent:codex-1", self.fake.label_names(11))

    def test_capacity_per_session(self):
        self.claim(11)
        with self.assertRaises(BbError) as error:
            self.claim(13)
        self.assertIn("limite", error.exception.message)

    def test_epic_stages_can_be_claimed(self):  # refinement and prototyping use the same protocol
        receipt = self.claim(10, name="dona", person=True)
        self.assertEqual(receipt["issue"], 10)

    def test_renew_extends_the_lease(self):
        receipt = self.claim(11)
        renewed = claims.renew(self.client, CONFIG, receipt, now=NOW + datetime.timedelta(hours=1))
        self.assertGreater(renewed["expires"], receipt["expires"])

    def test_unclaim_releases_lock_and_label(self):
        receipt = self.claim(11)
        claims.unclaim(self.client, CONFIG, receipt, now=NOW)
        self.assertNotIn("agent:claude-1", self.fake.label_names(11))
        self.assertNotIn("refs/bigbang/locks/issue-11", self.fake.refs)
        self.assertEqual(self.claim(11, name="codex-1")["generation"], 1)

    def test_live_lock_cannot_be_forced(self):
        self.claim(11)
        with self.assertRaises(BbError):
            claims.force(self.client, CONFIG, 11, "codex-1", "pode pegar", now=NOW)

    def test_expired_lock_is_forced_with_the_owner_order_and_fences_the_old_session(self):
        old = self.claim(11)
        later = NOW + datetime.timedelta(hours=3)
        new = claims.force(self.client, CONFIG, 11, "codex-1", "codex assume a 11", now=later)
        self.assertEqual(new["generation"], 2)
        self.assertIn("agent:codex-1", self.fake.label_names(11))
        self.assertNotIn("agent:claude-1", self.fake.label_names(11))
        self.assertTrue(any("codex assume a 11" in body for body in self.fake.comment_bodies(11)))
        with self.assertRaises(locks.LockLost):
            claims.renew(self.client, CONFIG, old, now=later)
        with self.assertRaises(BbError):
            claims.force(self.client, CONFIG, 11, "codex-1", "   ", now=later)

    def test_stale_report_lists_expired_claims(self):
        self.claim(11)
        self.assertEqual(claims.stale(self.client, now=NOW), [])
        stale = claims.stale(self.client, now=NOW + datetime.timedelta(hours=3))
        self.assertEqual([(item["issue"], item["owner"]) for item in stale], [(11, "claude-1")])


class Dispatch(unittest.TestCase):
    def test_v3_when_the_workflow_or_labels_are_v3(self):
        self.assertTrue(claims.is_v3(CONFIG))
        self.assertTrue(claims.is_v3({"workflow": {"model": "epic-branch"}, "board": {"labels": "v3"}}))
        self.assertFalse(claims.is_v3({"workflow": {"model": "epic-branch"}, "board": {"labels": "legacy"}}))
        self.assertFalse(claims.is_v3({"projeto": {"modo": "padrao"}}))


if __name__ == "__main__":
    unittest.main()
