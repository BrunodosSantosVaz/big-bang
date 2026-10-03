"""Example scenarios of spec E3: a project made from the template, founded with each scenario's bigbang.toml and
with the STACK.md model, then generated with the pipeline installed. Expected outputs live in esperado/<cenario>/."""
import os
import shutil

from _raiz import BIGBANG, RAIZ, ignorar_para_copia, importar_bb

importar_bb()
from bb import checksums, generator  # noqa: E402
from bb.init import set_value  # noqa: E402
from bb.paths import framework_version  # noqa: E402

CENARIOS = os.path.join(BIGBANG, "tests", "cenarios")
ESPERADO = os.path.join(BIGBANG, "tests", "esperado")
NOMES = ("deploy-vps-docker", "compilado-windows-linux")
IGNORAR = ignorar_para_copia("bigbang.toml", "STACK.md")


def montar(cenario, destino):
    """Create the scenario project in `destino` and return the plan of its generated layer."""
    shutil.copytree(RAIZ, destino, ignore=IGNORAR)
    checksums.write(destino)
    with open(os.path.join(CENARIOS, f"{cenario}.toml"), encoding="utf-8") as arquivo:
        texto = set_value(arquivo.read(), "bigbang", "versao", framework_version(destino))
    with open(os.path.join(destino, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    shutil.copy(os.path.join(destino, ".bigbang", "modelos", "STACK.md"), os.path.join(destino, "STACK.md"))
    return generator.build_plan(destino, install_pipeline=True)


def esperado(cenario):
    pasta = os.path.join(ESPERADO, cenario)
    resultado = {}
    for atual, _, nomes in os.walk(pasta):
        for nome in nomes:
            caminho = os.path.join(atual, nome)
            with open(caminho, encoding="utf-8", newline="") as arquivo:
                resultado[os.path.relpath(caminho, pasta).replace(os.sep, "/")] = arquivo.read().replace("\r\n", "\n")
    return resultado
