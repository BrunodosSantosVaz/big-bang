"""`bb esteira <subcomando>`: the pipeline rules for the Bash scripts (input on stdin, plain-text output).

These are building blocks for the generated workflows, not commands the owner types.
"""
import datetime
import os
import sys

from . import config as config_module
from . import docs_check, pipeline
from .errors import EXIT_OK, EXIT_USAGE, EXIT_VERIFICATION_FAILED, BbError
from .paths import read_text, write_text


def register(commands, parser_class):
    esteira = commands.add_parser("esteira", help="regras da esteira para os scripts (uso interno)")
    sub = esteira.add_subparsers(dest="esteira_command", metavar="<subcomando>", parser_class=parser_class)

    p = sub.add_parser("formulario", help="labels do formulário do épico (corpo na entrada padrão): +label/-label")
    p.add_argument("--antes", help="arquivo com o corpo anterior (evento edited): só aplica respostas que mudaram")
    p.set_defaults(handler=_form)

    p = sub.add_parser("pronto", help="Definition of Ready do épico (corpo na entrada padrão)")
    p.add_argument("--labels", default="", help="labels do épico, separadas por vírgula")
    p.set_defaults(handler=_ready)

    sub.add_parser("severidade", help="label de severidade do formulário de bug (corpo na entrada padrão)").set_defaults(
        handler=_severity)
    sub.add_parser("tarefas", help="tarefas previstas: <índice>\\t<título>\\t<dependências>").set_defaults(
        handler=_tasks)
    sub.add_parser("dependencias", help="épicos dos quais este depende (um número por linha)").set_defaults(
        handler=_dependencies)

    p = sub.add_parser("branch", help="nome da branch de uma issue")
    p.add_argument("tipo")
    p.add_argument("numero", type=int)
    p.add_argument("titulo")
    p.set_defaults(handler=_branch)

    p = sub.add_parser("regra-branch", help="confere origem e destino de um PR")
    p.add_argument("head")
    p.add_argument("base")
    p.set_defaults(handler=_branch_rule)

    p = sub.add_parser("titulo", help="confere o título do PR (Conventional Commits)")
    p.add_argument("titulo")
    p.set_defaults(handler=_title)

    p = sub.add_parser("versao", help="próxima versão a partir dos títulos dos PRs (entrada padrão)")
    p.add_argument("--atual", required=True)
    p.set_defaults(handler=_version)

    p = sub.add_parser("changelog", help="grava a seção da versão no CHANGELOG.md (itens: número\\ttítulo\\tlabels)")
    p.add_argument("--versao", required=True)
    p.add_argument("--data", default=None)
    p.add_argument("--arquivo", default="CHANGELOG.md")
    p.set_defaults(handler=_changelog)

    p = sub.add_parser("artefato", help="dos caminhos na entrada padrão, imprime os do artefato")
    p.set_defaults(handler=_artifact)

    p = sub.add_parser("sensivel", help="dos caminhos na entrada padrão, imprime os de zona sensível")
    p.add_argument("--pr-de-teste", action="store_true", help="PR de teste do épico: tests/aceite/ liberado")
    p.set_defaults(handler=_sensitive)

    p = sub.add_parser("documentacao", help="Markdown válido e links relativos do projeto (DOC-14)")
    p.set_defaults(handler=_docs)

    p = sub.add_parser("so-liberacao", help="o diff (entrada padrão) em tests/aceite/ só retira marcas da issue?")
    p.add_argument("issue", type=int)
    p.set_defaults(handler=_only_release)

    p = sub.add_parser("gravar-versao", help="grava a versão no arquivo de versão da stack (entrega.arquivo_versao)")
    p.add_argument("versao")
    p.set_defaults(handler=_write_version)


def _stdin():
    return sys.stdin.read()


def _lines():
    return [line.strip() for line in _stdin().splitlines() if line.strip()]


def _form(args):
    previous = read_text(args.antes) if args.antes else None
    add, remove = pipeline.form_label_changes(_stdin(), previous)
    for label in sorted(add):
        print(f"+{label}")
    for label in sorted(remove):
        print(f"-{label}")
    return EXIT_OK


def _ready(args):
    labels = [label for label in args.labels.split(",") if label]
    problems = pipeline.readiness_problems(_stdin(), labels)
    for problem in problems:
        print(problem)
    return EXIT_VERIFICATION_FAILED if problems else EXIT_OK


def _severity(args):
    label = pipeline.severity_label(_stdin())
    if label:
        print(label)
    return EXIT_OK


def _tasks(args):
    for index, (title, deps) in enumerate(pipeline.planned_tasks(_stdin()), start=1):
        print(f"{index}\t{title}\t{','.join(str(d) for d in deps)}")
    return EXIT_OK


def _dependencies(args):
    for number in pipeline.dependencies(_stdin()):
        print(number)
    return EXIT_OK


def _branch(args):
    print(pipeline.branch_name(args.tipo, args.numero, args.titulo))
    return EXIT_OK


def _branch_rule(args):
    problem = pipeline.branch_problem(args.head, args.base)
    if problem:
        print(problem)
        return EXIT_VERIFICATION_FAILED
    return EXIT_OK


def _title(args):
    problem = pipeline.title_problem(args.titulo)
    if problem:
        print(problem)
        return EXIT_VERIFICATION_FAILED
    return EXIT_OK


def _version(args):
    try:
        print(pipeline.next_version(args.atual, _lines()))
    except ValueError as exc:
        raise BbError(str(exc), EXIT_USAGE) from exc
    return EXIT_OK


def _changelog(args):
    items = []
    for line in _lines():
        number, title, labels = (line.split("\t") + ["", ""])[:3]
        items.append((number, title, [label for label in labels.split(",") if label]))
    path = os.path.join(args.raiz, args.arquivo)
    current = read_text(path) if os.path.exists(path) else None
    date = args.data or datetime.date.today().isoformat()
    write_text(path, pipeline.changelog_with_release(current, args.versao, date, items))
    print(f"{args.arquivo}: seção {args.versao} gravada")
    return EXIT_OK


def _artifact(args):
    patterns = config_module.load(args.raiz)["entrega"]["caminhos_artefato"]
    for path in pipeline.artifact_paths(_lines(), patterns):
        print(path)
    return EXIT_OK


def _sensitive(args):
    zones = config_module.load(args.raiz)["seguranca"]["zonas_sensiveis"]
    for path in pipeline.sensitive_paths(_lines(), zones, acceptance_allowed=args.pr_de_teste):
        print(path)
    return EXIT_OK


def _only_release(args):
    marker = config_module.load(args.raiz)["testes"]["marca_pendente"]
    return EXIT_OK if pipeline.only_own_marks_released(_stdin(), args.issue, marker) else EXIT_VERIFICATION_FAILED


def _docs(args):
    problems = docs_check.problems(args.raiz)
    for problem in problems:
        print(problem)
    if not problems:
        print("Documentação: Markdown e links em ordem.")
    return EXIT_VERIFICATION_FAILED if problems else EXIT_OK


def _write_version(args):
    relative = config_module.load(args.raiz)["entrega"].get("arquivo_versao", "")
    if not relative:
        raise BbError("entrega.arquivo_versao não definido no bigbang.toml (definido em F2)", EXIT_USAGE)
    path = os.path.join(args.raiz, relative)
    try:
        write_text(path, pipeline.with_version(read_text(path), args.versao))
    except (OSError, ValueError) as exc:
        raise BbError(f"{relative}: {exc}", EXIT_USAGE) from exc
    print(f"{relative}: versão {args.versao}")
    return EXIT_OK
