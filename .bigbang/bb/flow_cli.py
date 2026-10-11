"""CLI of the v3 board and controller (ADR-0023/0026): bb board …, bb move and bb pipeline controller."""
import json

from . import board, controller, gh, names
from . import config as config_module
from .errors import EXIT_INVALID_STATE, EXIT_OK, EXIT_USAGE, BbError


def register(commands, pipeline_sub):
    migration = commands.add_parser(**names.cli_name(None, "migrar"), help="migração opcional para a v3, em quatro PRs")
    migration_sub = migration.add_subparsers(dest="migration_part", metavar="<parte>")
    for part in ("config", "board", "workflow", "labels"):
        p = migration_sub.add_parser(part, help=f"migra {part}, com plano e volta")
        p.add_argument("--dry-run", action="store_true", help="só mostra o plano, sem gravar")
        p.add_argument("--snapshot", help="arquivo protegido com o estado anterior (obrigatório para aplicar)")
        p.add_argument("--rollback", action="store_true", help="restaura a parte pelo snapshot")
        p.add_argument("--yes", action="store_true", help="confirma as escritas no GitHub desta parte")
        p.set_defaults(handler=_migrate)
    board_parser = commands.add_parser("board", help="v3: quadro único (labels, Project, reconciliação)")
    sub = board_parser.add_subparsers(dest="board_command", metavar="<subcomando>")
    sub.add_parser("labels", help="cria as labels da v3 que faltam (idempotente)").set_defaults(handler=_labels)
    p = sub.add_parser("create", help="cria ou completa o Project único do repositório")
    p.add_argument("--title", required=True, help="nome do Project (normalmente o nome do produto)")
    p.set_defaults(handler=_create)
    sub.add_parser("reconcile", help="devolve cada cartão ao estado registrado nos recibos").set_defaults(
        handler=_reconcile)
    sub.add_parser("show", help="estado de cada cartão aberto (somente leitura)").set_defaults(handler=_show)

    move = commands.add_parser("move", help="v3: move um cartão conferindo regras, portões e evidências")
    move.add_argument("issue", type=int)
    move.add_argument("state", help="estado de destino (por exemplo: Backlog, Refinement, Rejected)")
    move.add_argument("--reason", help="motivo (Rejected: requirements, tests, code, security, docs, qa…; Cancelled: texto)")
    move.add_argument("--return-to", dest="return_to", help="Rejected: estado para onde o trabalho volta")
    move.set_defaults(handler=_move)

    sprint = commands.add_parser("sprint", help="v3: inicia a sprint dos épicos em Selected")
    sprint_sub = sprint.add_subparsers(dest="sprint_command", metavar="<subcomando>")
    p = sprint_sub.add_parser("start", help="cria teste, tarefas e documentação; branch de teste a partir da develop")
    p.add_argument("--epic", type=int, action="append", help="só estes épicos (repetível)")
    p.add_argument("--date", help="AAAA-MM-DD (padrão: hoje)")
    p.set_defaults(handler=_sprint_start)

    p = commands.add_parser("branches", help="v3: cria as branches desbloqueadas a partir da develop")
    p.add_argument("--epic", type=int)
    p.set_defaults(handler=_branches)

    p = commands.add_parser("merge", help="v3: mescla um PR aprovado e verde na develop ou na release (nunca na main)")
    p.add_argument("pr", type=int)
    p.set_defaults(handler=_merge)

    release = commands.add_parser("release", help="v3: corte e portão da release")
    release_sub = release.add_subparsers(dest="release_command", metavar="<subcomando>")
    p = release_sub.add_parser("cut", help="corta release/x.y.z da develop (versão pelos títulos dos PRs)")
    p.add_argument("--version", help="X.Y.Z (padrão: calculada)")
    p.set_defaults(handler=_release_cut)
    p = release_sub.add_parser("items", help="PRs da release (número, título, labels) para o CHANGELOG")
    p.add_argument("--head", default="develop", help="branch da release (padrão: develop)")
    p.set_defaults(handler=_release_items)
    p = release_sub.add_parser("gate", help="confere flags e testes pendentes dos épicos da release")
    p.add_argument("--epic", type=int, action="append", required=True)
    p.add_argument("--content-dir", dest="content_dir", help="conteúdo da release lido como dado (padrão: --raiz)")
    p.set_defaults(handler=_release_gate)

    p = release_sub.add_parser("publish", help="portão e publicação da release (merge na main, épicos, sync)")
    p.add_argument("--version", required=True)
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="só confere o portão")
    p.add_argument("--content-dir", dest="content_dir",
                   help="conteúdo da release (flags.toml, testes pendentes) lido como dado (padrão: --raiz)")
    p.set_defaults(handler=_release_publish)
    p = release_sub.add_parser("maintenance", help="publica um PR maintenance/* na main (sem mudar o artefato)")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="só confere o portão")
    p.set_defaults(handler=_release_maintenance)

    qa = commands.add_parser("qa", help="v3: homologação")
    qa_sub = qa.add_subparsers(dest="qa_command", metavar="<subcomando>")
    p = qa_sub.add_parser("reject", help="reprovação registrada: épico de volta e tarefa de correção na release")
    p.add_argument("epic", type=int)
    p.add_argument("--reason", required=True, help="motivo nas palavras do dono")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="só confere a reprovação registrada")
    p.set_defaults(handler=_qa_reject)
    p = qa_sub.add_parser("verdict", help="QA delegado: o agente independente registra o veredito da candidata")
    p.add_argument("epic", type=int)
    p.add_argument("--candidate", required=True, help="versão candidata homologada (ex.: v1.3.0-rc.1)")
    p.add_argument("--digest", required=True, help="digest do artefato homologado")
    p.add_argument("--verdict", required=True, choices=("approved", "rejected"))
    p.add_argument("--agent", required=True, help="nome do agente que homologou (de agents.names)")
    p.set_defaults(handler=_qa_verdict)

    autonomy_parser = commands.add_parser("autonomy", help="v3: modo autonomous (contrato e controles)")
    autonomy_sub = autonomy_parser.add_subparsers(dest="autonomy_command", metavar="<subcomando>")
    autonomy_sub.add_parser("check", help="confere autonomy.toml e os controles exigidos (ruleset, production)"
                            ).set_defaults(handler=_autonomy_check)

    p = commands.add_parser("cleanup", help="v3: faxina de branches concluídas; relata posses antigas")
    p.add_argument("--apply", action="store_true", help="apaga de verdade (padrão: só mostra o plano)")
    p.set_defaults(handler=_cleanup)

    flag = commands.add_parser("flag", help="v3: liga, desliga ou lista feature flags (flags.toml)")
    flag_sub = flag.add_subparsers(dest="flag_command", metavar="<subcomando>")
    flag_sub.add_parser("list", help="lista as flags e seus estados").set_defaults(handler=_flag_list)
    for action in ("on", "off"):
        p = flag_sub.add_parser(action, help=f"{'liga' if action == 'on' else 'desliga'} uma flag num ambiente")
        p.add_argument("name")
        p.add_argument("--env", choices=("staging", "production"), default="production")
        p.set_defaults(handler=_flag_switch, value=action == "on")

    p = pipeline_sub.add_parser("candidate-ready", help="v3: épicos da candidata em QA e PR da release")
    p.add_argument("--branch", required=True)
    p.add_argument("--rc-tag", dest="rc_tag", required=True)
    p.set_defaults(handler=_candidate_ready)

    p = pipeline_sub.add_parser("pr-rules", help="v3: regras do PR (branch, título, Refs, aceite, flag, zona sensível)")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--content-dir", dest="content_dir",
                   help="pasta com o conteúdo do PR (lido como dado): pendentes, rastreabilidade, guarda da stack")
    p.set_defaults(handler=_pr_rules)

    p = pipeline_sub.add_parser("controller", help="v3: aplica um evento do GitHub ao quadro (uso da esteira)")
    p.add_argument("--event", required=True, help="nome do evento (issues, push, pull_request, schedule)")
    p.add_argument("--payload", help="arquivo JSON do evento (GITHUB_EVENT_PATH)")
    p.set_defaults(handler=_controller)


