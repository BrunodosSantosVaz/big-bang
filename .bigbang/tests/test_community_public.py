"""Community defaults must be idempotent and must not expose existing private cards."""
import json
import unittest
from unittest.mock import patch

from _raiz import importar_bb

importar_bb()
from bb import community_public
from bb.errors import BbError


class Discussions(unittest.TestCase):
    def test_first_post_is_created_in_real_repository_category(self):
        state = {"id": "R_game", "hasDiscussionsEnabled": True,
                 "discussionCategories": {"nodes": [{"id": "C_general", "slug": "general"}]},
                 "discussions": {"nodes": [], "pageInfo": {"hasNextPage": False}}}
        with patch.object(community_public, "discussion_state", return_value=state), \
                patch.object(community_public.github, "run", return_value=json.dumps(
                    {"data": {"createDiscussion": {"discussion": {"url": "https://github.com/owner/game/discussions/1"}}}})) as run:
            self.assertIn("discussions/1", community_public.welcome("owner/game", "Jogo"))
            self.assertIn("category=C_general", run.call_args.args)
            self.assertIn("repo=R_game", run.call_args.args)

    def test_existing_welcome_is_not_reposted(self):
        state = {"id": "R_game", "hasDiscussionsEnabled": True,
                 "discussions": {"nodes": [{"body": community_public.WELCOME_MARKER,
                                               "url": "https://github.com/owner/game/discussions/1"}]}}
        with patch.object(community_public, "discussion_state", return_value=state), \
                patch.object(community_public.github, "run", side_effect=AssertionError("mutation")):
            self.assertIn("discussions/1", community_public.welcome("owner/game", "Jogo"))

    def test_disabled_discussions_is_diagnostic_not_silent_success(self):
        with patch.object(community_public, "discussion_state", return_value={"hasDiscussionsEnabled": False}):
            with self.assertRaisesRegex(BbError, "Discussions"):
                community_public.welcome("owner/game", "Jogo")


class Projects(unittest.TestCase):
    def test_new_empty_public_project_can_be_published(self):
        board = {"id": "P_empty", "public": False, "title": "Jogo", "shortDescription": "", "readme": "",
                 "items": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                 "fields": {"nodes": []}}
        with patch.object(community_public, "project_state", return_value=board), \
                patch.object(community_public.github, "run", return_value='{}') as run:
            community_public.ensure_public_project("owner/game", "owner", 1, publish=True)
            self.assertIn("updateProjectV2", run.call_args.args[2])

    def test_draft_or_private_item_is_never_published(self):
        for content in ({"__typename": "DraftIssue", "title": "Privado"},
                        {"__typename": "Issue", "repository": {"isPrivate": True, "nameWithOwner": "owner/private"}}):
            board = {"id": "P_private", "public": False, "title": "Jogo", "shortDescription": "", "readme": "",
                     "items": {"nodes": [{"content": content}], "pageInfo": {"hasNextPage": False}},
                     "fields": {"nodes": []}}
            with patch.object(community_public, "project_state", return_value=board), \
                    patch.object(community_public.github, "run", side_effect=AssertionError("mutation")):
                with self.assertRaisesRegex(BbError, "privado|rascunho"):
                    community_public.ensure_public_project("owner/game", "owner", 1, publish=True)

    def test_existing_text_requires_reviewed_audit_before_becoming_public(self):
        board = {"id": "P_nonempty", "public": False, "title": "Jogo", "shortDescription": "Nota interna",
                 "readme": "", "items": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                 "fields": {"nodes": []}}
        with patch.object(community_public, "project_state", return_value=board):
            with self.assertRaisesRegex(BbError, "auditoria"):
                community_public.ensure_public_project("owner/game", "owner", 1, publish=True)


if __name__ == "__main__":
    unittest.main()
