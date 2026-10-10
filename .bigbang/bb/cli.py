"""Command-line interface of the Big Bang (`bb`). Messages in Portuguese; stable exit codes in errors.py."""
import argparse
import os
import sys

from . import config as config_module
from . import acceptance, checklist, checksums, claims, decisions, deploy_catalog, generator, ownership, package, status, update, verify, workspaces
from . import init as init_module
from . import documentation_cli, pipeline_cli, test_runs, names
from .errors import EXIT_OK, EXIT_UNEXPECTED, EXIT_USAGE, EXIT_VERIFICATION_FAILED, BbError
from .paths import default_root


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        raise BbError(f"uso inválido: {message}", EXIT_USAGE)


def build_parser():
    parser = _Parser(prog="bb", description="Big Bang: ferramentas do framework.")
    parser.add_argument(*names.cli_option("--raiz"), dest="raiz", default=None, help="raiz do projeto (padrão: a pasta acima de .bigbang/)")
    commands = parser.add_subparsers(dest="command", metavar="<comando>", parser_class=_Parser)

    alvos_parser = commands.add_parser(**names.cli_name(None, "alvos"), help="lista alvos e formatos de deploy instalados (somente leitura)")
    alvos_parser.set_defaults(handler=_alvos)

    config_parser = commands.add_parser(**names.cli_name(None, "config"), help="lê o bigbang.toml")
    config_commands = config_parser.add_subparsers(dest="config_command", metavar="<subcomando>",
                                                   parser_class=_Parser)
    get_parser = config_commands.add_parser(**names.cli_name('config', "get"), help="mostra o valor de uma chave (secao.chave)")
    get_parser.add_argument("chave")
    get_parser.set_defaults(handler=_config_get)

    gerar_parser = commands.add_parser(**names.cli_name(None, "gerar"), help="gera a camada gerada a partir de .bigbang/ e do bigbang.toml")
    gerar_parser.add_argument(*names.cli_option("--simular"), dest="simular", action="store_true", help="só mostra o que mudaria (diff), sem gravar")
    gerar_parser.add_argument(*names.cli_option("--esteira"), dest="esteira", action="store_true",
                              help="instala a esteira (.github/) pela primeira vez (Fundação F5)")
    gerar_parser.set_defaults(handler=_gerar)

    init_parser = commands.add_parser(**names.cli_name(None, "init"), help="Fundação F0: cria o bigbang.toml e liga o projeto ao GitHub")
    init_parser.add_argument(*names.cli_option("--nome"), dest="nome", required=True, help="nome do sistema")
    init_parser.add_argument(*names.cli_option("--slug"), dest="slug", help="identificador em minúsculas com hífen (padrão: a partir do nome)")
    init_parser.add_argument(*names.cli_option("--dono"), dest="dono", help="login do GitHub do dono (padrão: o do repositório ou do gh)")
    init_parser.add_argument(*names.cli_option("--repositorio"), dest="repositorio", help="dono/nome (padrão: o remote origin)")
    init_parser.add_argument(*names.cli_option("--visibilidade"), dest="visibilidade", choices=("privado", "publico"), default="privado")
    init_parser.add_argument(*names.cli_option("--licenca"), dest="licenca", default="", help="identificador SPDX (obrigatório se público)")
    init_parser.add_argument(*names.cli_option("--modo"), dest="modo", choices=("padrao", "flash"), default="padrao", help="modo de trabalho (pode mudar depois)")
    init_parser.add_argument(*names.cli_option("--sem-github"), dest="sem_github", action="store_true", help="não cria label nem issue no GitHub")
    init_parser.add_argument(*names.cli_option("--simular"), dest="simular", action="store_true", help="só mostra o plano")
    init_parser.set_defaults(handler=_init)

    verificar_parser = commands.add_parser(**names.cli_name(None, "verificar"), help="confere framework, arquivos gerados e workflows")
    verificar_parser.set_defaults(handler=_verificar)

    testes_parser = commands.add_parser(**names.cli_name(None, "testes"), help="executa a suíte completa ou os testes afetados no Flash")
    testes_parser.add_argument(*names.cli_option("--base"), dest="base", help="referência Git de comparação; ausência força suíte completa")
    testes_parser.add_argument(*names.cli_option("--fase"), dest="fase", choices=("tarefa", "candidata", "producao"), default="tarefa")
    testes_parser.add_argument(*names.cli_option("--versao"), dest="versao", help="versão de entrega X.Y.Z (major/minor exige suíte completa)")
    testes_parser.add_argument(*names.cli_option("--completo"), dest="completo", action="store_true", help="força suíte completa")
    testes_parser.add_argument(*names.cli_option("--simular"), dest="simular", action="store_true", help="mostra a decisão sem executar testes")
    testes_parser.set_defaults(handler=_testes)

    assumir_parser = commands.add_parser(**names.cli_name(None, "assumir"), help="confirma a posse e abre uma pasta de trabalho própria")
    assumir_parser.add_argument("issue", type=int)
    assumir_parser.add_argument("nome")
    assumir_parser.add_argument(*names.cli_option("--forcar"), dest="forcar", action="store_true", help="retoma uma posse parada por ordem do dono")
    assumir_parser.add_argument(*names.cli_option("--frase"), dest="frase", help="ordem do dono (obrigatória com --forcar)")
    assumir_parser.add_argument(*names.cli_option("--pasta"), dest="pasta", help="pasta própria do worktree (padrão: ../repo-nome)")
    assumir_parser.add_argument("--person", action="store_true", help="v3: posse de uma pessoa (login) em vez de IA")
    assumir_parser.set_defaults(handler=_assumir)

    renew_parser = commands.add_parser("renew", help="v3: renova o prazo da posse da sessão na pasta atual")
    renew_parser.add_argument("issue", type=int)
    renew_parser.set_defaults(handler=_renew)

    liberar_posse = commands.add_parser(**names.cli_name(None, "liberar"), help="libera a posse da sessão na pasta de trabalho atual")
    liberar_posse.add_argument("issue", type=int)
    liberar_posse.set_defaults(handler=_liberar)

    status_parser = commands.add_parser(**names.cli_name(None, "status"), help="resumo dos painéis, posses, flags e segurança (somente leitura)")
    status_parser.set_defaults(handler=_status)

    aceite_parser = commands.add_parser(**names.cli_name(None, "aceite"), help="testes de aceite do épico")
    aceite_commands = aceite_parser.add_subparsers(dest="aceite_command", metavar="<subcomando>", parser_class=_Parser)
    liberar_parser = aceite_commands.add_parser(**names.cli_name('aceite', "liberar"), help="retira as marcas de pendente da sua tarefa")
    liberar_parser.add_argument("tarefa", type=int)
    liberar_parser.set_defaults(handler=_aceite_liberar)

    decisao_parser = commands.add_parser(**names.cli_name(None, "decisao"), help="registra uma decisão do dono (frase + label)")
    decisao_parser.add_argument("label", choices=decisions.ALL_DECISIONS)
    decisao_parser.add_argument("numero", type=int, help="issue ou PR")
    decisao_parser.add_argument(*names.cli_option("--frase"), dest="frase", required=True, help="as palavras do dono, como ele disse")
    decisao_parser.add_argument(*names.cli_option("--ia"), dest="ia", default=None, help="nome da IA (padrão: BB_IA ou 'ia')")
    decisao_parser.set_defaults(handler=_decisao)

    revisao_parser = commands.add_parser(**names.cli_name(None, "revisao"), help="revisão de PR")
    revisao_commands = revisao_parser.add_subparsers(dest="revisao_command", metavar="<subcomando>",
                                                     parser_class=_Parser)
    aprovar_parser = revisao_commands.add_parser(**names.cli_name('revisao', "aprovar"), help="põe pr-aprovado depois do bb-revisor-pr")
    aprovar_parser.add_argument("pr", type=int)
    aprovar_parser.add_argument(*names.cli_option("--ia"), dest="ia", default=None)
    aprovar_parser.add_argument(*names.cli_option("--relatorio"), dest="relatorio", default=None, help="arquivo com o relatório do revisor")
    aprovar_parser.set_defaults(handler=_revisao_aprovar)

    checklist_parser = commands.add_parser(**names.cli_name(None, "checklist"), help="validação final")
    checklist_commands = checklist_parser.add_subparsers(dest="checklist_command", metavar="<subcomando>",
                                                         parser_class=_Parser)
    producao_parser = checklist_commands.add_parser(**names.cli_name('checklist', "producao"), help="checklist de produção (seção 8.2)")
    producao_parser.add_argument(*names.cli_option("--dados"), dest="dados", help="pasta com o conteúdo a conferir (padrão: a raiz)")
    producao_parser.add_argument(*names.cli_option("--sem-github"), dest="sem_github", action="store_true", help="não confere os achados de segurança")
    producao_parser.set_defaults(handler=_checklist_producao)

    pipeline_cli.register(commands, _Parser)
    documentation_cli.register(commands, _Parser)

    atualizar_parser = commands.add_parser(**names.cli_name(None, "atualizar"), help="atualiza o framework numa branch framework/vX.Y.Z (PR)")
    atualizar_parser.add_argument("versao", nargs="?", help="versão alvo X.Y.Z (padrão: a última da origem)")
    atualizar_parser.add_argument(*names.cli_option("--simular"), dest="simular", action="store_true", help="baixa, confere e mostra a migração; não grava")
    atualizar_parser.add_argument(*names.cli_option("--confirmo-migracao"), dest="confirmo_migracao", action="store_true",
                                  help="o dono confirmou os passos manuais do MIGRACAO.md")
    atualizar_parser.add_argument(*names.cli_option("--sem-atestacao"), dest="sem_atestacao", action="store_true",
                                  help="só para origem sem atestação (fork privado); confere apenas o SHA-256")
    atualizar_parser.set_defaults(handler=_atualizar)

    pacote_parser = commands.add_parser(**names.cli_name(None, "pacote"), help="empacota .bigbang/ para a release do framework (manutenção)")
    pacote_parser.add_argument(*names.cli_option("--saida"), dest="saida", default="dist")
    pacote_parser.add_argument(*names.cli_option("--notas"), dest="notas", default=None, help="grava as notas da versão (MIGRACAO.md) neste arquivo")
    pacote_parser.set_defaults(handler=_pacote)

    checksums_parser = commands.add_parser(**names.cli_name(None, "checksums"), help="confere ou grava .bigbang/CHECKSUMS (manutenção)")
    checksums_parser.add_argument(*names.cli_option("--escrever"), dest="escrever", action="store_true", help="grava o CHECKSUMS com o estado atual")
    checksums_parser.set_defaults(handler=_checksums)

    return parser


