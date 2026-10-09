"""Automatic cleanup waits for a published, synchronized framework and exact successful CI."""
import os
import sys
import unittest

from _raiz import caminho, ler
from test_integrar_publicar import ComGit
from _scripts import GH_FALSO
import test_faxina as faxina_tests

REPO = "BrunodosSantosVaz/big-bang"


class FrameworkHousekeeping(ComGit):
    def prepare(self):
        self.escrever(".bigbang/VERSION", "1.5.4\n")
        self.escrever("release-fixture", "published framework\n")
        self.commit("chore: framework release fixture")
        self.git("tag", "v1.5.4")
        self.git("push", "-q", "origin", "main", "main:develop", "--tags")
        self.git("push", "-q", "origin", "main:feature/12-done")
        self.issue(12, labels=["task"], state="closed")
        self.sha = self.git("rev-parse", "main", saida=True)
        self.release_path = f"repos/{REPO}/releases/tags/v1.5.4"
        self.estado["api"] = {self.release_path: {
            "tag_name": "v1.5.4", "draft": False, "prerelease": False,
            "assets": [{"name": "bigbang-v1.5.4.tar.gz"}, {"name": "bigbang-v1.5.4.tar.gz.sha256"}]}}
        for branch in ("main", "develop"):
            self.estado["api"][self.ci_path(branch)] = {"workflow_runs": [{
                "status": "completed", "conclusion": "success", "head_sha": self.sha,
                "head_branch": branch, "event": "push"}]}
        self.gravar_estado()

    def ci_path(self, branch):
        return (f"repos/{REPO}/actions/workflows/bb-framework-ci.yml/runs"
                f"?branch={branch}&head_sha={self.sha}&event=push&per_page=1")

    def cleanup(self, **env):
        return self.script("faxina-framework.sh", GITHUB_REPOSITORY=REPO, **env)

    def test_removes_closed_merged_branch_after_all_gates(self):
        self.prepare()
        result = self.cleanup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.estado.get("apagadas"), ["feature/12-done"])
        self.assertEqual(self.git_origin("rev-parse", "main"), self.sha)
        self.assertEqual(self.git_origin("rev-parse", "develop"), self.sha)
        self.assertEqual(self.git_origin("rev-parse", "v1.5.4"), self.sha)

    def test_simulation_never_deletes(self):
        self.prepare()
        result = self.cleanup(SIMULAR="true")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[simulado] apagar", result.stdout)
        self.assertFalse(self.estado.get("apagadas"))

    def test_waits_for_stable_release_and_both_package_assets(self):
        for field, value in (("draft", True), ("prerelease", True), ("tag_name", "v1.5.3"), ("assets", [])):
            with self.subTest(field=field):
                self.setUp()
                self.prepare()
                self.estado["api"][self.release_path][field] = value
                self.gravar_estado()
                result = self.cleanup()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("aguardando", result.stdout)
                self.assertFalse(self.estado.get("apagadas"))

    def test_waits_for_exact_latest_successful_push_ci_on_both_branches(self):
        for branch in ("main", "develop"):
            for field, value in (("status", "in_progress"), ("conclusion", "failure"),
                                 ("head_sha", "f" * 40), ("event", "pull_request")):
                with self.subTest(branch=branch, field=field):
                    self.setUp()
                    self.prepare()
                    self.estado["api"][self.ci_path(branch)]["workflow_runs"][0][field] = value
                    self.gravar_estado()
                    result = self.cleanup()
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("aguardando", result.stdout)
                    self.assertFalse(self.estado.get("apagadas"))

    def test_waits_when_develop_has_different_content(self):
        self.prepare()
        self.branch("develop", "develop", "not-published", "pending\n")
        result = self.cleanup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("aguardando", result.stdout)
        self.assertFalse(self.estado.get("apagadas"))

    def test_waits_when_main_is_newer_than_published_tag(self):
        self.prepare()
        self.escrever("not-published", "pending\n")
        self.commit("chore: unreleased change")
        self.git("push", "-q", "origin", "main", "main:develop")
        result = self.cleanup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("aguardando", result.stdout)
        self.assertFalse(self.estado.get("apagadas"))

    def test_refuses_execution_in_consumer_repository(self):
        self.prepare()
        result = self.script("faxina-framework.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.estado.get("apagadas"))

    def test_preserves_open_pr_and_exclusive_commits_reports_leftovers(self):
        self.prepare()
        self.branch("feature/13-exclusive", "main", "exclusive", "keep\n")
        self.issue(13, labels=["task"], state="closed")
        self.git("push", "-q", "origin", "main:framework/v1.5.5")
        self.estado["prs"] = {"40": {"head": "framework/v1.5.5", "base": "develop", "state": "OPEN"}}
        self.gravar_estado()
        result = self.cleanup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.estado.get("apagadas"), ["feature/12-done"])
        self.assertIn("commits fora", result.stdout)


