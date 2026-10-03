"""bigbang.toml schema and `bb config get` (spec 5.4 and 14.6)."""
import contextlib
import copy
import io
import os
import tempfile
import unittest

from _raiz import exemplo_toml, importar_bb

importar_bb()
from bb import cli, config  # noqa: E402
from bb.errors import EXIT_INVALID_CONFIG, EXIT_UNKNOWN_KEY, EXIT_USAGE, BbError  # noqa: E402


def exemplo():
    return config.parse(exemplo_toml())


def compilado():
    cfg = exemplo()
    cfg["entrega"].update(perfil="compilado", alvo="")
    del cfg["deploy"]
    return cfg


class Esquema(unittest.TestCase):
    def test_exemplo_valido(self):
        cfg = exemplo()
        self.assertEqual(config.validate(cfg, cfg["bigbang"]["versao"]), [])

    def test_compilado_valido_sem_secao_deploy(self):
        self.assertEqual(config.validate(compilado()), [])

    def test_recusa_chave_e_secao_desconhecidas(self):
        cfg = exemplo()
        cfg["projeto"]["nomee"] = "x"
        cfg["extra"] = {}
        erros = config.validate(cfg)
        self.assertIn("chave desconhecida: projeto.nomee", erros)
        self.assertIn("seção desconhecida [extra]", erros)

    def test_recusa_chave_obrigatoria_ausente(self):
        cfg = exemplo()
        del cfg["ias"]["nomes"]
        self.assertIn("chave obrigatória ausente: ias.nomes", config.validate(cfg))

    def test_secao_do_perfil_ativo_e_obrigatoria(self):
        cfg = exemplo()
        del cfg["deploy"]
        self.assertIn("seção obrigatória ausente: [deploy]", config.validate(cfg))
        cfg = compilado()
        del cfg["compilado"]
        self.assertIn("seção obrigatória ausente: [compilado]", config.validate(cfg))

    def test_build_de_cada_sistema(self):
        cfg = compilado()
        cfg["compilado"]["sistemas"].append("macos-arm64")
        self.assertIn("[compilado] falta build_macos-arm64 (comando de build de cada sistema)", config.validate(cfg))
        cfg["compilado"]["sistemas"] = ["solaris"]
        self.assertTrue(any("solaris" in e for e in config.validate(cfg)))

    def test_alvo_conforme_o_perfil(self):
        cfg = exemplo()
        cfg["entrega"]["alvo"] = "heroku"
        self.assertTrue(any(e.startswith("entrega.alvo") for e in config.validate(cfg)))
        cfg = compilado()
        cfg["entrega"]["alvo"] = "aws"
        self.assertIn('entrega.alvo: no perfil compilado deve ser ""', config.validate(cfg))

    def test_publico_exige_licenca(self):
        cfg = exemplo()
        cfg["projeto"]["visibilidade"] = "publico"
        self.assertTrue(any(e.startswith("projeto.licenca") for e in config.validate(cfg)))
        cfg["projeto"]["licenca"] = "MIT"
        self.assertEqual(config.validate(cfg), [])

    def test_tipos(self):
        casos = [("testes", "cobertura_minima", "80"), ("testes", "cobertura_minima", 101),
                 ("seguranca", "banco_no_navegador", "false"), ("ias", "tarefas_por_ia", 0),
                 ("projeto", "slug", "Meu Sistema"), ("deploy", "url_producao", "http://x.com"),
                 ("testes", "padrao_teste", "(it|test"), ("ias", "nomes", ["claude-1", "claude-1"]),
                 ("paineis", "bugs", True)]
        for secao, chave, valor in casos:
            with self.subTest(chave=f"{secao}.{chave}", valor=valor):
                cfg = copy.deepcopy(exemplo())
                cfg[secao][chave] = valor
                self.assertTrue(any(e.startswith(f"{secao}.{chave}") for e in config.validate(cfg)))

    def test_versao_igual_ao_framework(self):
        erros = config.validate(exemplo(), "9.9.9")
        self.assertTrue(any("bigbang.versao" in e for e in erros))

    def test_repositorio_do_dono(self):
        cfg = exemplo()
        cfg["projeto"]["repositorio"] = "outra-pessoa/meu-sistema"
        self.assertIn("projeto.repositorio: deve pertencer ao projeto.dono", config.validate(cfg))


class ConfigGet(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = self.pasta.name
        os.makedirs(os.path.join(self.raiz, ".bigbang"))
        versao = exemplo()["bigbang"]["versao"]
        with open(os.path.join(self.raiz, ".bigbang", "VERSION"), "w", encoding="utf-8") as arquivo:
            arquivo.write(versao + "\n")
        with open(os.path.join(self.raiz, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(exemplo_toml())

    def tearDown(self):
        self.pasta.cleanup()

    def rodar(self, *argv):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = cli.main(["--raiz", self.raiz, *argv])
        return codigo, saida.getvalue(), erro.getvalue()

    def test_valores(self):
        self.assertEqual(self.rodar("config", "get", "projeto.slug"), (0, "meu-sistema\n", ""))
        self.assertEqual(self.rodar("config", "get", "seguranca.banco_no_navegador")[1], "false\n")
        self.assertEqual(self.rodar("config", "get", "testes.cobertura_minima")[1], "80\n")
        self.assertEqual(self.rodar("config", "get", "ias.nomes")[1], "claude-1\nclaude-2\ncodex-1\n")
        self.assertEqual(self.rodar("config", "get", "compilado.build_windows-x64")[1],
                         "python packaging/windows/build.py\n")

    def test_codigos_de_saida(self):
        self.assertEqual(self.rodar("config", "get", "projeto.inexistente")[0], EXIT_UNKNOWN_KEY)
        self.assertEqual(self.rodar("config", "get", "projeto")[0], EXIT_UNKNOWN_KEY)
        self.assertEqual(self.rodar("comando-que-nao-existe")[0], EXIT_USAGE)
        os.remove(os.path.join(self.raiz, "bigbang.toml"))
        self.assertEqual(self.rodar("config", "get", "projeto.slug")[0], EXIT_INVALID_CONFIG)

    def test_config_invalida(self):
        with open(os.path.join(self.raiz, "bigbang.toml"), "a", encoding="utf-8") as arquivo:
            arquivo.write("\n[extra]\nx = 1\n")
        codigo, _, erro = self.rodar("config", "get", "projeto.slug")
        self.assertEqual(codigo, EXIT_INVALID_CONFIG)
        self.assertIn("seção desconhecida [extra]", erro)

    def test_toml_quebrado(self):
        with self.assertRaises(BbError) as contexto:
            config.parse("[projeto\n")
        self.assertEqual(contexto.exception.code, EXIT_INVALID_CONFIG)


if __name__ == "__main__":
    unittest.main()