def _init(args):
    options = init_module.resolve_options(args.raiz, args.nome, args.slug, args.dono, args.repositorio,
                                          args.visibilidade, args.licenca, args.modo)
    steps = init_module.plan_steps(options, with_github=not args.sem_github)
    if args.simular:
        print("Simulação do bb init para " + options["repositorio"] + ":")
        for step in steps:
            print(f"  - {step}")
        return EXIT_OK
    problem = init_module.hook_python_problem()
    if problem:
        print(f"Atenção: {problem}", file=sys.stderr)
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


def _testes(args):
    test_runs.run(args.raiz, config_module.load(args.raiz), base=args.base, phase=args.fase,
                  version=args.versao, full=args.completo, simulate=args.simular)
    return EXIT_OK


def _v3_client(config):
    from . import gh
    return gh.GitHub(config_module.get(config, "project.repository"))


def _assumir(args):
    config = config_module.load(args.raiz)
    if claims.is_v3(config):
        return _claim_v3(args, config)
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


def _claim_v3(args, config):
    """v3 claim: lock first, worktree only for issues with a branch (an epic in refinement has none)."""
    import json
    client = _v3_client(config)
    if args.forcar:
        acquired = claims.force(client, config, args.issue, args.nome, args.frase, person=args.person)
    else:
        acquired = claims.claim(client, config, args.issue, args.nome, person=args.person)
    labels = client.issue(args.issue)["labels"]
    if "type:epic" in labels or "epic" in labels:
        print(f"#{args.issue}: posse confirmada de {args.nome} (geração {acquired['generation']}, até "
              f"{acquired['expires']}); épico sem branch, nenhuma pasta criada.")
        path = workspaces.git(args.raiz, "rev-parse", "--git-path", "bb-posse.json")
        with open(path if os.path.isabs(path) else os.path.join(args.raiz, path), "w", encoding="utf-8") as handle:
            json.dump(acquired, handle)
        return EXIT_OK
    try:
        folder = workspaces.isolate(args.raiz, config, acquired, args.pasta, kinds=workspaces.V3_KINDS)
    except BaseException:
        claims.unclaim(client, config, acquired, reason="pasta de trabalho não pôde ser criada")
        raise
    print(f"#{args.issue}: posse confirmada de {args.nome} (geração {acquired['generation']}, até "
          f"{acquired['expires']}). Renove com bb renew {args.issue}.")
    print(f"Pasta própria: {folder}")
    return EXIT_OK


