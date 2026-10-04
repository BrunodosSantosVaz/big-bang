"""`bb atualizar` (spec 5.7, ADR-0014): a project on the current version updates to a newer package without any change
in the project layer; a wrong hash, a failed attestation or an unconfirmed manual step stops before touching anything."""
import os
import re
import shutil
import subprocess
import sys

from _raiz import BIGBANG, exemplo_toml, ignorar_para_copia, importar_bb
from _scripts import CasoDeScript

importar_bb()
from bb import checksums, package  # noqa: E402

BB = os.path.join("{raiz}", ".bigbang", "bin", "bb.py")
NOVA = "99.0.0"
PROJETO = {"PRODUTO.md": "# Produto\n", "src/app.py": "print('oi')\n", "docs/memoria.md": "# Memória\n",
           ".agents/skills/minha-skill/SKILL.md": "---\nname: minha-skill\n---\n",
           ".github/workflows/meu.yml": "name: meu\npermissions: {}\non: push\n"}
SECAO = """## [{versao}] - 2026-12-01

### O que muda

- A skill bb-status ganhou uma linha.

### O que o projeto precisa fazer

{passos}

"""


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


def git(pasta, *args):
    return subprocess.run(["git", "-C", pasta, *args], capture_output=True, text=True, check=True).stdout.strip()


