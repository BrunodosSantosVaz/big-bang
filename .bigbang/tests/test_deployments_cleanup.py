import unittest
from unittest import mock

from _raiz import importar_bb

importar_bb()
from bb import gh, pipeline


class TestDeploymentsCleanup(unittest.TestCase):
    def test_clean_deployments_marks_inactive_and_deletes_matching_run_deployments(self):
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET" and path.startswith("repos/dono/repo/deployments?"):
                return 200, [
                    {"id": 101, "environment": "production"},
                    {"id": 102, "environment": "production"},
                    {"id": 103, "environment": "staging"},
                ]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/101/statuses"):
                return 200, [{"id": 1, "log_url": "https://github.com/dono/repo/actions/runs/12345/job/999"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/102/statuses"):
                return 200, [{"id": 2, "log_url": "https://github.com/dono/repo/actions/runs/99999/job/888"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/103/statuses"):
                return 200, [{"id": 3, "log_url": "https://github.com/dono/repo/actions/runs/12345/job/777"}]
            if method == "POST" and "statuses" in path:
                return 201, {"id": 999, "state": "inactive"}
            if method == "DELETE":
                return 204, None
            return 200, {}

        client = gh.GitHub("dono/repo", api=fake_api)
        cleaned = pipeline.clean_deployments(client, run_id="12345", environment="production")

        self.assertEqual(cleaned, [101])
        # Verify 101 was marked inactive and deleted
        self.assertIn(("POST", "repos/dono/repo/deployments/101/statuses", {"state": "inactive"}), calls)
        self.assertIn(("DELETE", "repos/dono/repo/deployments/101", None), calls)
        # Verify 102 (other run) and 103 (other environment) were untouched
        self.assertNotIn(("DELETE", "repos/dono/repo/deployments/102", None), calls)
        self.assertNotIn(("DELETE", "repos/dono/repo/deployments/103", None), calls)

    def test_clean_deployments_tolerates_missing_run_id_or_empty_deployments(self):
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            return 200, []

        client = gh.GitHub("dono/repo", api=fake_api)
        cleaned = pipeline.clean_deployments(client, run_id="", environment="production")
        self.assertEqual(cleaned, [])
        self.assertEqual(calls, [])

    def test_clean_deployments_matches_when_environment_is_none(self):
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET" and path.startswith("repos/dono/repo/deployments?"):
                return 200, [{"id": 201, "environment": "production"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/201/statuses"):
                return 200, [{"id": 1, "log_url": "https://github.com/dono/repo/actions/runs/54321/job/111"}]
            if method == "POST" and "statuses" in path:
                return 201, {"id": 999, "state": "inactive"}
            if method == "DELETE":
                return 204, None
            return 200, {}

        client = gh.GitHub("dono/repo", api=fake_api)
        cleaned = pipeline.clean_deployments(client, run_id="54321")
        self.assertEqual(cleaned, [201])
        self.assertIn(("DELETE", "repos/dono/repo/deployments/201", None), calls)


    def test_clean_deployments_exact_run_id_no_prefix_collision(self):
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET" and path.startswith("repos/dono/repo/deployments?"):
                return 200, [
                    {"id": 301, "environment": "production"},
                    {"id": 302, "environment": "production"},
                    {"id": 303, "environment": "production"},
                ]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/301/statuses"):
                # run 1234 prefix matches 123 but is NOT exact 123
                return 200, [{"id": 1, "log_url": "https://github.com/dono/repo/actions/runs/1234/job/10"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/302/statuses"):
                # run 9123 suffix matches 123 but is NOT exact 123
                return 200, [{"id": 2, "log_url": "https://github.com/dono/repo/actions/runs/9123/job/20"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/303/statuses"):
                # exact run 123
                return 200, [{"id": 3, "log_url": "https://github.com/dono/repo/actions/runs/123/job/30"}]
            if method == "POST" and "statuses" in path:
                return 201, {"id": 999, "state": "inactive"}
            if method == "DELETE":
                return 204, None
            return 200, {}

        client = gh.GitHub("dono/repo", api=fake_api)
        cleaned = pipeline.clean_deployments(client, run_id="123", environment="production")

        self.assertEqual(cleaned, [303])
        self.assertNotIn(("DELETE", "repos/dono/repo/deployments/301", None), calls)
        self.assertNotIn(("DELETE", "repos/dono/repo/deployments/302", None), calls)
        self.assertIn(("DELETE", "repos/dono/repo/deployments/303", None), calls)

    def test_clean_deployments_cleans_deployments_with_waiting_status(self):
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET" and path.startswith("repos/dono/repo/deployments?"):
                return 200, [
                    {"id": 401, "environment": "production"},
                ]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/401/statuses"):
                return 200, [{"id": 1, "state": "waiting", "log_url": "https://github.com/dono/repo/actions/runs/888/job/1"}]
            if method == "POST" and "statuses" in path:
                return 201, {"id": 999, "state": "inactive"}
            if method == "DELETE":
                return 204, None
            return 200, {}

        client = gh.GitHub("dono/repo", api=fake_api)
        cleaned = pipeline.clean_deployments(client, run_id="888", environment="production")

        self.assertEqual(cleaned, [401])
        self.assertIn(("POST", "repos/dono/repo/deployments/401/statuses", {"state": "inactive"}), calls)
        self.assertIn(("DELETE", "repos/dono/repo/deployments/401", None), calls)

    def test_clean_deployments_stale_cleans_other_runs_and_preserves_current_run(self):
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET" and path.startswith("repos/dono/repo/deployments?"):
                return 200, [
                    {"id": 501, "environment": "production"},
                    {"id": 502, "environment": "production"},
                    {"id": 503, "environment": "staging"},
                ]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/501/statuses"):
                # stale run 777
                return 200, [{"id": 1, "log_url": "https://github.com/dono/repo/actions/runs/777/job/1"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/502/statuses"):
                # current run 888
                return 200, [{"id": 2, "log_url": "https://github.com/dono/repo/actions/runs/888/job/2"}]
            if method == "GET" and path.startswith("repos/dono/repo/deployments/503/statuses"):
                # stale run 666, but in staging
                return 200, [{"id": 3, "log_url": "https://github.com/dono/repo/actions/runs/666/job/3"}]
            if method == "POST" and "statuses" in path:
                return 201, {"id": 999, "state": "inactive"}
            if method == "DELETE":
                return 204, None
            return 200, {}

        client = gh.GitHub("dono/repo", api=fake_api)
        cleaned = pipeline.clean_deployments(client, stale=True, exclude_run_id="888", environment="production")

        self.assertEqual(cleaned, [501])
        self.assertIn(("DELETE", "repos/dono/repo/deployments/501", None), calls)
        self.assertNotIn(("DELETE", "repos/dono/repo/deployments/502", None), calls)
        self.assertNotIn(("DELETE", "repos/dono/repo/deployments/503", None), calls)


class TestPublishWorkflowCleanDeploymentsStep(unittest.TestCase):
    def test_publish_workflow_contains_clean_deployments_always_step(self):
        import os
        from _raiz import RAIZ
        template_path = os.path.join(RAIZ, ".bigbang", "pipeline", "core", "files", ".github", "workflows", "bb-publish.yml.tmpl")
        with open(template_path, encoding="utf-8") as f:
            template_text = f.read()
        self.assertIn("name: Clean deployments", template_text)
        self.assertIn("if: always()", template_text)
        self.assertIn("name: Clean stale deployments", template_text)
        self.assertIn("python .bigbang/bin/bb.py pipeline clean-deployments --environment production --stale", template_text)