def _migrate(args):
    from . import migrate
    part = args.migration_part
    dry_run = args.dry_run or (part in ("board", "labels") and not args.yes)
    if not dry_run and not args.snapshot:
        raise BbError("para aplicar ou voltar, informe --snapshot <arquivo>; para planejar use --dry-run", EXIT_USAGE)
    options = {"snapshot": args.snapshot, "dry_run": dry_run, "rollback": args.rollback}
    if part == "config":
        report = migrate.config_part(args.raiz, **options)
    else:
        config = config_module.load(args.raiz)
        repository = config_module.get(config, "project.repository")
        client = gh.GitHub(repository)
        if part == "board":
            owner = config_module.get(config, "board.owner")
            def open_project(number):
                return board.ProjectGraphQL(owner, number, repository, gh.graphql)
            def create_project():
                number = board.create_project(gh.graphql, owner, config_module.get(config, "project.name"), repository)
                return number, open_project(number)
            report = migrate.board_part(client, args.raiz, open_project=open_project,
                                        create_project=create_project, **options)
        else:
            report = getattr(migrate, part + "_part")(client, args.raiz, **options)
    if dry_run:
        print("Plano de migração (nenhuma alteração aplicada).")
        if part in ("board", "labels") and not args.yes:
            print("Escritas no GitHub exigem --yes e --snapshot <arquivo> após revisar o plano.")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_OK


