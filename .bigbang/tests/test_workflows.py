"""Rules for the framework's own workflows (spec 14.1 and SEG-18; ADR-0006)."""
import os
import re
import unittest

from _raiz import caminho

WORKFLOWS = caminho(".github", "workflows")
REPOSITORIO = "BrunodosSantosVaz/big-bang"
GUARDA = f"if: github.repository == '{REPOSITORIO}'"

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$", re.M)
FIXADA = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
COMENTARIO_VERSAO = re.compile(r"^\s*#\s*v\d+(\.\d+){0,2}\s*$")
RUNS_ON = re.compile(r"^\s*runs-on:\s*(\S+)\s*$", re.M)
JOB = re.compile(r"^  ([\w-]+):\s*$", re.M)


def workflows():
    for nome in sorted(os.listdir(WORKFLOWS)):
        if nome.endswith((".yml", ".yaml")):
            with open(os.path.join(WORKFLOWS, nome), encoding="utf-8") as arquivo:
                yield nome, arquivo.read()


def jobs(texto):
    """Split the `jobs:` section into {job_id: body} using two-space indentation."""
    secao = texto.split("\njobs:\n", 1)[1]
    marcas = list(JOB.finditer(secao))
    for atual, proxima in zip(marcas, marcas[1:] + [None]):
        fim = proxima.start() if proxima else len(secao)
        yield atual.group(1), secao[atual.end():fim]


class RegrasDosWorkflows(unittest.TestCase):
    def test_existe_a_ci_do_framework(self):
        self.assertIn("bb-framework-ci.yml", dict(workflows()))

    def test_nome_com_prefixo_bb(self):
        for nome, _ in workflows():
            with self.subTest(workflow=nome):
                self.assertTrue(nome.startswith("bb-"))

    def test_actions_fixadas_por_sha_com_versao_em_comentario(self):
        for nome, texto in workflows():
            for acao, resto in USES.findall(texto):
                with self.subTest(workflow=nome, uses=acao):
                    self.assertRegex(acao, FIXADA)
                    self.assertRegex(resto, COMENTARIO_VERSAO)

    def test_runner_em_versao_fixa(self):
        for nome, texto in workflows():
            for runner in RUNS_ON.findall(texto):
                with self.subTest(workflow=nome, runner=runner):
                    self.assertNotIn("latest", runner)
                    self.assertRegex(runner, r"^(ubuntu|windows|macos)-\d")

    def test_permissoes_minimas_no_topo(self):
        for nome, texto in workflows():
            with self.subTest(workflow=nome):
                self.assertRegex(texto, r"(?m)^permissions:\s*$|^permissions:\s*\{\}\s*$")
                self.assertNotRegex(texto, r"(?m)^permissions:\s*write-all")

    def test_sem_pull_request_target(self):
        for nome, texto in workflows():
            with self.subTest(workflow=nome):
                self.assertNotIn("pull_request_target", texto)

    def test_concorrencia_sem_cancelar(self):
        for nome, texto in workflows():
            with self.subTest(workflow=nome):
                self.assertRegex(texto, r"(?m)^concurrency:")
                self.assertNotRegex(texto, r"cancel-in-progress:\s*true")

    def test_jobs_do_framework_so_rodam_no_repositorio_do_big_bang(self):
        for nome, texto in workflows():
            if not nome.startswith("bb-framework-"):
                continue
            for job, corpo in jobs(texto):
                with self.subTest(workflow=nome, job=job):
                    self.assertIn(GUARDA, corpo)


class AutoTesteDasRegras(unittest.TestCase):
    """The rules must refuse the wrong case and accept the right one."""

    def test_recusa_tag_e_aceita_sha(self):
        self.assertNotRegex("actions/checkout@v5", FIXADA)
        self.assertNotRegex("actions/checkout@main", FIXADA)
        self.assertRegex("actions/checkout@" + "a" * 40, FIXADA)
        self.assertRegex("github/codeql-action/init@" + "0" * 40, FIXADA)

    def test_comentario_de_versao(self):
        self.assertRegex(" # v7.0.1", COMENTARIO_VERSAO)
        self.assertNotRegex("", COMENTARIO_VERSAO)
        self.assertNotRegex(" # main", COMENTARIO_VERSAO)

    def test_separa_jobs(self):
        texto = "name: x\n\njobs:\n  um:\n    if: a\n    runs-on: b\n  dois:\n    runs-on: c\n"
        self.assertEqual([j for j, _ in jobs(texto)], ["um", "dois"])
        self.assertNotIn(GUARDA, dict(jobs(texto))["dois"])


if __name__ == "__main__":
    unittest.main()
