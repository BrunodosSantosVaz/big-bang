"""Regenerate esperado/<cenario>/ after a deliberate change to templates or to the version.

Usage: python .bigbang/tests/atualizar_esperado.py — then review the diff of esperado/ in the PR.
"""
import os
import shutil
import tempfile

from _cenarios import ESPERADO, NOMES, montar


def main():
    for cenario in NOMES:
        with tempfile.TemporaryDirectory() as pasta:
            plano = montar(cenario, os.path.join(pasta, "projeto"))
        destino = os.path.join(ESPERADO, cenario)
        shutil.rmtree(destino, ignore_errors=True)
        for caminho, conteudo in plano.expected.items():
            arquivo = os.path.join(destino, *caminho.split("/"))
            os.makedirs(os.path.dirname(arquivo), exist_ok=True)
            with open(arquivo, "w", encoding="utf-8", newline="\n") as saida:
                saida.write(conteudo)
        print(f"{cenario}: {len(plano.expected)} arquivos")


if __name__ == "__main__":
    main()