def _load(root):
    """The configuration plus the autonomy contract of this checkout (in the CI, the target branch)."""
    from . import autonomy
    return autonomy.attach(config_module.load(root), root)


def _context(root):
    config = _load(root)
    if config_module.get(config, "board.model") != "single":
        raise BbError("este projeto ainda usa os três painéis (board.model = three-boards): rode bb migrate board",
                      EXIT_USAGE)
    repository = config_module.get(config, "project.repository")
    client = gh.GitHub(repository)
    project = board.ProjectGraphQL(config_module.get(config, "board.owner"), config_module.get(config, "board.number"),
                                   repository, gh.graphql)
    return config, client, project


def _labels(args):
    config = _load(args.raiz)
    created = board.ensure_labels(gh.GitHub(config_module.get(config, "project.repository")))
    print(f"Labels da v3: {created} criada(s); as demais já existiam.")
    return EXIT_OK


def _create(args):
    config = _load(args.raiz)
    repository = config_module.get(config, "project.repository")
    if config_module.get(config, "project.mode") == "autonomous":
        _refuse_autonomy(gh.GitHub(repository), config, contract=False)
    owner = config_module.get(config, "board.owner")
    number = board.create_project(gh.graphql, owner, args.title, repository)
    board.ensure_fields(board.ProjectGraphQL(owner, number, repository, gh.graphql))
    print(f"Project único #{number} pronto para {repository} (15 estados, campos e visões Board/Table/Roadmap).")
    print("No bigbang.toml, seção [board]: model = \"single\", number = " + str(number))
    print(f"Variáveis do repositório: gh variable set PROJECT_OWNER --repo {repository} --body {owner}")
    print(f"                          gh variable set PROJECT_NUMBER --repo {repository} --body {number}")
    return EXIT_OK


def _refuse_autonomy(client, config, *, contract=True):
    from . import autonomy
    import datetime
    found = (autonomy.problems(config, _today()) if contract else []) + autonomy.bootstrap_problems(client)
    if found:
        raise BbError("o modo autonomous não pode ser ligado neste repositório:\n" +
                      "\n".join(f"  - {item}" for item in found), EXIT_INVALID_STATE)


def _autonomy_check(args):
    config = _load(args.raiz)
    _refuse_autonomy(gh.GitHub(config_module.get(config, "project.repository")), config)
    print("Modo autonomous: contrato válido e controles do repositório no lugar (gate obrigatório na main e na "
          "develop; production só a partir da main).")
    return EXIT_OK


def _reconcile(args):
    config, client, project = _context(args.raiz)
    fixed = board.reconcile(client, project, config)
    for number, shown, expected in fixed:
        print(f"#{number}: {shown or '(fora do quadro)'} → {expected}")
    print(f"Reconciliação: {len(fixed)} cartão(ões) ajustado(s).")
    return EXIT_OK


