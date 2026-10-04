"""E8 catalog contract and discovery/integrity before the Foundation."""
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from _raiz import BIGBANG, importar_bb

importar_bb()
from bb import checksums, generator, verify  # noqa: E402

NAMES = {
    "bb-iniciar-projeto", "bb-entrevista-produto", "bb-escolher-stack", "bb-design-kit", "bb-montar-github",
    "bb-gerar", "bb-refinar-backlog", "bb-prototipar", "bb-rodar-sprint", "bb-escrever-testes-aceite",
    "bb-codar-tarefa", "bb-documentar-epico", "bb-corrigir-bug", "bb-entregar-epico", "bb-triar-issue",
    "bb-nova-tecnologia", "bb-status", "bb-atualizar", "bb-retrospectiva", "bb-auditar-seguranca",
}
HEADINGS = ("Quando usar", "Antes de começar", "Passos", "Pare e pergunte quando", "Nunca", "Pronto quando")


class Catalogo(unittest.TestCase):
    def test_catalogo_e_formato_agent_skills(self):
        folder = Path(BIGBANG, "skills")
        self.assertEqual({p.name for p in folder.iterdir() if p.is_dir() and p.name != "__pycache__"}, NAMES)
        for name in sorted(NAMES):
            with self.subTest(skill=name):
                text = (folder / name / "SKILL.md").read_text(encoding="utf-8")
                header = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n", text)
                self.assertIsNotNone(header)
                self.assertEqual(header[1], name)
                self.assertLessEqual(len(name), 64)
                self.assertNotIn("--", name)
                self.assertTrue(1 <= len(header[2]) <= 1024)
                self.assertLessEqual(len(text.splitlines()), 150)
                headings = re.findall(r"^## (.+)$", text, re.M)
                self.assertEqual(tuple(headings), HEADINGS)
                for reference in re.findall(r"`(\.bigbang/[^`]+)`", text):
                    self.assertTrue(Path(BIGBANG).parent.joinpath(reference).exists(), reference)


class AntesDaFundacao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bb-skills-", suffix=" com espacos")
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        shutil.copytree(BIGBANG, os.path.join(self.root, ".bigbang"), ignore=shutil.ignore_patterns("__pycache__"))
        checksums.write(self.root)
        generator.apply(generator.build_plan(self.root), self.root)

    def test_skills_descobertas_antes_do_init_sem_esteira(self):
        self.assertFalse(Path(self.root, "bigbang.toml").exists())
        self.assertFalse(Path(self.root, ".github").exists())
        self.assertEqual(verify.run(self.root), [])
        for name in NAMES:
            first = Path(self.root, ".agents/skills", name, "SKILL.md").read_bytes()
            second = Path(self.root, ".claude/skills", name, "SKILL.md").read_bytes()
            self.assertEqual(first, second)
            self.assertTrue(first.startswith(b"---\n"))

    def test_edicao_de_uma_copia_reprova_e_gerador_repara(self):
        path = Path(self.root, ".claude/skills/bb-status/SKILL.md")
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\nAlteracao manual.\n", encoding="utf-8")
        self.assertTrue(any(".claude/skills/bb-status/SKILL.md" in p for p in verify.run(self.root)))
        generator.apply(generator.build_plan(self.root), self.root)
        self.assertEqual(verify.run(self.root), [])
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_skill_do_projeto_e_preservada(self):
        path = Path(self.root, ".agents/skills/minha-skill/SKILL.md")
        path.parent.mkdir(parents=True)
        path.write_text("# Skill do projeto\n", encoding="utf-8")
        generator.apply(generator.build_plan(self.root), self.root)
        self.assertEqual(path.read_text(encoding="utf-8"), "# Skill do projeto\n")
        self.assertEqual(verify.run(self.root), [])


if __name__ == "__main__":
    unittest.main()
