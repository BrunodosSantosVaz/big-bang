"""Command-line interface of the Big Bang (`bb`). Messages in Portuguese; stable exit codes in errors.py."""
import argparse
import sys

from . import config as config_module
from . import checksums, generator, verify
from .errors import EXIT_OK, EXIT_UNEXPECTED, EXIT_USAGE, EXIT_VERIFICATION_FAILED, BbError
from .paths import default_root


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        raise BbError(f"uso inválido: {message}", EXIT_USAGE)


def build_parser():
    parser = _Parser(prog="bb", description="Big Bang: ferramentas do framework.")
    parser.add_argument("--raiz", default=None, help="raiz do projeto (padrão: a pasta acima de .bigbang/)")
    commands = parser.add_subparsers(dest="command", metavar="<comando>", parser_class=_Parser)

    config_parser = commands.add_parser("config", help="lê o bigbang.toml")
    config_commands = config_parser.add_subparsers(dest="config_command", metavar="<subcomando>",
                                                   parser_class=_Parser)
    get_parser = config_commands.add_parser("get", help="mostra o valor de uma chave (secao.chave)")
    get_parser.add_argument("chave")
    get_parser.set_defaults(handler=_config_get)

    gerar_parser = commands.add_parser("gerar", help="gera a camada gerada a partir de .bigbang/ e do bigbang.toml")
    gerar_parser.add_argument("--simular", action="store_true", help="só mostra o que mudaria (diff), sem gravar")
    gerar_parser.add_argument("--esteira", action="store_true",
                              help="instala a esteira (.github/) pela primeira vez (Fundação F5)")
    gerar_parser.set_defaults(handler=_gerar)

    verificar_parser = commands.add_parser("verificar", help="confere framework, arquivos gerados e workflows")
    verificar_parser.set_defaults(handler=_verificar)

    checksums_parser = commands.add_parser("checksums", help="confere ou grava .bigbang/CHECKSUMS (manutenção)")
    checksums_parser.add_argument("--escrever", action="store_true", help="grava o CHECKSUMS com o estado atual")
    checksums_parser.set_defaults(handler=_checksums)

    return parser


def _verificar(args):
    found = verify.run(args.raiz)
    if found:
        print(f"bb verificar: {len(found)} problema(s):", file=sys.stderr)
        for problem in found:
            print(f"  - {problem}", file=sys.stderr)
        return EXIT_VERIFICATION_FAILED
    print("bb verificar: tudo certo.")
    return EXIT_OK


def _checksums(args):
    if args.escrever:
        print(f".bigbang/CHECKSUMS gravado ({checksums.write(args.raiz)} arquivos).")
        return EXIT_OK
    found = checksums.problems(args.raiz)
    for problem in found:
        print(f"  - {problem}", file=sys.stderr)
    return EXIT_VERIFICATION_FAILED if found else EXIT_OK


def _gerar(args):
    plan = generator.build_plan(args.raiz, install_pipeline=args.esteira)
    pending = generator.changes(plan, args.raiz)
    if not pending:
        print("Camada gerada em dia: nada a mudar.")
        return EXIT_OK
    if args.simular:
        for kind, path in pending:
            print(f"{kind}: {path}")
        for kind, path in pending:
            if kind != "remover":
                print(generator.diff(plan, args.raiz, path), end="")
        print(f"Simulação: {len(pending)} arquivo(s) mudariam. Nada foi gravado.")
        return EXIT_OK
    for kind, path in generator.apply(plan, args.raiz):
        print(f"{kind}: {path}")
    print(f"{len(pending)} arquivo(s) atualizados. Rode bb verificar e revise o diff num PR.")
    return EXIT_OK


def _config_get(args):
    value = config_module.get(config_module.load(args.raiz), args.chave)
    print(config_module.format_value(value))
    return EXIT_OK


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if not hasattr(args, "handler"):
            parser.print_help(sys.stderr)
            return EXIT_USAGE
        args.raiz = args.raiz or default_root()
        return args.handler(args)
    except BbError as exc:
        print(f"bb: {exc.message}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return EXIT_UNEXPECTED
