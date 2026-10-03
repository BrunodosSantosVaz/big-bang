"""Command-line interface of the Big Bang (`bb`). Messages in Portuguese; stable exit codes in errors.py."""
import argparse
import sys

from . import config as config_module
from .errors import EXIT_OK, EXIT_UNEXPECTED, EXIT_USAGE, BbError
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

    return parser


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
