"""Names table and bilingual bigbang.toml (epic #223, ADR-0024): a v3 file in English must behave exactly like the
legacy Portuguese file, and legacy code must keep reading both."""
import os
import shutil
import tempfile
import unittest

from _cenarios import CENARIOS, ESPERADO, NOMES, esperado
from _raiz import RAIZ, ignorar_para_copia, importar_bb

importar_bb()
from bb import checksums, config, generator, names  # noqa: E402
from bb.errors import BbError  # noqa: E402
from bb.init import set_value  # noqa: E402
from bb.paths import framework_version  # noqa: E402


def scenario_text(name):
    with open(os.path.join(CENARIOS, f"{name}.toml"), encoding="utf-8") as handle:
        return set_value(handle.read(), "bigbang", "versao", framework_version(RAIZ))


class Names(unittest.TestCase):
    def test_every_key_round_trips(self):
        for section, keys in names.KEYS.items():
            for key in keys:
                legacy = f"{section}.{key}"
                with self.subTest(key=legacy):
                    self.assertEqual(names.key_to_legacy(names.key_to_v3(legacy)), legacy)

    def test_values_round_trip(self):
        for dotted, mapping in names.VALUES.items():
            for legacy, v3 in mapping.items():
                self.assertEqual(names.value_to_v3(dotted, legacy), v3)
                self.assertEqual(names.value_to_legacy(dotted, v3), legacy)

    def test_v3_only_keys_have_no_legacy_name(self):
        self.assertIsNone(names.key_to_legacy("workflow.model"))
        self.assertIsNone(names.key_to_legacy("board.model"))
        self.assertEqual(names.key_to_legacy("board.planning"), "paineis.planejamento")

    def test_decision_labels_in_both_dialects(self):
        self.assertEqual(len(names.DECISIONS), len(names.DECISIONS_LEGACY))
        self.assertEqual(names.label("homologado", "v3"), "qa:approved")
        self.assertEqual(names.label("qa:approved", "legacy"), "homologado")
        self.assertEqual(names.label("qa:approved", "v3"), "qa:approved")

    def test_every_legacy_cli_command_has_one_v3_name(self):
        aliases = [alias for values in names.COMMANDS.values() for alias in values]
        self.assertEqual(len(aliases), len(set(aliases)))
        self.assertFalse(set(aliases) & set(names.COMMANDS))


