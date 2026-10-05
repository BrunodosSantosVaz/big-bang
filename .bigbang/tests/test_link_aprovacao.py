"""link-aprovacao.sh (#153): whoever starts a real publication hands the human the run link and the approval steps."""
import os
import unittest

from _raiz import BIGBANG
from _scripts import CasoDeScript

WORKFLOWS = {
    "bb-publicar-producao.yml.tmpl": os.path.join(BIGBANG, "esteira", "nucleo", "arquivos", ".github", "workflows"),
    "bb-publicar-sem-release.yml": os.path.join(BIGBANG, "esteira", "nucleo", "arquivos", ".github", "workflows"),
    "bb-voltar-versao.yml.tmpl": os.path.join(BIGBANG, "esteira", "perfis", "deploy", "arquivos", ".github",
                                              "workflows"),
}
PASSOS = ("Review deployments", "producao", "Approve and deploy", "Reject")


class LinkAprovacao(CasoDeScript):
    def link(self, *args, **env):
        return self.rodar("link-aprovacao.sh", *args, env={k: str(v) for k, v in env.items()})

    def test_run_aguardando_vira_link_e_passos(self):
        url = "https://github.com/dono/repo/actions/runs/123"
        self.estado["comandos"] = {"run list": f"{url}\tPublicar em produção\n"}
        self.gravar_estado()
        r = self.link("bb-publicar-producao.yml", "Publicar em produção v1.2.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"Link: {url}", r.stdout)
        self.assertIn("Aprovação pendente: Publicar em produção v1.2.0", r.stdout)
        for passo in PASSOS:
            self.assertIn(passo, r.stdout)
        chamada = next(c for c in self.chamadas() if c[:2] == ["run", "list"])
        self.assertIn("--status", chamada)
        self.assertEqual(chamada[chamada.index("--status") + 1], "waiting")

    def test_sem_run_aguardando_avisa_com_o_link_da_lista(self):
        self.estado["comandos"] = {"run list": ""}
        self.gravar_estado()
        r = self.link("bb-publicar-sem-release.yml", APROVACAO_ESPERA=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Nenhum run de bb-publicar-sem-release.yml", r.stdout)
        self.assertIn("https://github.com/dono/repo/actions/workflows/bb-publicar-sem-release.yml", r.stdout)

    def test_resumo_do_run_usa_o_proprio_link(self):
        resumo = os.path.join(self.pasta, "resumo.md")
        r = self.link("--resumo", "Voltar produção para v1.1.0", GITHUB_RUN_ID=987, GITHUB_STEP_SUMMARY=resumo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(resumo, encoding="utf-8") as arquivo:
            texto = arquivo.read()
        self.assertIn("Link: https://github.com/dono/repo/actions/runs/987", texto)
        for passo in PASSOS:
            self.assertIn(passo, texto)
        self.assertFalse(self.chamadas())  # no API call: the link is the current run


class WorkflowsDePublicacao(unittest.TestCase):
    def test_conferir_deixa_as_instrucoes_quando_e_de_verdade(self):
        for nome, pasta in WORKFLOWS.items():
            with self.subTest(workflow=nome):
                with open(os.path.join(pasta, nome), encoding="utf-8") as arquivo:
                    texto = arquivo.read()
                conferir = texto.split("\n  conferir:\n", 1)[1].split("\n\n  ", 1)[0]
                self.assertIn("link-aprovacao.sh --resumo", conferir)
                passo = conferir.split("link-aprovacao.sh --resumo", 1)[0].rsplit("- name:", 1)[1]
                self.assertIn("if: ${{ !inputs.simular }}", passo)


if __name__ == "__main__":
    unittest.main()
