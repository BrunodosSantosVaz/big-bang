"""Command-line interface of the Big Bang (`bb`). Messages in Portuguese; stable exit codes in errors.py."""
import argparse
import sys

from . import config as config_module
from . import acceptance, checklist, checksums, decisions, generator, ownership, status, verify, workspaces
from . import init as init_module
from . import pipeline_cli
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

    init_parser = commands.add_parser("init", help="Fundação F0: cria o bigbang.toml e liga o projeto ao GitHub")
    init_parser.add_argument("--nome", required=True, help="nome do sistema")
    init_parser.add_argument("--slug", help="identificador em minúsculas com hífen (padrão: a partir do nome)")
    init_parser.add_argument("--dono", help="login do GitHub do dono (padrão: o do repositório ou do gh)")
    init_parser.add_argument("--repositorio", help="dono/nome (padrão: o remote origin)")
    init_parser.add_argument("--visibilidade", choices=("privado", "publico"), default="privado")
    init_parser.add_argument("--licenca", default="", help="identificador SPDX (obrigatório se público)")
    init_parser.add_argument("--sem-github", action="store_true", help="não cria label nem issue no GitHub")
    init_parser.add_argument("--simular", action="store_true", help="só mostra o plano")
    init_parser.set_defaults(handler=_init)

    verificar_parser = commands.add_parser("verificar", help="confere framework, arquivos gerados e workflows")
    verificar_parser.set_defaults(handler=_verificar)

    assumir_parser = commands.add_parser("assumir", help="confirma a posse e abre uma pasta de trabalho própria")
    assumir_parser.add_argument("issue", type=int)
    assumir_parser.add_argument("nome")
    assumir_parser.add_argument("--forcar", action="store_true", help="retoma uma posse parada por ordem do dono")
    assumir_parser.add_argument("--frase", help="ordem do dono (obrigatória com --forcar)")
    assumir_parser.add_argument("--pasta", help="pasta própria do worktree (padrão: ../repo-nome)")
    assumir_parser.set_defaults(handler=_assumir)

    liberar_posse = commands.add_parser("liberar", help="libera a posse da sessão na pasta de trabalho atual")
    liberar_posse.add_argument("issue", type=int)
    liberar_posse.set_defaults(handler=_liberar)

    status_parser = commands.add_parser("status", help="resumo dos painéis, posses, flags e segurança (somente leitura)")
    status_parser.set_defaults(handler=_status)

    aceite_parser = commands.add_parser("aceite", help="testes de aceite do épico")
    aceite_commands = aceite_parser.add_subparsers(dest="aceite_command", metavar="<subcomando>", parser_class=_Parser)
    liberar_parser = aceite_commands.add_parser("liberar", help="retira as marcas de pendente da sua tarefa")
    liberar_parser.add_argument("tarefa", type=int)
    liberar_parser.set_defaults(handler=_aceite_liberar)

    decisao_parser = commands.add_parser("decisao", help="registra uma decisão do dono (frase + label)")
    decisao_parser.add_argument("label", choices=decisions.DECISIONS)
    decisao_parser.add_argument("numero", type=int, help="issue ou PR")
    decisao_parser.add_argument("--frase", required=True, help="as palavras do dono, como ele disse")
    decisao_parser.add_argument("--ia", default=None, help="nome da IA (padrão: BB_IA ou 'ia')")
    decisao_parser.set_defaults(handler=_decisao)

    revisao_parser = commands.add_parser("revisao", help="revisão de PR")
    revisao_commands = revisao_parser.add_subparsers(dest="revisao_command", metavar="<subcomando>",
                                                     parser_class=_Parser)
    aprovar_parser = revisao_commands.add_parser("aprovar", help="põe pr-aprovado depois do bb-revisor-pr")
    aprovar_parser.add_argument("pr", type=int)
    aprovar_parser.add_argument("--ia", default=None)
    aprovar_parser.add_argument("--relatorio", default=None, help="arquivo com o relatório do revisor")
    aprovar_parser.set_defaults(handler=_revisao_aprovar)

    checklist_parser = commands.add_parser("checklist", help="validação final")
    checklist_commands = checklist_parser.add_subparsers(dest="checklist_command", metavar="<subcomando>",
                                                         parser_class=_Parser)
    producao_parser = checklist_commands.add_parser("producao", help="checklist de produção (seção 8.2)")
    producao_parser.add_argument("--dados", help="pasta com o conteúdo a conferir (padrão: a raiz)")
    producao_parser.add_argument("--sem-github", action="store_true", help="não confere os achados de segurança")
    producao_parser.set_defaults(handler=_checklist_producao)

    pipeline_cli.register(commands, _Parser)

    checksums_parser = commands.add_parser("checksums", help="confere ou grava .bigbang/CHECKSUMS (manutenção)")
    checksums_parser.add_argument("--escrever", action="store_true", help="grava o CHECKSUMS com o estado atual")
    checksums_parser.set_defaults(handler=_checksums)

    return parser


