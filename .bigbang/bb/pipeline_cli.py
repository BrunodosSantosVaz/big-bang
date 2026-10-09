"""`bb esteira <subcomando>`: the pipeline rules for the Bash scripts (input on stdin, plain-text output).

These are building blocks for the generated workflows, not commands the owner types.
"""
import datetime
import os
import sys
import tomllib

from . import config as config_module
from . import acceptance, community_public, documentation, docs_check, ownership, pipeline, stack_guard, status, traceability
from .errors import EXIT_OK, EXIT_USAGE, EXIT_VERIFICATION_FAILED, BbError
from .paths import CONFIG_FILE, read_text, write_text


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

    p = sub.add_parser("documentacao", help="Markdown válido, links relativos (DOC-14), README do sistema (DOC-15), "
                                            "arquivos de comunidade (DOC-16) e ícone global (DOC-17)")
    p.add_argument("--dados", help="pasta com o conteúdo revisado a conferir")
    p.add_argument("--publicada", action="store_true")
    p.add_argument("--comunidade", action="store_true")
    p.add_argument('--visibilidade-remota', action='store_true')
    p.set_defaults(handler=_docs)

    p = sub.add_parser("comunidade", help="cria os arquivos de comunidade que faltam (DOC-16) a partir dos modelos")
    p.set_defaults(handler=_community)

    p = sub.add_parser("so-liberacao", help="o diff (entrada padrão) em tests/aceite/ só retira marcas da issue?")
    p.add_argument("issue", type=int)
    p.set_defaults(handler=_only_release)

    p = sub.add_parser("nome-candidata", help="nome do binário na candidata (slug, versão, rc, sistema, arquivo)")
    for nome in ("versao", "rc", "sistema", "arquivo"):
        p.add_argument(nome)
    p.set_defaults(handler=_candidate_name)

    p = sub.add_parser("nome-producao", help="nome do binário em produção (tira o -rc.N)")
    p.add_argument("arquivo")
    p.set_defaults(handler=lambda args: print(pipeline.promoted_name(args.arquivo)) or EXIT_OK)

    p = sub.add_parser("trava-aceite", help="trava de tests/aceite/ (diff na entrada padrão)")
    p.add_argument("tipo", help="tipo da branch: teste, feature, docs, bugfix, hotfix…")
    p.add_argument("issue", nargs="?", type=int)
    p.add_argument("--aprovado", action="store_true", help="o PR tem teste-alterado-aprovado")
    p.set_defaults(handler=_lock)

    p = sub.add_parser("pendentes", help="marcas de pendente em tests/aceite/: <issue>\t<arquivo:linha>")
    p.add_argument("--dados", help="pasta com o conteúdo a examinar (padrão: a raiz)")
    p.set_defaults(handler=_pending)

    p = sub.add_parser("rastreabilidade", help="RN vigente sem teste, teste sem RN, RN apagada")
    p.add_argument("--dados", help="pasta com o conteúdo a examinar (padrão: a raiz)")
    p.add_argument("--mudados", default="", help="arquivo com os caminhos mudados no PR (um por linha)")
    p.add_argument("--padrao-dos-dados", action="store_true",
                   help="usa testes.padrao_teste do bigbang.toml de --dados (PR release/*: conteúdo já revisado)")
    p.set_defaults(handler=_traceability)

    p = sub.add_parser("guarda-stack", help="dependências diretas de execução fora do STACK.md")
    p.add_argument("--dados", help="pasta com o conteúdo a examinar (padrão: a raiz)")
    p.set_defaults(handler=_stack_guard)

    sub.add_parser("osv-avaliar", help="relatório JSON do OSV-Scanner (entrada padrão): reprova alta e crítica"
                   ).set_defaults(handler=_osv)

    p = sub.add_parser("rls", help="tabelas sem RLS nas migrações (quando banco_no_navegador = true)")
    p.add_argument("--pasta", default="migrations")
    p.set_defaults(handler=_rls)

    p = sub.add_parser("gravar-versao", help="grava a versão no arquivo de versão da stack (entrega.arquivo_versao)")
    p.add_argument("versao")
    p.set_defaults(handler=_write_version)

    sub.add_parser("resumo-posses", help="possessões, flags e segurança (somente leitura)").set_defaults(
        handler=lambda args: status.report(args.raiz, config_module.load(args.raiz)) or EXIT_OK)

    p = sub.add_parser("marcar-paradas", help="marca posses sem push há mais que ias.trava_expira_horas")
    p.add_argument("--aplicar", action="store_true", help="grava a label parada; padrão: simulação")
    p.set_defaults(handler=lambda args: status.mark_stale(config_module.load(args.raiz), not args.aplicar) or EXIT_OK)

    p = sub.add_parser("liberar-posse", help="liberação automática depois do merge (uso interno da esteira)")
    p.add_argument("issue", type=int)
    p.set_defaults(handler=lambda args: ownership.release(config_module.load(args.raiz), args.issue,
                                                          automated=True) or EXIT_OK)

    p = sub.add_parser("registrar-push", help="registra push na posse pelo horário do GitHub (uso interno)")
    p.add_argument("issue", type=int)
    p.set_defaults(handler=lambda args: ownership.touch(config_module.load(args.raiz), args.issue) or EXIT_OK)


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
    public = documentation.is_public(args.raiz)
    path = os.path.join(args.raiz, args.arquivo)
    current = documentation.read(args.raiz, args.arquivo) if public else read_text(path) if os.path.exists(path) else None
    date = args.data or datetime.date.today().isoformat()
    text = pipeline.changelog_with_release(current, args.versao, date, items)
    if public:
        from . import documentation_cli
        import argparse
        import tempfile
        with tempfile.TemporaryDirectory(prefix="bb-changelog-") as temporary:
            draft = os.path.join(temporary, "changelog.md")
            write_text(draft, text)
            documentation_cli._write(argparse.Namespace(raiz=args.raiz, documento=args.arquivo, arquivo=draft))
        folder, _ = documentation.prepare(args.raiz)
        documentation_cli._propose(argparse.Namespace(raiz=args.raiz, wiki=str(folder),
                                                       branch="bigbang/proposta-release-" + args.versao))
    else:
        write_text(path, text)
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