class BilingualConfig(unittest.TestCase):
    def test_scenarios_translate_and_validate(self):
        for name in NOMES:
            with self.subTest(scenario=name):
                v3 = config.text_to_v3(scenario_text(name))
                self.assertEqual(config.dialect(config.parse(v3)), "v3")
                self.assertEqual(config.validate(config.parse(v3)), [])
                self.assertIn('[workflow]\nmodel = "epic-branch"', v3)

    def test_both_files_load_into_the_same_views(self):
        for name in NOMES:
            with self.subTest(scenario=name):
                legacy = config.views(config.parse(scenario_text(name)))
                v3 = config.views(config.parse(config.text_to_v3(scenario_text(name))))
                legacy.pop("_dialect"), v3.pop("_dialect")
                self.assertEqual(legacy, v3)

    def test_v3_file_generates_exactly_the_expected_layer(self):
        for name in NOMES:
            with self.subTest(scenario=name), tempfile.TemporaryDirectory() as folder:
                root = os.path.join(folder, "projeto")
                shutil.copytree(RAIZ, root, ignore=ignorar_para_copia("bigbang.toml", "STACK.md", ".worktrees"))
                checksums.write(root)
                with open(os.path.join(root, "bigbang.toml"), "w", encoding="utf-8") as handle:
                    handle.write(config.text_to_v3(scenario_text(name)))
                shutil.copy(os.path.join(root, ".bigbang", "modelos", "STACK.md"), os.path.join(root, "STACK.md"))
                plan = generator.build_plan(root, install_pipeline=True)
                self.assertEqual(plan.expected, esperado(name))

    def test_get_answers_in_both_dialects(self):
        loaded = config.views(config.parse(config.text_to_v3(scenario_text("deploy-vps-docker"))))
        self.assertEqual(config.get(loaded, "projeto.modo"), "padrao")
        self.assertEqual(config.get(loaded, "project.mode"), "normal")
        self.assertEqual(config.get(loaded, "entrega.perfil"), "deploy")
        self.assertEqual(config.get(loaded, "deploy.servico_migrar"), "migrar")  # optional default
        self.assertEqual(config.get(loaded, "deploy.migrate_service"), "migrar")
        self.assertEqual(config.get(loaded, "workflow.model"), "epic-branch")
        self.assertEqual(config.get(loaded, "board.model"), "three-boards")

    def test_get_translates_plain_mappings(self):
        plain = config.parse(scenario_text("compilado-windows-linux"))
        self.assertEqual(config.get(plain, "delivery.profile"), "compiled")
        self.assertEqual(config.get(plain, "project.visibility"), "private")
        self.assertEqual(config.get(plain, "workflow.model"), "epic-branch")
        v3 = config.parse(config.text_to_v3(scenario_text("compilado-windows-linux")))
        self.assertEqual(config.get(v3, "entrega.perfil"), "compilado")

    def test_autonomous_mode_is_v3_only_and_reads_as_flash_in_the_legacy_view(self):
        text = config.text_to_v3(scenario_text("deploy-vps-docker")).replace(
            'repository = "BrunodosSantosVaz/meu-sistema"',
            'repository = "BrunodosSantosVaz/meu-sistema"\nmode = "autonomous"')
        loaded = config.views(config.parse(text))
        self.assertEqual(config.get(loaded, "project.mode"), "autonomous")
        self.assertEqual(config.get(loaded, "projeto.modo"), "flash")

    def test_mixed_file_is_refused(self):
        raw = config.parse(scenario_text("deploy-vps-docker"))
        raw["workflow"] = {"model": "grouping"}
        self.assertEqual(config.dialect(raw), "mixed")
        self.assertIn("mistura", config.validate(raw)[0])

    def test_errors_use_v3_names(self):
        raw = config.parse(config.text_to_v3(scenario_text("deploy-vps-docker")))
        raw["project"]["colour"] = "x"
        self.assertEqual(config.validate(raw), ["chave desconhecida: project.colour"])
        del raw["project"]["colour"]
        del raw["delivery"]["artifact_paths"]
        self.assertEqual(config.validate(raw), ["chave obrigatória ausente: delivery.artifact_paths"])

    def test_legacy_values_are_refused_in_v3_files(self):
        raw = config.parse(config.text_to_v3(scenario_text("compilado-windows-linux")))
        raw["delivery"]["profile"] = "compilado"
        self.assertIn("use o valor em inglês 'compiled'", config.validate(raw)[0])

    def test_single_board_needs_its_number_and_fills_the_legacy_view(self):
        raw = config.parse(config.text_to_v3(scenario_text("compilado-windows-linux")))
        raw["board"] = {"owner": "BrunodosSantosVaz", "model": "single", "number": 42}
        self.assertEqual(config.validate(raw), [])
        loaded = config.views(raw)
        self.assertEqual(loaded["paineis"]["planejamento"], 42)
        self.assertEqual(config.get(loaded, "board.number"), 42)
        raw["board"]["planning"] = 3
        self.assertIn("board.planning: só existe no modelo three-boards", config.validate(raw))
        del raw["board"]["planning"]
        raw["board"]["number"] = "x"
        self.assertIn("board.number", config.validate(raw)[0])

    def test_workflow_model_values(self):
        raw = config.parse(config.text_to_v3(scenario_text("compilado-windows-linux")))
        raw["workflow"]["model"] = "trunk"
        self.assertIn("workflow.model", config.validate(raw)[0])

    def test_already_v3_text_is_not_translated_again(self):
        with self.assertRaises(BbError):
            config.text_to_v3(config.text_to_v3(scenario_text("compilado-windows-linux")))