def _init(args):
    options = init_module.resolve_options(args.raiz, args.nome, args.slug, args.dono, args.repositorio,
                                          args.visibilidade, args.licenca)
    steps = init_module.plan_steps(options, with_github=not args.sem_github)
    if args.simular:
        print("Simulação do bb init para " + options["repositorio"] + ":")
        for step in steps:
            print(f"  - {step}")
        return EXIT_OK
    issue = init_module.run(args.raiz, options, with_github=not args.sem_github)
    for step in steps:
        print(f"feito: {step}")
    if issue:
        print(f"Issue de F0: {issue}")
    print("Próximo passo: revisar o diff, commitar numa branch fundacao/<n>-f0 e abrir o PR para a develop.")
    return EXIT_OK


def _ia(args):
    import os
    return args.ia or os.environ.get("BB_IA") or "ia"


def _assumir(args):
    config = config_module.load(args.raiz)
    if args.forcar:
        acquired = ownership.recover(config, args.issue, args.nome, args.frase)
    else:
        acquired = ownership.claim(config, args.issue, args.nome)
    try:
        folder = workspaces.isolate(args.raiz, config, acquired, args.pasta)
    except BaseException:
        ownership.release(config, args.issue, acquired["name"], acquired["session"])
        raise
    print(f"#{args.issue}: posse confirmada de {args.nome} (sessão {acquired['session']}).")
    print(f"Pasta própria: {folder}")
    return EXIT_OK


def _liberar(args):
    acquired = workspaces.receipt(args.raiz)
    if acquired.get("issue") != args.issue:
        raise BbError("execute bb liberar na pasta da sessão dona da issue", EXIT_USAGE)
    ownership.release(config_module.load(args.raiz), args.issue, acquired["name"], acquired["session"])
    print(f"#{args.issue}: posse liberada. A pasta de trabalho foi preservada.")
    return EXIT_OK


def _status(args):
    import os
    import subprocess
    config = config_module.load(args.raiz)
    script = os.path.join(args.raiz, ".bigbang", "esteira", "nucleo", "scripts", "ver-paineis.sh")
    env = {**os.environ, "GITHUB_REPOSITORY": config["projeto"]["repositorio"],
           "PROJETO_OWNER": config["paineis"]["owner"], "PYTHON": sys.executable,
           "BB_ENTRY": os.path.join(args.raiz, ".bigbang", "bin", "bb.py"), "BB_ROOT": args.raiz}
    env.pop("BB", None)
    for key in ("planejamento", "execucao", "bugs"):
        env["PROJETO_" + key.upper()] = str(config["paineis"][key]) if config["paineis"][key] else ""
    result = subprocess.run(["bash", script], env=env, cwd=args.raiz, check=False)
    return EXIT_OK if result.returncode == 0 else EXIT_UNEXPECTED


def _decisao(args):
    repository = config_module.load(args.raiz)["projeto"]["repositorio"]
    decisions.record_decision(repository, args.label, args.numero, args.frase, _ia(args))
    print(f"Decisão registrada em #{args.numero}: {args.label}.")
    return EXIT_OK


def _revisao_aprovar(args):
    config = config_module.load(args.raiz)
    report = ""
    if args.relatorio:
        from .paths import read_text
        report = read_text(args.relatorio)
    decisions.approve_review(config["projeto"]["repositorio"], args.pr, _ia(args),
                             config["seguranca"]["zonas_sensiveis"], config["testes"]["marca_pendente"], report)
    print(f"PR #{args.pr}: pr-aprovado (revisão da IA).")
    return EXIT_OK


def _checklist_producao(args):
    import os
    repository = os.environ.get("GITHUB_REPOSITORY") or config_module.load(args.raiz)["projeto"]["repositorio"]
    results, problems = checklist.run(args.dados or args.raiz, repository, with_github=not args.sem_github)
    for item, status, detail in results:
        print(f"[{status}] {item}" + (f" ({detail})" if detail else ""))
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        print(f"Checklist de produção REPROVADO: {len(problems)} problema(s).", file=sys.stderr)
        return EXIT_VERIFICATION_FAILED
    print("Checklist de produção aprovado.")
    return EXIT_OK


def _aceite_liberar(args):
    marker = config_module.load(args.raiz)["testes"]["marca_pendente"]
    changed = acceptance.release_marks(args.raiz, args.tarefa, marker)
    if not changed:
        print(f"Nenhuma marca de pendente da #{args.tarefa} em tests/aceite/.")
        return EXIT_OK
    for path, line in changed:
        print(f"liberado: {path}:{line}")
    print(f"{len(changed)} teste(s) da #{args.tarefa} liberados. Rode os testes de aceite: agora eles precisam passar.")
    return EXIT_OK


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