def _show(args):
    config, client, project = _context(args.raiz)
    trusted = {config_module.get(config, "project.owner")}
    for issue in client.issues("open"):
        if board.states.kind(set(issue["labels"])):
            print(f"{board.current_state(client, issue['number'], trusted, issue):<12} #{issue['number']} "
                  f"{issue['title']}")
    return EXIT_OK


def _move(args):
    config, client, project = _context(args.raiz)
    actor = gh.GitHub(config_module.get(config, "project.repository")).api("GET", "user")[1]["login"]  # recorded only
    receipt = board.move(client, project, config, args.issue, args.state, actor, reason=args.reason,
                         return_to=args.return_to)
    print(f"#{args.issue}: {receipt['from']} → {receipt['to']} ({receipt['event_id']}).")
    return EXIT_OK


def _today(value=None):
    import datetime
    return datetime.date.fromisoformat(value) if value else datetime.date.today()


def _sprint_start(args):
    from . import flows
    config, client, project = _context(args.raiz)
    plan = flows.start_sprint(client, project, config, date=_today(args.date), epics=args.epic)
    for item in plan:
        print(f"Épico #{item['epic']} em {item['sprint']}: teste #{item['test']}, tarefas "
              + ", ".join(f"#{n}" for n in item["tasks"]) + f", documentação #{item['docs']}.")
    print(f"Sprint: {len(plan)} épico(s) iniciado(s).")
    return EXIT_OK


def _branches(args):
    from . import flows
    config = _load(args.raiz)
    for name in flows.create_branches(gh.GitHub(config_module.get(config, "project.repository")), config, args.epic):
        print(f"branch criada: {name}")
    return EXIT_OK


def _merge(args):
    from . import flows
    config = _load(args.raiz)
    created = flows.merge_pr(gh.GitHub(config_module.get(config, "project.repository")), config, args.pr)
    print(f"PR #{args.pr} mesclado." + (" Branches criadas: " + ", ".join(created) if created else ""))
    return EXIT_OK


def _release_cut(args):
    from . import flows
    config = _load(args.raiz)
    release = flows.cut_release(gh.GitHub(config_module.get(config, "project.repository")), config,
                                version=args.version)
    if release is None:
        print("Nada a publicar: a develop não tem PRs mesclados fora da main.")
        return EXIT_OK
    print(f"{release['branch']} cortada da develop ({release['sha'][:10]}); versão {release['previous']} → "
          f"{release['version']}; épicos " + ", ".join(f"#{n}" for n in release["epics"]) + ".")
    return EXIT_OK


def _release_items(args):
    from . import flows
    config = _load(args.raiz)
    for number, title, labels in flows.release_items(gh.GitHub(config_module.get(config, "project.repository")),
                                                     head=args.head):
        print(f"{number}\t{title}\t{','.join(labels)}")
    return EXIT_OK


def _release_gate(args):
    from . import flows
    config, client, project = _context(args.raiz)
    problems = flows.release_gate(client, config, args.content_dir or args.raiz, args.epic, today=_today(),
                                  project=project)
    for problem in problems:
        print(problem)
    if problems:
        raise BbError("portão da release recusado", EXIT_USAGE)
    print("Portão da release: cada épico está homologado ou entra com a flag desligada.")
    return EXIT_OK


def _flag_path(root):
    import os
    return os.path.join(root, "flags.toml")


def _flag_list(args):
    from . import flags
    import os
    path = _flag_path(args.raiz)
    registered = flags.parse(open(path, encoding="utf-8").read(), _today()) if os.path.exists(path) else []
    for flag in registered:
        print(f"{flag['name']}: épico #{flag['epic']} · staging={'on' if flag['staging'] else 'off'} · "
              f"production={'on' if flag['production'] else 'off'} · expira {flag['expires']}")
    return EXIT_OK


def _flag_switch(args):
    from . import flags
    path = _flag_path(args.raiz)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(flags.switch(text, args.name, args.env, args.value, _today()))
    print(f"flag {args.name}: {args.env} {'ligada' if args.value else 'desligada'} no flags.toml "
          "(zona sensível: abra o PR para a decisão registrada).")
    return EXIT_OK