class Atualizar(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.projeto = os.path.join(self.pasta, "projeto")
        self.remoto = os.path.join(self.pasta, "remoto.git")
        shutil.copytree(BIGBANG, os.path.join(self.projeto, ".bigbang"), ignore=ignorar_para_copia())
        self.atual = ler(os.path.join(BIGBANG, "VERSION")).strip()
        toml = re.sub(r'(?m)^versao = "[^"]*"', f'versao = "{self.atual}"', exemplo_toml())
        self.escrever("bigbang.toml", toml)
        for caminho, texto in PROJETO.items():
            self.escrever(caminho, texto)
        self.escrever(".bigbang/README.md", "# README do framework movido pelo bb init\n")
        self.bb("gerar", "--esteira")
        subprocess.run(["git", "init", "-q", "--bare", self.remoto], check=True)
        git(self.projeto, "init", "-q", "-b", "develop")
        git(self.projeto, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(self.projeto, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "inicio")
        git(self.projeto, "remote", "add", "origin", self.remoto)
        git(self.projeto, "push", "-q", "origin", "develop")
        git(self.projeto, "config", "user.name", "t")
        git(self.projeto, "config", "user.email", "t@t")

    def escrever(self, caminho, texto):
        destino = os.path.join(self.projeto, *caminho.split("/"))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    def bb(self, *args):
        ambiente = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"],
                    "FAKE_GH_STATE": self.estado_arquivo, "FAKE_GH_LOG": self.log}
        r = subprocess.run([sys.executable, BB.format(raiz=self.projeto), "--raiz", self.projeto, *args],
                           capture_output=True, text=True, env=ambiente, check=False)
        self.ler_estado()
        return r

    def publicar_versao(self, passos="Nada.", estragar_hash=False):
        """A newer framework release in the fake GitHub: the package of a changed copy of .bigbang/."""
        raiz = os.path.join(self.pasta, "framework-novo")
        shutil.copytree(BIGBANG, os.path.join(raiz, ".bigbang"), ignore=ignorar_para_copia())
        nova = os.path.join(raiz, ".bigbang")
        with open(os.path.join(nova, "VERSION"), "w", encoding="utf-8") as arquivo:
            arquivo.write(NOVA + "\n")
        migracao = os.path.join(nova, "MIGRACAO.md")
        texto = ler(migracao)
        marca = texto.index("## [")
        with open(migracao, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto[:marca] + SECAO.format(versao=NOVA, passos=passos) + texto[marca:])
        skill = os.path.join(nova, "skills", "bb-status", "SKILL.md")
        with open(skill, "a", encoding="utf-8") as arquivo:
            arquivo.write("\nLinha nova da versão nova.\n")
        exemplo = os.path.join(nova, "modelos", "bigbang.toml.exemplo")
        texto = ler(exemplo)
        with open(exemplo, "w", encoding="utf-8") as arquivo:
            arquivo.write(re.sub(r'(?m)^versao = "[^"]*"', f'versao = "{NOVA}"', texto))
        checksums.write(raiz)
        saida = os.path.join(self.pasta, "release")
        alvo, _ = package.build(raiz, saida)
        if estragar_hash:
            with open(alvo + ".sha256", "w", encoding="utf-8") as arquivo:
                arquivo.write("0" * 64 + "  " + os.path.basename(alvo) + "\n")
        self.estado.setdefault("releases", []).append(f"v{NOVA}")
        self.estado.setdefault("release_dirs", {})[f"v{NOVA}"] = saida
        self.gravar_estado()

    def projeto_intacto(self, branch):
        mudados = git(self.projeto, "diff", "--name-only", f"origin/develop..{branch}").splitlines()
        for caminho in mudados:
            gerado = (caminho.startswith((".bigbang/", ".agents/skills/bb-", ".claude/", ".github/bb-"))
                      or re.match(r"^\.github/(workflows/bb-|ISSUE_TEMPLATE/|dependabot|pull_request_template)",
                                  caminho) or caminho in ("AGENTS.md", "bigbang.toml"))
            self.assertTrue(gerado, f"a atualização mexeu na camada do projeto: {caminho}")
        diff_toml = git(self.projeto, "diff", f"origin/develop..{branch}", "--", "bigbang.toml")
        trocadas = [linha for linha in diff_toml.splitlines() if re.match(r"^[-+][^-+]", linha)]
        self.assertEqual(trocadas, [f'-versao = "{self.atual}"' + trocadas[0].split('"', 2)[2],
                                    f'+versao = "{NOVA}"' + trocadas[1].split('"', 2)[2]])
        return mudados

    def test_atualiza_sem_tocar_a_camada_do_projeto(self):
        self.publicar_versao()
        r = self.bb("atualizar")  # no version: the latest release of the origin
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        branch = f"framework/v{NOVA}"
        self.assertIn(branch, git(self.remoto, "branch", "--list"))
        mudados = self.projeto_intacto(branch)
        self.assertIn(".bigbang/VERSION", mudados)
        self.assertIn(".agents/skills/bb-status/SKILL.md", mudados)  # generated layer regenerated
        self.assertIn(".claude/skills/bb-status/SKILL.md", mudados)
        self.assertNotIn(".bigbang/README.md", mudados)  # moved in by bb init: kept
        pr = next(iter(self.estado["prs"].values()))
        self.assertEqual((pr["base"], pr["head"]), ("develop", branch))
        self.assertIn("revisao-humana", pr["labels"])
        criar = [c for c in self.chamadas() if c[:3] == ["label", "create", "revisao-humana"]]
        self.assertTrue(criar)  # before F4 the label does not exist yet (found by the pilot)
        self.assertLess(self.chamadas().index(criar[0]),
                        next(i for i, c in enumerate(self.chamadas()) if c[:2] == ["pr", "create"]))
        self.assertIn(f"## [{NOVA}]", pr["body"])
        self.assertEqual(self.bb("verificar").returncode, 0)

    def test_hash_errado_recusa_sem_mexer(self):
        self.publicar_versao(estragar_hash=True)
        r = self.bb("atualizar", NOVA)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("SHA-256", r.stderr)
        self.assertEqual(git(self.projeto, "status", "--porcelain"), "")
        self.assertEqual(git(self.projeto, "branch", "--show-current"), "develop")

    def test_atestacao_que_nao_confere_recusa(self):
        self.publicar_versao()
        self.estado["atestacao_falha"] = True
        self.gravar_estado()
        r = self.bb("atualizar", NOVA)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("atestação", r.stderr)
        self.assertNotIn("prs", self.estado)

    def test_passo_manual_exige_confirmacao_do_dono(self):
        self.publicar_versao(passos="Renomeie a chave `a` para `b` no bigbang.toml.")
        r = self.bb("atualizar", NOVA)
        self.assertEqual(r.returncode, 7, r.stdout + r.stderr)
        self.assertIn("Renomeie", r.stdout)
        self.assertEqual(git(self.projeto, "branch", "--show-current"), "develop")
        r = self.bb("atualizar", NOVA, "--confirmo-migracao")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("- [ ] ", next(iter(self.estado["prs"].values()))["body"])

    def test_simular_nao_grava(self):
        self.publicar_versao()
        r = self.bb("atualizar", NOVA, "--simular")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Simulação", r.stdout)
        self.assertEqual(git(self.projeto, "status", "--porcelain"), "")
        self.assertEqual(git(self.remoto, "branch", "--list").split(), ["develop"])

    def test_mesma_versao_nao_faz_nada(self):
        r = self.bb("atualizar", self.atual)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nada a atualizar", r.stdout)

    def test_arvore_suja_recusa(self):
        self.publicar_versao()
        self.escrever("src/app.py", "mudado\n")
        r = self.bb("atualizar", NOVA)
        self.assertEqual(r.returncode, 7, r.stdout + r.stderr)