def _session_receipt(args, command):
    acquired = workspaces.receipt(args.raiz)
    if acquired.get("issue") != args.issue:
        raise BbError(f"execute bb {command} na pasta da sessão dona da issue (o recibo da posse fica nos metadados "
                      "Git dessa pasta: libere ANTES de remover a pasta com git worktree remove)", EXIT_USAGE)
    return acquired


def _renew(args):
    import json
    config = config_module.load(args.raiz)
    if not claims.is_v3(config):
        raise BbError("bb renew é da posse v3; no modelo legado a posse é renovada pelos pushes", EXIT_USAGE)
    acquired = claims.renew(_v3_client(config), config, _session_receipt(args, "renew"))
    path = workspaces.git(args.raiz, "rev-parse", "--git-path", "bb-posse.json")
    with open(path if os.path.isabs(path) else os.path.join(args.raiz, path), "w", encoding="utf-8") as handle:
        json.dump(acquired, handle)
    print(f"#{args.issue}: posse renovada até {acquired['expires']}.")
    return EXIT_OK


def _liberar(args):
    acquired = _session_receipt(args, "liberar")
    config = config_module.load(args.raiz)
    if claims.is_v3(config):
        claims.unclaim(_v3_client(config), config, acquired)
        print(f"#{args.issue}: posse liberada. A pasta de trabalho foi preservada.")
        return EXIT_OK
    ownership.release(config, args.issue, acquired["name"], acquired["session"])
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
    config = config_module.load(args.raiz)
    label = names.label(args.label, names.label_dialect(config))  # either spelling, written in the project's
    decisions.record_decision(config["projeto"]["repositorio"], label, args.numero, args.frase, _ia(args))
    print(f"Decisão registrada em #{args.numero}: {label}.")
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


