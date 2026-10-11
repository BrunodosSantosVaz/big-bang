"""v3 skills (epic #233 · plan 7.4): a grouping-workflow project gets the v3 version of the adapted skills and the
v3-only skills; a legacy project keeps the current skills untouched."""
import os
import tempfile
import unittest

from _raiz import RAIZ, importar_bb
from test_grouping_v3 import GeneratedV3

importar_bb()
from bb import generator  # noqa: E402

ADAPTED = ("bb-refinar-backlog", "bb-rodar-sprint", "bb-codar-tarefa", "bb-entregar-epico", "bb-corrigir-bug",
           "bb-status", "bb-montar-github", "bb-atualizar", "bb-escrever-testes-aceite", "bb-documentar-epico",
           "bb-triar-issue")
V3_ONLY = ("bb-reject",)
LEGACY_WORDS = ("`epico/", " epico/", "Iniciar sprint", "bb assumir", "Integrar release", "Homologação ou adiante")


def skill(root, name, target=".claude/skills"):
    path = os.path.join(root, target, name, "SKILL.md")
    return open(path, encoding="utf-8").read() if os.path.exists(path) else None


class SkillsV3(unittest.TestCase):
    def test_every_override_has_a_legacy_skill_or_is_v3_only(self):
        overrides = os.listdir(os.path.join(RAIZ, ".bigbang", "pipeline", "skills"))
        legacy = os.listdir(os.path.join(RAIZ, ".bigbang", "skills"))
        self.assertEqual(sorted(set(overrides) - set(legacy)), sorted(V3_ONLY))
        self.assertEqual(sorted(set(ADAPTED) - set(overrides)), [])

    def test_v3_project_gets_the_v3_skills(self):
        helper = GeneratedV3()
        with tempfile.TemporaryDirectory() as folder:
            root = helper.project(folder)
            generator.apply(generator.build_plan(root, install_pipeline=True), root)
            for target in generator.SKILL_TARGETS:
                for name in ADAPTED + V3_ONLY:
                    text = skill(root, name, target)
                    self.assertIsNotNone(text, f"{target}/{name}")
                    self.assertIn(f"name: {name}", text)
                    for word in LEGACY_WORDS:
                        self.assertNotIn(word, text, f"{target}/{name}: {word}")
            self.assertIn("bb sprint start", skill(root, "bb-rodar-sprint"))
            self.assertIn("bb claim", skill(root, "bb-codar-tarefa"))
            self.assertIn("bb release publish", skill(root, "bb-entregar-epico"))
            self.assertIn("bb move", skill(root, "bb-reject"))

    def test_legacy_project_keeps_the_current_skills(self):
        with tempfile.TemporaryDirectory() as folder:
            import shutil
            from _cenarios import CENARIOS
            from _raiz import ignorar_para_copia
            from bb import checksums, init
            from bb.paths import framework_version
            root = os.path.join(folder, "projeto")
            shutil.copytree(RAIZ, root, ignore=ignorar_para_copia("bigbang.toml", "STACK.md", ".worktrees"))
            checksums.write(root)
            with open(os.path.join(CENARIOS, "deploy-vps-docker.toml"), encoding="utf-8") as handle:
                text = init.set_value(handle.read(), "bigbang", "versao", framework_version(root))
            with open(os.path.join(root, "bigbang.toml"), "w", encoding="utf-8") as handle:
                handle.write(text)
            generator.apply(generator.build_plan(root, install_pipeline=True), root)
            original = open(os.path.join(RAIZ, ".bigbang", "skills", "bb-rodar-sprint", "SKILL.md"),
                            encoding="utf-8").read()
            self.assertIn(original.split("---", 2)[2].strip()[:200], skill(root, "bb-rodar-sprint"))
            self.assertIsNone(skill(root, "bb-reject"))


if __name__ == "__main__":
    unittest.main()


class ProcessV3(unittest.TestCase):
    def test_every_process_reference_of_the_v3_layer_exists(self):
        import re
        base = os.path.join(RAIZ, ".bigbang", "pipeline")
        texts = [open(os.path.join(base, "AGENTS.base.md"), encoding="utf-8").read()]
        for name in os.listdir(os.path.join(base, "skills")):
            texts.append(open(os.path.join(base, "skills", name, "SKILL.md"), encoding="utf-8").read())
        found = set()
        for text in texts:
            found |= set(re.findall(r"\.bigbang/pipeline/process/([a-z-]+\.md)", text))
        for name in ("execution.md", "sprint.md", "delivery.md"):
            found.add(name)
        for name in sorted(found):
            self.assertTrue(os.path.exists(os.path.join(base, "process", name)), name)
        sibling = re.compile(r"`(execution|sprint|delivery|board|planning|bugs|modes)\.md`")
        for text in texts:
            for name in sibling.findall(text):
                self.assertTrue(os.path.exists(os.path.join(base, "process", name + ".md")), name)

    def test_v3_agents_md_points_to_the_v3_process(self):
        helper = GeneratedV3()
        with tempfile.TemporaryDirectory() as folder:
            root = helper.project(folder)
            generator.apply(generator.build_plan(root, install_pipeline=True), root)
            agents = open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read()
            for legacy in ("processo/06-execucao.md", "processo/17-flash.md", "processo/05-sprint.md",
                           "processo/09-entrega.md"):
                self.assertNotIn(legacy, agents)
            self.assertIn(".bigbang/pipeline/process/", agents)