def _candidate_name(args):
    slug = config_module.load(args.raiz)["projeto"]["slug"]
    print(pipeline.candidate_asset_name(slug, args.versao, args.rc, args.sistema, args.arquivo))
    return EXIT_OK


def _lock(args):
    marker = config_module.load(args.raiz)["testes"]["marca_pendente"]
    problems = acceptance.lock_problems(_stdin(), args.tipo, args.issue, marker, args.aprovado)
    for problem in problems:
        print(problem)
    return EXIT_VERIFICATION_FAILED if problems else EXIT_OK


def _pending(args):
    marker = config_module.load(args.raiz)["testes"]["marca_pendente"]
    for issue, where in acceptance.pending_marks(args.dados or args.raiz, marker):
        print(f"{issue}\t{where}")
    return EXIT_OK


def _report(problems, ok_message):
    for problem in problems:
        print(problem)
    if not problems:
        print(ok_message)
    return EXIT_VERIFICATION_FAILED if problems else EXIT_OK


def _traceability(args):
    pattern = config_module.load(args.raiz)["testes"]["padrao_teste"]
    if args.padrao_dos_dados and args.dados and os.path.exists(os.path.join(args.dados, CONFIG_FILE)):
        with open(os.path.join(args.dados, CONFIG_FILE), "rb") as handle:  # only this key; scripts stay the target's
            pattern = tomllib.load(handle).get("testes", {}).get("padrao_teste", pattern)
    changed = read_text(args.mudados).split() if args.mudados else []
    return _report(traceability.problems(args.dados or args.raiz, pattern, changed),
                   "Rastreabilidade: toda RN vigente tem teste e todo teste cita uma RN.")


def _stack_guard(args):
    return _report(stack_guard.problems(args.dados or args.raiz),
                   "Guarda da stack: todas as dependências de execução estão aprovadas no STACK.md.")


def _osv(args):
    import json
    text = _stdin().strip()
    findings = pipeline.osv_high_findings(json.loads(text) if text else {})
    return _report(findings, "OSV-Scanner: nenhuma vulnerabilidade alta ou crítica.")


def _rls(args):
    if not config_module.load(args.raiz)["seguranca"]["banco_no_navegador"]:
        print("banco_no_navegador = false: o navegador não acessa o banco (SEG-IA-01); nada a conferir.")
        return EXIT_OK
    folder = os.path.join(args.raiz, args.pasta)
    texts = []
    for current, _, names in os.walk(folder):
        texts += [read_text(os.path.join(current, n)) for n in sorted(names) if n.endswith(".sql")]
    missing = pipeline.tables_without_rls(texts)
    return _report([f"tabela {t} sem ROW LEVEL SECURITY (SEG-IA-01)" for t in missing],
                   "Todas as tabelas das migrações têm RLS ligada.")


def _docs(args):
    root = args.dados or args.raiz
    if args.visibilidade_remota:
        visibility = documentation.visibility_problems(root)
        if visibility:
            return _report(visibility, '')
    if args.publicada and not documentation.is_public(root):
        print("Projeto privado: publicação documental local preservada")
        return EXIT_OK
    problems = docs_check.problems(root)
    if documentation.is_public(root):
        if args.publicada:
            problems += documentation.validate(root, published=True)
        if args.comunidade:
            config = config_module.load(root, required=False)
            config = config or documentation.load(root).get("configuracao_comunidade")
            if config:
                problems += community_public.verify(root, config)
            else:
                problems.append("configuração dos três painéis obrigatórios ausente")
    for problem in problems:
        print(problem)
    if not problems:
        print("Documentação: Markdown e links em ordem.")
    return EXIT_VERIFICATION_FAILED if problems else EXIT_OK


def _community(args):
    from .render import substitute
    config = config_module.load(args.raiz)
    created = []
    for name in docs_check.COMMUNITY_FILES:
        target = os.path.join(args.raiz, name)
        if os.path.exists(target):
            continue
        source = f".bigbang/modelos/comunidade/{name}"
        write_text(target, substitute(read_text(os.path.join(args.raiz, source)), config, source))
        created.append(name)
    print("Criados: " + ", ".join(created) if created else "Arquivos de comunidade já existem.")
    return EXIT_OK


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
