"""CLI for the canonical documentation store and GitHub community settings."""
import json
from pathlib import Path

from . import community_public, documentation
from . import config as config_module
from .errors import EXIT_OK, EXIT_VERIFICATION_FAILED


def register(commands, parser_class):
    parser = commands.add_parser("documentacao", help="documentação local privada ou Wiki pública versionada")
    sub = parser.add_subparsers(dest="docs_command", parser_class=parser_class)
    for command in ("ler", "destino"):
        p = sub.add_parser(command, help="resolve um documento lógico sem duplicar documentação")
        p.add_argument("documento")
        p.set_defaults(handler=_read if command == "ler" else _path)
    p = sub.add_parser("preparar", help="confere HEAD/acesso e clona a Wiki nos metadados Git")
    p.add_argument("--repositorio")
    p.set_defaults(handler=_prepare)
    p = sub.add_parser("gravar", help="grava uma proposta documental; não publica na Wiki oficial")
    p.add_argument("documento")
    p.add_argument("--arquivo", required=True)
    p.set_defaults(handler=_write)
    p = sub.add_parser("propor", help="envia commit da Wiki para revisão junto ao PR de código")
    p.add_argument("--wiki", required=True, help="pasta Git com a proposta documental")
    p.add_argument("--branch", required=True, help="bigbang/proposta-ISSUE-slug")
    p.set_defaults(handler=_propose)
    p = sub.add_parser("validar", help="bloqueia cobertura incompleta, links ruins e documentação desatualizada")
    p.add_argument("--wiki", help="snapshot local (padrão: SHA do manifesto)")
    p.add_argument("--publicada", action="store_true", help="exige publicação confirmada no HEAD oficial da Wiki")
    p.add_argument("--comunidade", action="store_true", help="confere Discussions e visibilidade dos três painéis")
    p.set_defaults(handler=_validate)
    p = sub.add_parser("publicar", help="publica a proposta revisada com proteção contra alterações concorrentes")
    p.add_argument("--simular", action="store_true")
    p.set_defaults(handler=_publish)
    p = sub.add_parser("inventario", help="lista fontes reais e hashes para a matriz de rastreabilidade")
    p.set_defaults(handler=_inventory)

    parser = commands.add_parser("comunidade", help="padrões de Discussions, painéis e Social preview")
    sub = parser.add_subparsers(dest="community_command", parser_class=parser_class)
    p = sub.add_parser("primeiro-post", help="publica as boas-vindas da IA uma única vez por repositório")
    p.add_argument("--repositorio")
    p.add_argument("--nome")
    p.add_argument("--texto", help="arquivo com conteúdo factual revisado em português")
    p.add_argument("--simular", action="store_true")
    p.set_defaults(handler=_welcome)
    p = sub.add_parser("painel", help="audita, verifica ou publica um painel sem alterar permissões de edição")
    p.add_argument("acao", choices=("auditar", "validar", "publicar"))
    p.add_argument("numero", type=int)
    p.add_argument("--repositorio", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--auditoria", help="recibo da revisão do conteúdo atual antes de mudar a visibilidade")
    p.set_defaults(handler=_project)
    p = sub.add_parser("social-preview", help="mostra se a imagem personalizada foi instalada no GitHub")
    p.add_argument("--repositorio", required=True)
    p.set_defaults(handler=_preview)


def _read(args):
    print(documentation.read(args.raiz, args.documento), end="")
    return EXIT_OK


def _path(args):
    print(documentation.resolve(args.raiz, args.documento))
    return EXIT_OK


def _prepare(args):
    folder, state = documentation.prepare(args.raiz, args.repositorio)
    print(json.dumps({"pasta": str(folder), **state}, ensure_ascii=False, indent=2))
    return EXIT_OK


def _write(args):
    text = Path(args.arquivo).read_text(encoding="utf-8")
    if documentation.is_public(args.raiz):
        data = documentation.load(args.raiz)
        if args.documento not in data["paginas"]:
            import re
            documentation.safe_path(args.raiz, args.documento)
            page = re.sub(r"[^\w-]+", "-", str(Path(args.documento).with_suffix("")))
            if page in data["paginas"].values():
                documentation.fail("colisão de nomes: escolha explicitamente o destino no manifesto")
            data["paginas"][args.documento] = page
            Path(args.raiz, documentation.MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        folder, _ = documentation.prepare(args.raiz)
        if documentation.git(folder, "rev-parse", "HEAD") != data["wiki"]["commit"]:
            if documentation.git(folder, "status", "--porcelain"):
                documentation.fail("proposta local divergente; preserve o diff antes de trocar o commit")
            documentation.git(folder, "switch", "--detach", data["wiki"]["commit"])
        path = documentation.resolve(args.raiz, args.documento, folder)
    else:
        path = documentation.resolve(args.raiz, args.documento)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Proposta gravada em {path}; revise e use documentacao propor antes de entregar")
    return EXIT_OK


def _propose(args):
    import re
    data = documentation.load(args.raiz)
    folder = Path(args.wiki).resolve()
    if not re.fullmatch(r"bigbang/proposta-[A-Za-z0-9][A-Za-z0-9._-]*", args.branch):
        documentation.fail("use uma branch de proposta bigbang/proposta-ISSUE-slug")
    expected = f"https://github.com/{data['repositorio']}.wiki.git"
    if documentation.git(folder, "remote", "get-url", "origin") != expected:
        documentation.fail("proposta deve pertencer à Wiki do próprio projeto")
    if documentation.git(folder, "status", "--porcelain"):
        documentation.git(folder, "add", "--all")
        documentation.git(folder, "commit", "-m", "docs: update canonical documentation proposal")
    desired = documentation.git(folder, "rev-parse", "HEAD")
    documentation.git(folder, "merge-base", "--is-ancestor", data["wiki"]["base"], desired)
    data["wiki"]["commit"] = desired
    data["wiki"]["proposta"] = args.branch
    documentation.git(folder, "push", "origin", desired + ":refs/heads/" + args.branch)
    Path(args.raiz, documentation.MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Wiki proposta: {desired}; base: {data['wiki']['base']}. Revise o diff junto ao PR de código")
    return EXIT_OK


def _validate(args):
    found = documentation.validate(args.raiz, args.wiki, published=args.publicada)
    if args.comunidade:
        config = config_module.load(args.raiz, required=False)
        if config is None:
            config = documentation.load(args.raiz).get("configuracao_comunidade")
        if not config:
            found.append("configuração dos painéis do framework ausente")
        else:
            found += community_public.verify(args.raiz, config)
    for problem in found:
        print(problem)
    if not found:
        print("Documentação validada: inventário, rastreabilidade, conteúdo e navegação conferidos")
    return EXIT_VERIFICATION_FAILED if found else EXIT_OK


def _publish(args):
    print(documentation.publish(args.raiz, simulate=args.simular))
    return EXIT_OK


def _inventory(args):
    import hashlib
    data = documentation.load(args.raiz)
    print(json.dumps({path: hashlib.sha256(Path(args.raiz, path).read_bytes()).hexdigest()
                      for path in documentation.inventory(args.raiz, data)}, ensure_ascii=False, indent=2))
    return EXIT_OK


def _welcome(args):
    config = config_module.load(args.raiz, required=False) if not args.repositorio else None
    repository = args.repositorio or config["projeto"]["repositorio"]
    name = args.nome or (config and config["projeto"]["nome"]) or repository.split("/")[1]
    body = Path(args.texto).read_text(encoding="utf-8") if args.texto else None
    print(community_public.welcome(repository, name, body, args.simular))
    return EXIT_OK


def _project(args):
    if args.acao == "auditar":
        board = community_public.project_state(args.owner, args.numero)
        print(json.dumps({"repositorio": args.repositorio, "painel": board["id"],
                          "sha256": community_public.audit_digest(board), "conteudo": board,
                          "sem_conteudo_sensivel": False, "revisor": ""}, ensure_ascii=False, indent=2))
    else:
        print(community_public.ensure_public_project(args.repositorio, args.owner, args.numero,
                                                     args.acao == "publicar", args.auditoria))
    return EXIT_OK


def _preview(args):
    state = community_public.discussion_state(args.repositorio)
    print(json.dumps({"personalizada": state["usesCustomOpenGraphImage"], "url": state["openGraphImageUrl"],
                      "upload": "Settings → General → Social preview → Edit → Upload an image",
                      "formato": "PNG/JPG/GIF, menos de 1 MB, 1280×640 px"}, ensure_ascii=False, indent=2))
    return EXIT_OK