def _atualizar(args):
    update.check_args(args.versao)
    update.update(args.raiz, args.versao, simulate=args.simular, confirmed=args.confirmo_migracao,
                  attestation=not args.sem_atestacao)
    return EXIT_OK


def _pacote(args):
    import os
    from .paths import framework_version, write_text
    target, digest = package.build(args.raiz, os.path.join(args.raiz, args.saida) if not os.path.isabs(args.saida)
                                   else args.saida)
    if args.notas:
        write_text(args.notas, package.release_notes(args.raiz, framework_version(args.raiz)) + "\n")
    print(f"{target}\n{digest}")
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


def _alvos(args):
    problems = []
    for collection, title in (('alvos', 'Alvos de deploy'), ('artefatos', 'Formatos de artefato')):
        print(title + ':')
        entries = deploy_catalog.entries(args.raiz, collection)
        if not entries:
            problems.append(f'{collection}: catálogo instalado ausente ou vazio')
        for name, entry, error in entries:
            if error:
                print(f'  {name}: inválido')
                problems.append(error)
            else:
                capabilities = ' (artefatos: ' + ', '.join(entry.artifacts) + ')' if collection == 'alvos' else ''
                print(f'  {name}: {entry.state}{capabilities} — {entry.description}')
    for problem in problems:
        print('  - ' + problem, file=sys.stderr)
    return EXIT_VERIFICATION_FAILED if problems else EXIT_OK


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
