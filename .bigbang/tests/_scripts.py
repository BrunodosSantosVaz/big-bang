"""Harness for the pipeline Bash scripts: a temp dir with the fake gh first in PATH, its state and its call log."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from _raiz import BIGBANG

SCRIPTS = os.path.join(BIGBANG, "esteira", "nucleo", "scripts")
SETUP = os.path.join(BIGBANG, "scripts")
GH_FALSO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_gh_falso.py")
USAVEL = os.name != "nt" and bool(shutil.which("bash")) and bool(shutil.which("jq"))
MOTIVO = "bash e jq indisponíveis (os scripts rodam no Linux das Actions)"

STATUS_EXECUCAO = ["A fazer", "Feature", "Code", "CI/PR", "Validar PR", "Pronto", "Concluído"]
STATUS_PLANEJAMENTO = ["Brainstorm", "Backlog", "Backlog Refinement", "Validar protótipo", "Próxima sprint",
                       "Em desenvolvimento", "Homologação", "Concluída"]
STATUS_BUGS = ["Novo", "Em correção", "CI/PR", "Validar PR", "Homologação", "Corrigido"]


def painel(numero, colunas, sprints=("Sem sprint",)):
    def opcoes(prefixo, nomes):
        return [{"id": f"{prefixo}{numero}-{i}", "name": nome} for i, nome in enumerate(nomes)]
    return {"fields": {"Status": {"id": f"FS{numero}", "options": opcoes("OS", colunas)},
                       "Sprint": {"id": f"FP{numero}", "options": opcoes("OP", sprints)},
                       "Épico": {"id": f"FE{numero}"}, "Versão": {"id": f"FV{numero}"}},
            "items": {}}


class CasoDeScript(unittest.TestCase):
    """Each test gets a fresh fake GitHub with the three boards (1 Planejamento, 2 Execução, 3 Bugs)."""

    def setUp(self):
        if not USAVEL:
            self.skipTest(MOTIVO)
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.bin = os.path.join(self.pasta, "bin")
        os.makedirs(self.bin)
        gh = os.path.join(self.bin, "gh")
        with open(gh, "w", encoding="utf-8") as arquivo:
            arquivo.write(f'#!/usr/bin/env bash\nexec "{sys.executable}" "{GH_FALSO}" "$@"\n')
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IXUSR)
        self.estado_arquivo = os.path.join(self.pasta, "estado.json")
        self.log = os.path.join(self.pasta, "gh.log")
        self.estado = {"boards": {"1": painel(1, STATUS_PLANEJAMENTO), "2": painel(2, STATUS_EXECUCAO),
                                  "3": painel(3, STATUS_BUGS)},
                       "issues": {}, "refs": {}, "pulls": [], "checks": {}}
        self.gravar_estado()

    def gravar_estado(self):
        with open(self.estado_arquivo, "w", encoding="utf-8") as arquivo:
            json.dump(self.estado, arquivo, ensure_ascii=False)

    def ler_estado(self):
        with open(self.estado_arquivo, encoding="utf-8") as arquivo:
            self.estado = json.load(arquivo)
        return self.estado

    def issue(self, numero, titulo="Issue", labels=(), corpo="", **extra):
        self.estado["issues"][str(numero)] = {"title": titulo, "labels": list(labels), "body": corpo,
                                              "state": "open", **extra}
        self.gravar_estado()

    def cartao(self, painel_numero, issue, status, **campos):
        self.estado["boards"][str(painel_numero)]["items"][str(issue)] = {"Status": status, **campos}
        self.gravar_estado()

    def status(self, painel_numero, issue):
        return self.ler_estado()["boards"][str(painel_numero)]["items"].get(str(issue), {}).get("Status")

    def chamadas(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as arquivo:
            return [json.loads(linha) for linha in arquivo]

    def rodar(self, script, *args, env=None, pasta=SCRIPTS, cwd=None):
        ambiente = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"],
                    "FAKE_GH_STATE": self.estado_arquivo, "FAKE_GH_LOG": self.log,
                    "GITHUB_REPOSITORY": "dono/repo", "PROJETO_OWNER": "dono",
                    "PROJETO_PLANEJAMENTO": "1", "PROJETO_EXECUCAO": "2", "PROJETO_BUGS": "3",
                    **(env or {})}
        resultado = subprocess.run(["bash", os.path.join(pasta, script), *args], capture_output=True, text=True,
                                   env=ambiente, cwd=cwd or self.pasta, check=False)
        self.ler_estado()
        return resultado
