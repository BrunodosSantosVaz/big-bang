"""Execute the registered PreToolUse guards with real JSON input, not mocked decisions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from _raiz import BIGBANG, importar_bb

importar_bb()
from bb import generator, verify, checksums  # noqa: E402


class ComHook(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bb-hooks-", suffix=" com espacos")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".bigbang").mkdir()
        self.git("init", "--initial-branch=main")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def hook(self, script, tool, **values):
        event = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(self.root), "tool_input": values}
        result = self.raw(script, json.dumps(event))
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout:
            return None
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertTrue(output["permissionDecisionReason"])
        return output["permissionDecision"]

    def raw(self, script, payload):
        return subprocess.run([sys.executable, str(Path(BIGBANG, "hooks", script))], input=payload,
                              cwd=self.root, capture_output=True, text=True, check=False,
                              env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)}, timeout=15)


class Arquivos(ComHook):
    def call(self, name, tool="Write", **fields):
        return self.hook("proteger_arquivos.py", tool, file_path=str(self.root / name), **fields)

    def test_nega_framework_aceite_e_gerados_inclusive_arquivo_novo(self):
        for path in (".bigbang/novo.py", "tests/aceite/teste.py", ".agents/skills/bb-status/SKILL.md",
                     ".claude/skills/bb-status/SKILL.md", ".claude/agents/bb-revisor-pr.md",
                     ".claude/settings.json", ".github/workflows/bb-ci.yml"):
            with self.subTest(path=path):
                self.assertEqual(self.call(path, content="x"), "deny")

    def test_documentos_de_decisao_pedem_confirmacao(self):
        for path in ("PRODUTO.md", "STACK.md", "DESIGN.md", "bigbang.toml", "flags.toml"):
            with self.subTest(path=path):
                self.assertEqual(self.call(path, content="x"), "ask")

    def test_codigo_e_skill_propria_seguem_permissoes_normais(self):
        self.assertIsNone(self.call("src/parser.py", content="x"))
        self.assertIsNone(self.call(".agents/skills/minha-skill/SKILL.md", content="x"))

    def test_alias_e_caminho_com_separadores_windows_nao_contornam(self):
        alias = self.root / "atalho"
        try:
            alias.symlink_to(self.root / ".bigbang", target_is_directory=True)
        except OSError:
            self.skipTest("symlink indisponivel nesta plataforma")
        self.assertEqual(self.call("atalho/novo.py", content="x"), "deny")
        path = str(self.root / "tests/aceite/teste.py").replace("/", "\\")
        self.assertEqual(self.hook("proteger_arquivos.py", "Edit", file_path=path,
                                   old_string="x", new_string="y"), "deny")

    def test_aviso_de_gerado_e_protegido_sem_prefixo(self):
        self.write("config/arquivo.md", "<!-- Gerado pelo Big Bang v0.7.0 -->\n# Config\n")
        self.assertEqual(self.call("config/arquivo.md", content="x"), "deny")

    def test_edicao_na_secao_do_projeto_preserva_bloco_agents(self):
        block = "<!-- bigbang:inicio v0.7.0 -->\nRegra.\n<!-- bigbang:fim -->"
        self.write("AGENTS.md", block + "\n\n## Projeto\nAntigo.\n")
        self.assertIsNone(self.call("AGENTS.md", "Edit", old_string="Antigo.", new_string="Novo."))
        self.assertEqual(self.call("AGENTS.md", "Edit", old_string="Regra.", new_string="Livre."), "deny")
        self.assertEqual(self.call("AGENTS.md", content="# Apagado\n"), "deny")
        self.assertIsNone(self.call("AGENTS.md", content=block + "\n\n## Projeto\nNovo.\n"))

    def test_stack_nega_bloco_mas_pede_confirmacao_fora_dele(self):
        text = "# Stack\nPython.\n<!-- bb:config:inicio -->\nGerado.\n<!-- bb:config:fim -->\n"
        self.write("STACK.md", text)
        self.assertEqual(self.call("STACK.md", "Edit", old_string="Python.", new_string="Outra."), "ask")
        self.assertEqual(self.call("STACK.md", "Edit", old_string="Gerado.", new_string="Livre."), "deny")

    def test_alias_de_documento_preserva_classificacao_lexical(self):
        text = "# Stack\nPython.\n" + "\n" * 9 + "<!-- bb:config:inicio -->\nGerado.\n<!-- bb:config:fim -->\n"
        target = self.write("docs/stack-real.md", text)
        try:
            (self.root / "STACK.md").symlink_to(target)
        except OSError:
            self.skipTest("symlink indisponivel nesta plataforma")
        self.assertEqual(self.call("STACK.md", "Edit", old_string="Python.", new_string="Outra."), "ask")
        self.assertEqual(self.call("STACK.md", "Edit", old_string="Gerado.", new_string="Livre."), "deny")
        self.assertEqual(self.call("STACK.md", content="# Apagado\n"), "deny")

    def test_falha_de_entrada_bloqueia_sem_vazar_evento(self):
        for data in ("{", "[]", '{"tool_input": "segredo-nao-expor"}'):
            result = self.raw("proteger_arquivos.py", data)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("segredo-nao-expor", result.stdout + result.stderr)


class Comandos(ComHook):
    def call(self, command, tool="Bash"):
        return self.hook("proteger_comandos.py", tool, command=command)

    def test_push_direto_e_force_sao_negados(self):
        for command in ("git push origin main", "git push origin HEAD:develop", "git push origin feature/a:epico/1-a",
                        "git push origin refs/heads/feature/a:refs/heads/main", "git push origin HEAD",
                        "git push", "git push origin --all", "git push origin --mirror",
                        "git push -f origin feature/a", "git push --force-with-lease origin feature/a",
                        "git push origin +feature/a:feature/a"):
            with self.subTest(command=command):
                self.assertEqual(self.call(command), "deny")

    def test_branch_propria_e_leituras_nao_sao_aprovadas_automaticamente(self):
        for command in ("git push origin feature/1-parser", "git status --short", "gh pr view 1",
                        "bb decisao homologado 1 --frase 'Homologado pelo dono'", "python .bigbang/bin/bb.py verificar"):
            with self.subTest(command=command):
                self.assertIsNone(self.call(command))

    def test_reset_e_tags_negados(self):
        for command in ("git reset --hard HEAD", "git tag -d v1.0.0", "git tag --force v1.0.0 HEAD",
                        "git update-ref -d refs/tags/v1.0.0", "git push origin :refs/tags/v1.0.0",
                        "git push origin --delete main", "gh release delete v1.0.0 --cleanup-tag"):
            with self.subTest(command=command):
                self.assertEqual(self.call(command), "deny")

    def test_labels_de_decisao_negadas_em_cli_e_api(self):
        for command in ("gh issue edit 1 --add-label homologado", "gh pr edit 2 --add-label=pr-aprovado",
                        "gh issue edit 1 --add-label 'bug,dono:revisao-ia'",
                        "gh api -X POST repos/dono/repo/issues/1/labels -f 'labels[]=testes-aprovados'",
                        "gh api repos/dono/repo/git/refs/tags/v1 --method=DELETE"):
            with self.subTest(command=command):
                self.assertEqual(self.call(command), "deny")
        self.assertIsNone(self.call("gh issue edit 1 --add-label bug"))
        self.assertIsNone(self.call("gh issue comment 1 --body 'Falta homologado, nao aplicar a label'"))

    def test_composto_nao_e_isentado_por_bb(self):
        self.assertEqual(self.call("bb verificar && git push origin main"), "deny")
        self.assertEqual(self.call("git status; git reset --hard"), "deny")
        self.assertEqual(self.call("env LANG=C command git push origin develop"), "deny")
        self.assertEqual(self.call("git status\ngit push origin main"), "deny")

    def test_formas_dinamicas_pedem_conferencia(self):
        for command in ("git push origin HEAD:$DESTINO", "git -c alias.enviar=push enviar origin feature/a",
                        "bash -c 'git push origin main'",
                        "gh api graphql -f query='mutation { addLabelsToLabelable(input:{}) { clientMutationId } }'"):
            with self.subTest(command=command):
                self.assertEqual(self.call(command), "ask")

    def test_opcoes_globais_do_gh_nao_isentam_decisoes(self):
        for command in ("gh -R dono/repo issue edit 1 --add-label homologado",
                        "gh --repo=dono/repo pr edit 2 --add-label pr-aprovado",
                        "gh -Rdono/repo issue edit 1 --add-label testes-aprovados",
                        "gh --hostname github.com api -XDELETE repos/dono/repo/git/refs/tags/v1"):
            with self.subTest(command=command):
                self.assertEqual(self.call(command), "deny")
        self.assertEqual(self.call("gh --opcao-desconhecida issue edit 1 --add-label homologado"), "ask")
        self.assertIsNone(self.call("gh -R dono/repo pr view 1"))

    def test_pontuacao_agrupada_nao_esconde_comando_seguinte(self):
        for command in ("(git status); git push origin main", "(git status); git tag -d v1.0.0",
                        "(git status)&&git reset --hard", "(bb verificar)||git push origin develop"):
            with self.subTest(command=command):
                self.assertEqual(self.call(command), "deny")

    def test_powershell_tambem_aciona_os_bloqueios(self):
        self.assertEqual(self.call("git.exe push origin main", "PowerShell"), "deny")
        self.assertEqual(self.call("Git.exe reset --hard", "PowerShell"), "deny")


class Registro(unittest.TestCase):
    def test_settings_gerado_registra_scripts_executaveis_e_verificacao(self):
        with tempfile.TemporaryDirectory(prefix="bb-registro-", suffix=" com espacos") as folder:
            root = Path(folder)
            shutil.copytree(BIGBANG, root / ".bigbang", ignore=shutil.ignore_patterns("__pycache__"))
            checksums.write(folder)
            generator.apply(generator.build_plan(folder), folder)
            settings = root / ".claude/settings.json"
            data = json.loads(settings.read_text(encoding="utf-8"))
            matchers = {entry["matcher"] for entry in data["hooks"]["PreToolUse"]}
            self.assertIn("Bash|PowerShell", matchers)
            self.assertIn("Edit|Write|MultiEdit|NotebookEdit", matchers)
            event = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(root),
                                "tool_input": {"file_path": str(root / ".bigbang/novo.py"), "content": "x"}})
            handler = data["hooks"]["PreToolUse"][0]["hooks"][0]
            self.assertEqual(handler["type"], "command")
            arguments = [arg.replace("${CLAUDE_PROJECT_DIR}", folder) for arg in handler["args"]]
            result = subprocess.run([handler["command"], *arguments], input=event, cwd=root,
                                    capture_output=True, text=True, check=False, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertEqual(verify.run(folder), [])
            data["hooks"] = {}
            settings.write_text(json.dumps(data), encoding="utf-8")
            self.assertTrue(any(".claude/settings.json" in problem for problem in verify.run(folder)))


if __name__ == "__main__":
    unittest.main()
