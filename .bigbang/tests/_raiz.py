"""Shared paths for the framework tests."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIGBANG = os.path.join(RAIZ, ".bigbang")


def caminho(*partes):
    return os.path.join(RAIZ, *partes)


def ler(*partes):
    with open(caminho(*partes), encoding="utf-8") as arquivo:
        return arquivo.read()


def arquivos_markdown():
    """Yield every Markdown file tracked in the repository tree (skipping .git)."""
    for pasta, subpastas, nomes in os.walk(RAIZ):
        subpastas[:] = [s for s in subpastas if s != ".git"]
        for nome in sorted(nomes):
            if nome.endswith(".md"):
                yield os.path.join(pasta, nome)


def importar_bb():
    """Make the `bb` package (in .bigbang/) importable by the tests."""
    import sys
    if BIGBANG not in sys.path:
        sys.path.insert(0, BIGBANG)


def exemplo_toml():
    with open(os.path.join(BIGBANG, "modelos", "bigbang.toml.exemplo"), encoding="utf-8") as arquivo:
        return arquivo.read()