def _flags_by_agent(config):
    from . import autonomy
    contract = autonomy.usable(config, _today())
    return bool(contract) and contract.get("flags") == "agent"


def _pr_rules(args):
    from . import pipeline
    config = _load(args.raiz)
    client = gh.GitHub(config_module.get(config, "project.repository"))
    pull = client.pull(args.pr)
    files = client.pull_files(args.pr)
    paths, diffs = [], []
    for file in files:
        path, previous = file["filename"], file.get("previous_filename", file["filename"])
        paths.extend({previous, path})
        if path.startswith("tests/aceite/") or previous.startswith("tests/aceite/"):
            diffs.append(f"diff --git a/{previous} b/{path}\n--- a/{previous}\n+++ b/{path}\n{file.get('patch', '')}")
    _, issue_number = pipeline.branch_issue(pull["head"])
    issue = client.issue(issue_number) if issue_number else None
    parent = client.parent(issue_number) if issue_number else None
    errors, add, remove = pipeline.v3_pr_rules(
        pull["head"], pull["base"], pull["title"], pull["body"], set(pull["labels"]), paths, "\n".join(diffs),
        config_module.get(config, "delivery.artifact_paths"), config_module.get(config, "security.sensitive_paths"),
        config_module.get(config, "tests.pending_marker"), set(issue["labels"]) if issue else set(),
        set(parent["labels"]) if parent else set(), mode=config_module.get(config, "project.mode"),
        flags_by_agent=_flags_by_agent(config))
    if args.content_dir:
        errors += _content_problems(client, config, args.content_dir, paths, pull["head"])
    else:
        print("::notice::conteúdo do PR indisponível: pendentes, rastreabilidade e guarda da stack não conferidos")
    for target in [args.pr] + ([issue_number] if issue else []):
        client.add_labels(target, sorted(add))
        for label in sorted(remove):
            client.remove_label(target, label)
    for error in errors:
        print(f"::error::{error}")
    if errors:
        raise BbError(f"regras do PR #{args.pr}: {len(errors)} problema(s)", EXIT_USAGE)
    print(f"Regras do PR #{args.pr}: em ordem.")
    return EXIT_OK


def _escaping_links(content):
    import os
    base = os.path.realpath(content)
    found = []
    for folder, dirs, files in os.walk(content):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in dirs + files:
            path = os.path.join(folder, name)
            if os.path.islink(path):
                target = os.path.realpath(path)
                if target != base and not target.startswith(base + os.sep):
                    found.append(os.path.relpath(path, content).replace(os.sep, "/"))
    return sorted(found)


def _content_problems(client, config, content, paths, head):
    """Checks on the PR head content, read as data by the target branch's code."""
    from . import acceptance, stack_guard, traceability
    escaping = _escaping_links(content)
    if escaping:  # nothing is read from a PR that points outside itself (runner files, secrets)
        return [f"link simbólico para fora do conteúdo do PR: {path}" for path in escaping]
    found = []
    for issue, location in acceptance.pending_marks(content, config_module.get(config, "tests.pending_marker")):
        current = client.issue(issue)
        if current and current["state"] == "closed":
            found.append(f"{location}: teste ainda marcado como pendente da #{issue}, que já foi concluída")
    pattern = config_module.get(config, "tests.test_pattern")
    found += [f"rastreabilidade: {problem}" for problem in traceability.problems(content, pattern, paths)]
    found += [f"guarda da stack: {problem}" for problem in stack_guard.problems(content)]
    return found


def _actor(client):
    return client.api("GET", "user")[1]["login"]  # recorded only; never an approval


def _candidate_ready(args):
    from . import delivery
    config, client, project = _context(args.raiz)
    result = delivery.candidate_ready(client, project, config, args.branch, args.rc_tag)
    print(f"Candidata {args.rc_tag}: épicos " + ", ".join(f"#{n}" for n in result["epics"]) +
          f"; PR da release #{result['pr']}.")
    return EXIT_OK


