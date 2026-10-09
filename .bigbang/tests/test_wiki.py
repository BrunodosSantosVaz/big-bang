"""Public Wiki routing, coverage and concurrent publication; private projects stay local."""
import hashlib
import json
import subprocess
import tempfile
import unittest
import contextlib
import io
import os
from pathlib import Path
from unittest.mock import patch

from _raiz import importar_bb

importar_bb()
from bb import documentation
from bb.errors import BbError


def git(folder, *args):
    return subprocess.check_output(["git", "-C", str(folder), *args], text=True).strip()


class Wiki(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "code"
        self.wiki = Path(self.temp.name) / "wiki"
        self.remote = Path(self.temp.name) / "remote.git"
        for folder in (self.root, self.wiki):
            folder.mkdir()
            git(folder, "init", "-b", "master")
            git(folder, "config", "user.email", "test@example.invalid")
            git(folder, "config", "user.name", "Test")
        self.root.joinpath("src").mkdir()
        self.root.joinpath("tests").mkdir()
        self.root.joinpath("src/game.py").write_text("def move():\n    return 1\n")
        self.root.joinpath("tests/test_game.py").write_text("def test_move():\n    assert move() == 1\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "test: inventory")
        self.code_sha = git(self.root, "rev-parse", "HEAD")
        body = "# Partida\n\n" + "\n\n".join(
            "## " + heading + "\n\nTexto verificável da partida, com resultado esperado e cenário real do sistema."
            for heading in documentation.FEATURE_SECTIONS)
        self.wiki.joinpath("Partida.md").write_text(body)
        self.wiki.joinpath("Produto.md").write_text("# Produto\n\nObjetivo e escopo do jogo. RF-001: mover a cobra.\n")
        self.wiki.joinpath("Home.md").write_text("# Jogo\n\n[Partida](Partida) [Produto](Produto)\n")
        self.wiki.joinpath("_Sidebar.md").write_text("# Navegação\n\n[Início](Home) [Partida](Partida)\n")
        git(self.wiki, "add", ".")
        git(self.wiki, "commit", "-m", "docs: game")
        self.base_sha = git(self.wiki, "rev-parse", "HEAD")
        subprocess.run(["git", "clone", "--bare", str(self.wiki), str(self.remote)],
                       check=True, capture_output=True)
        git(self.wiki, "remote", "add", "origin", str(self.remote))
        self.manifest = {
            "schema": 1, "repositorio": "owner/game", "visibilidade": "publico",
            "wiki": {"base": self.base_sha, "commit": self.base_sha, "branch": "master"},
            "paginas": {"PRODUTO.md": "Produto", "docs/guias/partida.md": "Partida"},
            "categorias": {category: {"pagina": "Produto"} for category in documentation.CATEGORIES},
            "requisitos": {"RF-001": {"pagina": "Produto"}},
            "codigo": {"commit": self.code_sha, "raizes": ["src/"], "excluir": []},
            "funcionalidades": [{"id": "F-001", "requisitos": ["RF-001"], "pagina": "Partida",
                                  "fontes": ["src/game.py"], "testes": ["tests/test_game.py:test_move"],
                                  "hashes": {"src/game.py": hashlib.sha256(
                                      self.root.joinpath("src/game.py").read_bytes()).hexdigest()}}],
            "arquivos_funcionais": [],
        }
        self.save()

    def save(self):
        self.root.joinpath(documentation.MANIFEST).write_text(json.dumps(self.manifest))

    def commit_wiki(self):
        git(self.wiki, "add", ".")
        git(self.wiki, "commit", "-m", "docs: update")
        self.manifest["wiki"]["commit"] = git(self.wiki, "rev-parse", "HEAD")
        self.save()

    def problems(self):
        return documentation.validate(self.root, self.wiki, check_repository=False)

    def test_public_reads_pinned_wiki_without_legacy_file(self):
        with patch.object(documentation, "checkout", return_value=self.wiki):
            self.assertIn("Objetivo", documentation.read(self.root, "PRODUTO.md"))
        self.assertFalse(self.root.joinpath("PRODUTO.md").exists())

    def test_cli_proposal_review_and_publication_preserve_original_until_confirmed(self):
        from bb import cli
        original = self.root.joinpath('PRODUTO.md')
        original.write_text('Documento original preservado')
        draft = self.root.parent.joinpath('draft.md')
        draft.write_text('# Produto\n\nRF-001: mover a cobra com documentação revisada.\n')
        real_git = documentation.git
        def canonical_remote(folder, *args):
            if args == ('remote', 'get-url', 'origin'):
                return 'https://github.com/owner/game.wiki.git'
            return real_git(folder, *args)
        with contextlib.redirect_stdout(io.StringIO()), \
                patch.object(documentation, 'prepare', side_effect=lambda *a: (
                    self.wiki, {'commit': git(self.remote, 'rev-parse', 'master')})), \
                patch.object(documentation, 'checkout', return_value=self.wiki), \
                patch.object(documentation, 'repository_state', return_value={'private': False, 'has_wiki': True}), \
                patch.object(documentation, 'git', side_effect=canonical_remote):
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'gravar',
                                      'PRODUTO.md', '--arquivo', str(draft)]), 0)
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'propor',
                                      '--wiki', str(self.wiki), '--branch', 'bigbang/proposta-1-docs']), 0)
            proposal = json.loads(self.root.joinpath(documentation.MANIFEST).read_text())
            self.assertNotEqual(proposal['wiki']['commit'], self.base_sha)
            self.assertEqual(git(self.remote, 'rev-parse', 'master'), self.base_sha)
            self.assertEqual(original.read_text(), 'Documento original preservado')
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'publicar']), 0)
            self.assertEqual(git(self.remote, 'rev-parse', 'master'), proposal['wiki']['commit'])
            self.assertEqual(original.read_text(), 'Documento original preservado')
            self.assertTrue(any('duplicada' in p for p in self.problems()))
            original.unlink()
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'validar', '--publicada']), 0)
            first = proposal['wiki']['commit']
            draft.write_text('# Produto\n\nRF-001: mover a cobra, revisão subsequente sem concorrência.\n')
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'gravar',
                                      'PRODUTO.md', '--arquivo', str(draft)]), 0)
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'propor',
                                      '--wiki', str(self.wiki), '--branch', 'bigbang/proposta-2-docs']), 0)
            self.assertEqual(cli.main(['--raiz', str(self.root), 'documentacao', 'publicar']), 0)
            second = json.loads(self.root.joinpath(documentation.MANIFEST).read_text())
            self.assertEqual(second['wiki']['base'], first)
            self.assertEqual(git(self.remote, 'rev-parse', 'master'), second['wiki']['commit'])

    def test_private_reads_existing_file_and_does_not_access_github(self):
        self.root.joinpath(documentation.MANIFEST).unlink()
        self.root.joinpath("bigbang.toml").write_text('[projeto]\nvisibilidade="privado"\n')
        self.root.joinpath("PRODUTO.md").write_text("Local privado")
        with patch.object(documentation, "checkout", side_effect=AssertionError("network")):
            self.assertEqual(documentation.read(self.root, "PRODUTO.md"), "Local privado")

    def test_public_repository_cannot_bypass_policy_with_private_config(self):
        self.root.joinpath('bigbang.toml').write_text(
            '[projeto]\nvisibilidade="privado"\nrepositorio="owner/game"\n')
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/game'}), \
                patch.object(documentation, 'repository_state', return_value={'private': False}):
            self.assertTrue(any('visibilidade real diverge' in problem
                                for problem in documentation.visibility_problems(self.root)))

    def test_private_repository_visibility_keeps_current_policy(self):
        self.root.joinpath('bigbang.toml').write_text(
            '[projeto]\nvisibilidade="privado"\nrepositorio="owner/game"\n')
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/game'}), \
                patch.object(documentation, 'repository_state', return_value={'private': True}):
            self.assertEqual(documentation.visibility_problems(self.root), [])

    def test_ci_repository_mismatch_blocks_before_network_access(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/another'}), \
                patch.object(documentation, 'repository_state', side_effect=AssertionError('network')):
            self.assertTrue(any('repositório da esteira diverge' in problem
                                for problem in documentation.visibility_problems(self.root)))

    def test_complete_inventory_passes(self):
        self.assertEqual(self.problems(), [])

    def test_invented_code_commit_is_rejected(self):
        self.manifest['codigo']['commit'] = 'f' * 40
        self.save()
        self.assertTrue(any('commit do código' in p for p in self.problems()))

    def test_absolute_links_to_own_wiki_are_checked(self):
        self.wiki.joinpath('Home.md').write_text(
            '# Jogo\n\n[ausente](https://github.com/owner/game/wiki/Inexistente)\n')
        self.commit_wiki()
        self.assertTrue(any('Inexistente' in p for p in self.problems()))

    def test_unlisted_manual_at_root_is_rejected(self):
        self.root.joinpath('MANUAL.md').write_text('# Manual duplicado\n')
        self.assertTrue(any('MANUAL.md' in p for p in self.problems()))

    def test_new_implemented_module_without_documentation_blocks_delivery(self):
        self.root.joinpath("src/ranking.py").write_text("def ranking():\n    return []\n")
        git(self.root, "add", ".")
        self.assertTrue(any("src/ranking.py" in p for p in self.problems()))

    def test_requirement_must_exist_in_actual_documentation(self):
        self.wiki.joinpath("Produto.md").write_text("# Produto\n\nObjetivo sem requisito identificável.\n")
        self.commit_wiki()
        self.assertTrue(any("RF-001" in p for p in self.problems()))

    def test_empty_functional_sections_do_not_prove_coverage(self):
        self.wiki.joinpath("Partida.md").write_text("# Partida\n\n" + "\n\n".join(
            "## " + heading for heading in documentation.FEATURE_SECTIONS))
        self.commit_wiki()
        self.assertTrue(any("conteúdo" in p for p in self.problems()))

    def test_published_head_must_match_exact_reviewed_commit(self):
        self.wiki.joinpath("Home.md").write_text("# Proposta\n\n[Partida](Partida)\n")
        self.commit_wiki()
        self.assertTrue(any("publicação" in p for p in documentation.validate(
            self.root, self.wiki, published=True, check_repository=False)))

    def test_public_stack_guard_uses_approved_table_from_wiki(self):
        from bb import stack_guard
        self.wiki.joinpath("Stack.md").write_text(
            '# Stack\n\n<!-- bb:dependencias:inicio -->\n| Pacote | Ecossistema |\n'
            '| fastify | npm |\n<!-- bb:dependencias:fim -->\n')
        self.manifest["paginas"]["STACK.md"] = "Stack"
        self.commit_wiki()
        with patch.object(documentation, "checkout", return_value=self.wiki):
            self.assertEqual(stack_guard.allowed(self.root), {("npm", "fastify")})
        self.assertFalse(self.root.joinpath("STACK.md").exists())

    def test_business_rules_survive_migration_without_changing_acceptance_tests(self):
        from bb import traceability
        self.wiki.joinpath("RN-0001-partida.md").write_text('id: RN-0001\nsituacao: vigente\n\n## Regra\n\nMover.\n')
        name = "docs/negocio/regras/RN-0001-partida.md"
        self.manifest["paginas"][name] = "RN-0001-partida"
        self.root.joinpath("tests/aceite").mkdir()
        self.root.joinpath("tests/aceite/test_partida.py").write_text('def test_rn0001_move():\n    assert True\n')
        self.commit_wiki()
        with patch.object(documentation, "checkout", return_value=self.wiki):
            self.assertEqual(traceability.problems(self.root, r"def test_", [name]), [])

    def test_changed_behavior_without_doc_refresh_blocks_delivery(self):
        self.root.joinpath("src/game.py").write_text("def move():\n    return 2\n")
        self.assertTrue(any("desatualizada" in p for p in self.problems()))

    def test_algorithm_tagged_source_hash_is_validated_and_tampering_blocks(self):
        hashes = self.manifest['funcionalidades'][0]['hashes']
        hashes['src/game.py'] = 'sha256:' + hashes['src/game.py']
        self.save()
        self.assertEqual(self.problems(), [])
        self.root.joinpath('src/game.py').write_text('def move():\n    return 99\n')
        self.assertTrue(any('desatualizada' in p for p in self.problems()))

    def test_missing_test_symbol_or_functional_flow_blocks(self):
        self.manifest["funcionalidades"][0]["testes"] = ["tests/test_game.py:test_missing"]
        self.save()
        self.wiki.joinpath("Partida.md").write_text("# Partida\n\nNão há fluxos registrados.\n")
        self.commit_wiki()
        found = self.problems()
        self.assertTrue(any("test_missing" in p for p in found))
        self.assertTrue(any("Fluxo" in p for p in found))

    def test_broken_image_wikilink_and_anchor_are_detected(self):
        self.wiki.joinpath("Home.md").write_text(
            "# Jogo\n\n![tela](assets/missing.png) [[Ausente]] [partida](Partida#nao-existe)\n")
        self.commit_wiki()
        found = self.problems()
        for target in ("assets/missing.png", "Ausente", "Partida#nao-existe"):
            self.assertTrue(any(target in p for p in found), found)

    def test_local_system_docs_block_but_functional_contracts_remain(self):
        self.root.joinpath("PRODUTO.md").write_text("Duplicado")
        self.assertTrue(any("PRODUTO.md" in p for p in self.problems()))
        self.root.joinpath("PRODUTO.md").unlink()
        self.root.joinpath("docs").mkdir()
        self.root.joinpath("docs/contract.md").write_text("Contrato consumido pelo código")
        self.manifest["arquivos_funcionais"] = [
            {"caminho": "docs/contract.md", "motivo": "Contrato lido pelo verificador do projeto"}]
        self.save()
        self.assertEqual(self.problems(), [])

    def test_public_missing_manifest_fails_clearly(self):
        self.root.joinpath(documentation.MANIFEST).unlink()
        self.root.joinpath("bigbang.toml").write_text('[projeto]\nvisibilidade="publico"\n')
        with self.assertRaisesRegex(BbError, "manifesto"):
            documentation.read(self.root, "PRODUTO.md")

    def test_traversal_manifest_cannot_read_outside_wiki(self):
        self.manifest["paginas"]["PRODUTO.md"] = "../secret"
        self.save()
        with patch.object(documentation, "checkout", return_value=self.wiki):
            with self.assertRaises(BbError):
                documentation.read(self.root, "PRODUTO.md")

    def test_uninitialized_wiki_does_not_modify_local_documents(self):
        self.root.joinpath("PRODUTO.md").write_text("Preservar")
        with patch.object(documentation, "repository_state", return_value={"has_wiki": True}), \
                patch.object(documentation, "git", side_effect=BbError("Wiki sem HEAD")):
            with self.assertRaises(BbError):
                documentation.preflight("owner/game")
        self.assertEqual(self.root.joinpath("PRODUTO.md").read_text(), "Preservar")

    def test_publish_fast_forwards_and_rerun_is_idempotent(self):
        self.wiki.joinpath("Home.md").write_text("# Jogo\n\n[Partida](Partida)\n")
        self.commit_wiki()
        documentation.publish(self.root, self.wiki, check_repository=False)
        self.assertEqual(git(self.remote, "rev-parse", "master"), self.manifest["wiki"]["commit"])
        documentation.publish(self.root, self.wiki, check_repository=False)

    def test_concurrent_owner_change_is_preserved_and_publication_rejected(self):
        other = Path(self.temp.name) / "other"
        subprocess.run(["git", "clone", str(self.remote), str(other)], check=True, capture_output=True)
        git(other, "config", "user.email", "owner@example.invalid")
        git(other, "config", "user.name", "Owner")
        other.joinpath("Owner.md").write_text("# Alteração concorrente do dono\n")
        git(other, "add", ".")
        git(other, "commit", "-m", "docs: owner")
        git(other, "push", "origin", "master")
        owner_sha = git(other, "rev-parse", "HEAD")
        self.wiki.joinpath("Home.md").write_text("# Nossa proposta\n\n[Partida](Partida)\n")
        self.commit_wiki()
        with self.assertRaisesRegex(BbError, "concorrente"):
            documentation.publish(self.root, self.wiki, check_repository=False)
        self.assertEqual(git(self.remote, "rev-parse", "master"), owner_sha)


if __name__ == "__main__":
    unittest.main()