class StrictCleanup(ComGit):
    def test_release_with_exclusive_commits_is_never_deleted(self):
        self.branch("release/0.1.0", "main", "exclusive", "keep\n")
        self.estado["api"] = {"repos/dono/repo/releases/tags/v0.1.0": {
            "tag_name": "v0.1.0", "draft": False, "prerelease": False}}
        self.gravar_estado()
        result = self.script("faxina.sh", FAXINA_EXIGIR_LIMPA="true")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.estado.get("apagadas"))
        self.assertTrue(self.git_origin("rev-parse", "release/0.1.0"))

    def test_release_requires_stable_publication_and_containment_in_tag(self):
        for draft, prerelease in ((True, False), (False, True), (False, False)):
            with self.subTest(draft=draft, prerelease=prerelease):
                self.setUp()
                self.branch("develop", "develop", "after-tag", "keep\n")
                self.git("push", "-q", "origin", "origin/develop:release/0.1.0")
                self.estado["api"] = {"repos/dono/repo/releases/tags/v0.1.0": {
                    "tag_name": "v0.1.0", "draft": draft, "prerelease": prerelease}}
                self.gravar_estado()
                result = self.script("faxina.sh", FAXINA_EXIGIR_LIMPA="true")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.estado.get("apagadas"))

    def test_published_release_fully_incorporated_can_be_deleted(self):
        self.git("push", "-q", "origin", "main:release/0.1.0")
        self.estado["api"] = {"repos/dono/repo/releases/tags/v0.1.0": {
            "tag_name": "v0.1.0", "draft": False, "prerelease": False}}
        self.gravar_estado()
        result = self.script("faxina.sh", FAXINA_EXIGIR_LIMPA="true")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.estado.get("apagadas"), ["release/0.1.0"])

    def test_epic_with_open_pr_is_preserved_even_when_closed_and_merged(self):
        self.git("push", "-q", "origin", "main:epico/8-closed")
        self.issue(8, state="closed")
        self.estado["prs"] = {"40": {"head": "epico/8-closed", "base": "develop", "state": "OPEN"}}
        self.gravar_estado()
        result = self.script("faxina.sh", FAXINA_EXIGIR_LIMPA="true")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.estado.get("apagadas"))

    def test_api_read_failure_is_explicit_and_does_not_claim_clean(self):
        for endpoint in ("issues?state=open", "issues/12", "--json number,createdAt,headRefName"):
            with self.subTest(endpoint=endpoint):
                self.setUp()
                self.git("push", "-q", "origin", "main:feature/12-done")
                self.issue(12, state="closed")
                with open(os.path.join(self.bin, "gh"), "w", encoding="utf-8") as handle:
                    handle.write(f'#!/usr/bin/env bash\nif [[ "$*" == *"{endpoint}"* ]]; then '
                                 'echo "fixture: GitHub API unavailable" >&2; exit 42; fi\n'
                                 f'exec "{sys.executable}" "{GH_FALSO}" "$@"\n')
                result = self.script("faxina.sh", FAXINA_EXIGIR_LIMPA="true")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("nada sobrando", result.stdout)
                self.assertIn("API unavailable", result.stderr)

    def test_strict_mode_reports_leftovers_as_failure(self):
        faxina_tests.Faxina.preparar(self)
        result = self.script("faxina.sh", FAXINA_EXIGIR_LIMPA="true")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ponto(s) para revisar", result.stdout)

    def test_end_sprint_does_not_hide_cleanup_failure(self):
        self.git("push", "-q", "origin", "main:unrecognized")
        result = self.script("encerrar.sh", SPRINT="true")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("branch fora do padrão", result.stdout)


class HousekeepingWorkflowSecurity(unittest.TestCase):
    def test_privileged_framework_events_only_execute_trusted_main(self):
        text = ler(".github/workflows/bb-framework-faxina.yml")
        self.assertIn("ref: main", text)
        self.assertNotIn("pull_request.head", text)
        self.assertNotIn("workflow_run.head_sha", text)
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("persist-credentials: false", text)

    def test_consumer_recovery_cannot_turn_a_publication_simulation_into_real_cleanup(self):
        path = caminho(".bigbang/esteira/nucleo/arquivos/.github/workflows/bb-faxina.yml")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("ref: main", text)
        self.assertNotIn("workflow_run:", text)
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("FAXINA_EXIGIR_LIMPA: 'true'", text)
        self.assertNotIn("workflow_run.head_sha", text)


if __name__ == "__main__":
    unittest.main()
