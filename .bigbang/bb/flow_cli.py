"""CLI of the v3 board and controller (ADR-0023/0026): bb board …, bb move and bb pipeline controller."""
import json

from . import board, controller, gh
from . import config as config_module
from .errors import EXIT_OK, EXIT_USAGE, BbError


def register(commands, pipeline_sub):
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

    p = pipeline_sub.add_parser("controller", help="v3: aplica um evento do GitHub ao quadro (uso da esteira)")
    p.add_argument("--event", required=True, help="nome do evento (issues, push, pull_request, schedule)")
    p.add_argument("--payload", help="arquivo JSON do evento (GITHUB_EVENT_PATH)")
    p.set_defaults(handler=_controller)


def _context(root):
    config = config_module.load(root)
    if config_module.get(config, "board.model") != "single":
        raise BbError("este projeto ainda usa os três painéis (board.model = three-boards): rode bb migrate board",
                      EXIT_USAGE)
    repository = config_module.get(config, "project.repository")
    client = gh.GitHub(repository)
    project = board.ProjectGraphQL(config_module.get(config, "board.owner"), config_module.get(config, "board.number"),
                                   repository, gh.graphql)
    return config, client, project


def _labels(args):
    config = config_module.load(args.raiz)
    created = board.ensure_labels(gh.GitHub(config_module.get(config, "project.repository")))
    print(f"Labels da v3: {created} criada(s); as demais já existiam.")
    return EXIT_OK


def _create(args):
    config = config_module.load(args.raiz)
    repository = config_module.get(config, "project.repository")
    owner = config_module.get(config, "board.owner")
    number = board.create_project(gh.graphql, owner, args.title, repository)
    board.ensure_fields(board.ProjectGraphQL(owner, number, repository, gh.graphql))
    print(f"Project único #{number} pronto para {repository} (15 estados, campos e visões Board/Table/Roadmap).")
    print("No bigbang.toml, seção [board]: model = \"single\", number = " + str(number))
    print(f"Variáveis do repositório: gh variable set PROJECT_OWNER --repo {repository} --body {owner}")
    print(f"                          gh variable set PROJECT_NUMBER --repo {repository} --body {number}")
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


def _controller(args):
    config, client, project = _context(args.raiz)
    payload = {}
    if args.payload:
        with open(args.payload, encoding="utf-8") as handle:
            payload = json.load(handle)
    for number, target in controller.handle(client, project, config, args.event, payload):
        print(f"#{number} → {target}")
    return EXIT_OK