class ReviewFindings(unittest.TestCase):
    """Regressions found in the review of #242: legacy outputs preserved and every reader understands a v3 file."""

    def legacy(self):
        return config.views(config.parse(scenario_text("deploy-vps-docker")))

    def v3_public_text(self):
        text = config.text_to_v3(scenario_text("deploy-vps-docker"))
        return text.replace('visibility = "private"', 'visibility = "public"').replace(
            'license = ""', 'license = "MIT"')

    def test_missing_legacy_key_reports_the_key_that_was_asked(self):
        for key in ("projeto.inexistente", "compilado.build_linux", "deploy.imagemx"):
            with self.subTest(key=key), self.assertRaises(BbError) as error:
                config.get(self.legacy(), key)
            self.assertIn(key, error.exception.message)
        with self.assertRaises(BbError) as error:
            config.get(self.legacy(), "projeto")
        self.assertIn("projeto é uma seção", error.exception.message)

    def test_mixed_language_keys_and_internal_keys_are_refused(self):
        for key in ("projeto.mode", "project.modo", "paineis.model", "_dialect", "_dialect.x"):
            with self.subTest(key=key), self.assertRaises(BbError):
                config.get(self.legacy(), key)

    def test_consistent_keys_answer_in_both_languages(self):
        loaded = self.legacy()
        self.assertEqual(config.get(loaded, "deploy.image"), config.get(loaded, "deploy.imagem"))
        self.assertEqual(config.get(loaded, "project.mode"), "normal")

    def test_documentation_reads_a_v3_public_file(self):
        from bb import documentation
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "bigbang.toml"), "w", encoding="utf-8") as handle:
                handle.write(self.v3_public_text())
            self.assertTrue(documentation.is_public(root))
            from unittest.mock import patch
            with patch.object(documentation, "repository_state", return_value={"private": False}), \
                    patch.dict(os.environ, {"GITHUB_REPOSITORY": "BrunodosSantosVaz/meu-sistema"}):
                self.assertEqual(documentation.visibility_problems(root), [])

    def test_target_mode_reads_both_dialects(self):
        from bb import decisions
        for text, expected in (('[projeto]\nmodo="flash"\n', "flash"), ('[project]\nmode="flash"\n', "flash"),
                               ('[project]\nmode="normal"\n', "padrao"), ('[project]\nmode="autonomous"\n', "flash"),
                               ('[projeto]\nmodo="padrao"\n', "padrao")):
            with self.subTest(text=text):
                self.assertEqual(decisions.mode_from_text(text), expected)
        with self.assertRaises(BbError):
            decisions.mode_from_text('[project]\nmode="turbo"\n')

    def test_review_blockers_see_v3_labels(self):
        from bb import decisions
        blockers = decisions.review_blockers({"review:human"}, set(), "feature/12-x", [], "", [], "x")
        self.assertTrue(blockers)
        self.assertEqual(decisions.review_blockers({"review:human"}, {"owner:ai-review"}, "feature/12-x", [], "",
                                                   [], "x"), [])
        self.assertTrue(decisions.review_blockers(set(), {"tests-review:human"}, "test/11-testes", [], "", [], "x"))

    def test_set_config_value_in_each_dialect(self):
        from bb import init
        legacy = scenario_text("compilado-windows-linux")
        v3 = config.text_to_v3(legacy)
        self.assertIn('version = "9.9.9"', init.set_config_value(v3, "bigbang.versao", "9.9.9"))
        self.assertIn('name = "Outro"', init.set_config_value(v3, "projeto.nome", "Outro"))
        updated = init.set_config_value(legacy, "bigbang.versao", "9.9.9")
        self.assertEqual(updated, init.set_value(legacy, "bigbang", "versao", "9.9.9"))

    def test_v3_errors_do_not_hide_structural_ones(self):
        raw = config.parse(config.text_to_v3(scenario_text("deploy-vps-docker")))
        del raw["board"]
        del raw["commands"]
        errors = config.validate(raw)
        self.assertTrue(any("[commands]" in error for error in errors), errors)


class EnglishCli(unittest.TestCase):
    """v3 commands and options, with every legacy spelling still accepted (the scripts of legacy projects use them)."""

    def setUp(self):
        import contextlib
        import io
        from bb import cli
        self.folder = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.folder.name, "projeto")
        shutil.copytree(RAIZ, self.root, ignore=ignorar_para_copia("bigbang.toml", "STACK.md", ".worktrees"))
        checksums.write(self.root)
        with open(os.path.join(self.root, "bigbang.toml"), "w", encoding="utf-8") as handle:
            handle.write(config.text_to_v3(scenario_text("deploy-vps-docker")))

        def run(*argv):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                code = cli.main(list(argv))
            return code, output.getvalue().strip()
        self.run_bb = run

    def tearDown(self):
        self.folder.cleanup()

    def test_config_get_in_both_languages_and_both_option_spellings(self):
        for argv, expected in ((("--root", self.root, "config", "get", "project.mode"), "normal"),
                               (("--raiz", self.root, "config", "get", "projeto.modo"), "padrao"),
                               (("--root", self.root, "config", "get", "delivery.profile"), "deploy"),
                               (("--root", self.root, "config", "get", "workflow.model"), "epic-branch")):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_bb(*argv), (0, expected))

    def test_generate_and_verify_by_either_name(self):
        self.assertEqual(self.run_bb("--root", self.root, "generate", "--pipeline")[0], 0)
        self.assertEqual(self.run_bb("--root", self.root, "verify"), (0, "bb verificar: tudo certo."))
        self.assertEqual(self.run_bb("--raiz", self.root, "verificar"), (0, "bb verificar: tudo certo."))
        self.assertEqual(self.run_bb("--root", self.root, "gerar", "--dry-run")[0], 0)

    def test_pipeline_subcommands_by_either_name(self):
        for name in ("title", "titulo"):
            with self.subTest(name=name):
                self.assertEqual(self.run_bb("--root", self.root, "pipeline", name, "feat: x")[0], 0)
                self.assertEqual(self.run_bb("--root", self.root, "esteira", name, "feat: x")[0], 0)

    def test_decision_labels_follow_the_project_label_dialect(self):
        from bb import decisions
        self.assertIn("qa:approved", decisions.ALL_DECISIONS)
        self.assertIn("homologado", decisions.ALL_DECISIONS)
        legacy = config.views(config.parse(config.text_to_v3(scenario_text("deploy-vps-docker"))))
        self.assertEqual(names.label("qa:approved", names.label_dialect(legacy)), "homologado")
        raw = config.parse(config.text_to_v3(scenario_text("deploy-vps-docker")))
        raw["board"]["labels"] = "v3"
        self.assertEqual(names.label("homologado", names.label_dialect(config.views(raw))), "qa:approved")


if __name__ == "__main__":
    unittest.main()