def _release_publish(args):
    from . import delivery, flows
    config, client, project = _context(args.raiz)
    content = args.content_dir or args.raiz
    if args.dry_run:
        result = delivery.publish(client, project, config, args.version, content, today=_today(), dry_run=True)
        print(f"Portão da release {args.version} em ordem (PR #{result['pr']}).")
        return EXIT_OK
    import os
    import subprocess
    profile_dir = config_module.get(config, "entrega.perfil")  # compilado | deploy (the shared profile scripts)
    script = os.path.join(args.raiz, ".bigbang", "esteira", "perfis", profile_dir, "scripts", "promover.sh")

    def promote(rc_tag, tag, target_sha):
        if config.get("_framework"):
            from . import framework
            framework.promote(args.raiz, rc_tag, tag, target_sha)
            return
        completed = subprocess.run(["bash", script], cwd=args.raiz, check=False,
                                   env={**os.environ, "RC_TAG": rc_tag, "TAG": tag, "TARGET_SHA": target_sha})
        if completed.returncode:
            raise BbError(f"promoção de {rc_tag} como {tag} falhou (veja o log acima)", EXIT_USAGE)

    result = delivery.publish(client, project, config, args.version, content, today=_today(), promote=promote)
    print(f"Release {args.version} publicada (PR #{result['pr']}); concluídos: "
          + (", ".join(f"#{n}" for n in result["done"]) or "nenhum")
          + "; com a flag desligada: " + (", ".join(f"#{n}" for n in result["dark"]) or "nenhum") + ".")
    for number in result.get("pending", []):
        print(f"::warning::épico #{number} publicado com a flag ligada, mas não concluído: confira com o dono")
    return EXIT_OK


def _release_maintenance(args):
    from . import delivery
    config = _load(args.raiz)
    client = gh.GitHub(config_module.get(config, "project.repository"))
    paths = []
    for file in client.pull_files(args.pr):
        paths.extend({file.get("previous_filename", file["filename"]), file["filename"]})
    result = delivery.publish_maintenance(client, config, args.pr, changed_paths=paths, dry_run=args.dry_run)
    if args.dry_run:
        print(f"Simulação: a manutenção #{args.pr} passa no portão; nada foi mesclado.")
        return EXIT_OK
    print(f"Manutenção #{args.pr} publicada na main; devolução para a develop: {result}.")
    return EXIT_OK


def _qa_reject(args):
    from . import delivery
    config, client, project = _context(args.raiz)
    task = delivery.correction_task(client, project, config, args.epic, args.reason, actor=_actor(client),
                                    dry_run=args.dry_run)
    if args.dry_run:
        print(f"Simulação: a reprovação do épico #{args.epic} está registrada; nada foi alterado.")
        return EXIT_OK
    print(f"Épico #{args.epic} reprovado; tarefa de correção #{task} criada a partir da release.")
    return EXIT_OK


def _qa_verdict(args):
    config, client, _ = _context(args.raiz)
    if args.agent not in config_module.get(config, "agents.names"):
        raise BbError(f"agente desconhecido: {args.agent} (declare em agents.names)", EXIT_USAGE)
    board.record_qa(client, config, args.epic, candidate=args.candidate, digest=args.digest, verdict=args.verdict,
                    approver=args.agent)
    print(f"QA {args.verdict} de {args.agent} registrado na #{args.epic} para {args.candidate}. Ele só vale se "
          "o agente não teve posse no épico nem nas tarefas dele.")
    return EXIT_OK


def _cleanup(args):
    from . import delivery
    config = _load(args.raiz)
    report = delivery.cleanup(gh.GitHub(config_module.get(config, "project.repository")), config,
                              dry_run=not args.apply)
    verb = "apagada" if args.apply else "seria apagada"
    for branch in report["deleted"]:
        print(f"branch {verb}: {branch}")
    for resource in report["locks"]:
        print(f"::warning::posse vencida há mais de uma semana (a trava fica; o dono decide): {resource}")
    for branch in report["outside"]:
        print(f"::warning::branch fora do padrão: {branch}")
    return EXIT_OK


def _controller(args):
    config, client, project = _context(args.raiz)
    payload = {}
    if args.payload:
        with open(args.payload, encoding="utf-8") as handle:
            payload = json.load(handle)
    for number, target in controller.handle(client, project, config, args.event, payload):
        print(f"#{number} → {target}")
    return EXIT_OK
