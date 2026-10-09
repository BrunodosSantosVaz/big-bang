"""Discussions and public read-only Projects defaults. Never broaden collaborator permissions."""
import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from . import github
from .errors import BbError
from .documentation import REPOSITORY, fail

WELCOME_MARKER = "<!-- bigbang:discussions:welcome:v1 -->"
DISCUSSIONS_QUERY = """query($owner:String!,$name:String!,$cursor:String){
 repository(owner:$owner,name:$name){id isPrivate hasDiscussionsEnabled usesCustomOpenGraphImage openGraphImageUrl
 discussionCategories(first:100){nodes{id name slug}}
 discussions(first:100,after:$cursor){nodes{id title body url} pageInfo{hasNextPage endCursor}}}}"""
PROJECT_QUERY = """query($owner:String!,$number:Int!){user(login:$owner){projectV2(number:$number){
 id number title public url shortDescription readme viewerCanUpdate
 fields(first:100){nodes{... on ProjectV2Field{id name dataType}
 ... on ProjectV2SingleSelectField{id name options{id name description}}}pageInfo{hasNextPage}}
 items(first:100){nodes{id content{__typename ... on Issue{title body url repository{nameWithOwner isPrivate}}
 ... on PullRequest{title body url repository{nameWithOwner isPrivate}} ... on DraftIssue{title body}}
 fieldValues(first:100){nodes{... on ProjectV2ItemFieldTextValue{text}
 ... on ProjectV2ItemFieldSingleSelectValue{name}}pageInfo{hasNextPage}}}pageInfo{hasNextPage}}}}}"""


def discussion_state(repository):
    if not REPOSITORY.fullmatch(repository):
        fail("repositório inválido")
    owner, name = repository.split("/")
    nodes, cursor = [], None
    while True:
        args = ["api", "graphql", "-f", "query=" + DISCUSSIONS_QUERY, "-f", "owner=" + owner, "-f", "name=" + name]
        if cursor:
            args += ["-f", "cursor=" + cursor]
        response = json.loads(github.run(*args))
        state = response["data"]["repository"]
        if not state:
            fail("repositório não acessível para configurar Discussions")
        discussions = state["discussions"]
        nodes += discussions["nodes"]
        if not discussions["pageInfo"]["hasNextPage"]:
            discussions["nodes"] = nodes
            return state
        cursor = discussions["pageInfo"]["endCursor"]


def welcome(repository, name, body=None, simulate=False):
    state = discussion_state(repository)
    if not state["hasDiscussionsEnabled"]:
        fail("Discussions desabilitado: habilite em Settings antes do primeiro post")
    matches = [item for item in state["discussions"]["nodes"] if WELCOME_MARKER in item["body"]]
    if matches:
        return matches[0]["url"]
    categories = state["discussionCategories"]["nodes"]
    category = next((item for slug in ("announcements", "general") for item in categories if item["slug"] == slug), None)
    if category is None:
        fail("Discussions sem categoria Announcements ou General; configure uma categoria antes de publicar")
    text = body or (
        f"# Bem-vindo ao {name}\n\nEste é o espaço para dúvidas, ideias e conversas sobre o projeto.\n\n"
        f"Acompanhe a [documentação](https://github.com/{repository}/wiki), os "
        f"[bugs e tarefas](https://github.com/{repository}/issues) e as "
        f"[releases](https://github.com/{repository}/releases). O estado de implementação deve ser consultado "
        "na Wiki e nas issues; este anúncio não declara funcionalidades ainda não entregues.\n\n"
        "Procure discussões existentes antes de abrir outra. Descreva versão, contexto e passos reproduzíveis. "
        "Nunca publique dados pessoais, credenciais ou segredos. Vulnerabilidades seguem o canal SECURITY.md. "
        "Decisões e trabalho de implementação são registrados em issues e PRs pela esteira.\n")
    if state.get("isPrivate"):
        text = text.replace(f"https://github.com/{repository}/wiki", f"https://github.com/{repository}#readme")
    text += "\n\n" + WELCOME_MARKER + "\n"
    if simulate:
        return f"[simulado] primeiro post de {name} em {repository}/discussions ({category['slug']})"
    query = """mutation($repo:ID!,$category:ID!,$title:String!,$body:String!){createDiscussion(input:{
     repositoryId:$repo,categoryId:$category,title:$title,body:$body}){discussion{url}}}"""
    result = json.loads(github.run("api", "graphql", "-f", "query=" + query, "-f", "repo=" + state["id"],
                                  "-f", "category=" + category["id"], "-f", "title=Boas-vindas à comunidade " + name,
                                  "-f", "body=" + text))
    return result["data"]["createDiscussion"]["discussion"]["url"]


def enable_discussions(repository):
    github.run("api", "--method", "PATCH", f"repos/{repository}", "-F", "has_discussions=true")


def project_state(owner, number):
    response = json.loads(github.run("api", "graphql", "-f", "query=" + PROJECT_QUERY,
                                     "-f", "owner=" + owner, "-F", "number=" + str(number)))
    board = response["data"]["user"]["projectV2"]
    if not board:
        fail("painel não encontrado ou sem acesso")
    if board["items"]["pageInfo"]["hasNextPage"] or board["fields"]["pageInfo"]["hasNextPage"] or any(
            item["fieldValues"]["pageInfo"]["hasNextPage"] for item in board["items"]["nodes"]):
        fail("painel excede o limite do inventário automático; audite todas as páginas antes de publicar")
    return board


def audit_digest(board):
    return hashlib.sha256(json.dumps(board, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def anonymous_project(owner, number):
    if not REPOSITORY.fullmatch(owner + "/project") or not isinstance(number, int) or number < 1:
        fail("painel público com identificador inválido")
    url = f"https://github.com/users/{owner}/projects/{number}"
    request = Request(url, headers={"User-Agent": "BigBang-documentation-check/2.0"})
    try:
        with urlopen(request, timeout=30) as response:
            if response.geturl().rstrip("/") != url:
                fail("painel público redireciona o visitante anônimo para outra página")
            text = response.read(8 * 1024 * 1024).decode("utf-8")
        def payload(name):
            match = re.search(r'<script[^>]*id="' + name + r'"[^>]*>(.*?)</script>', text, re.S)
            if not match:
                fail("GitHub não informou o acesso anônimo do painel; validação inconclusiva")
            return json.loads(match.group(1))
        board, privileges = payload("memex-data"), payload("memex-viewer-privileges")
    except (OSError, ValueError) as exc:
        fail(f"não foi possível confirmar leitura pública do painel ({type(exc).__name__})")
    if board.get("number") != number or not board.get("public") or privileges.get("role") != "read" or \
            privileges.get("canChangeProjectVisibility"):
        fail("painel não oferece exclusivamente leitura ao visitante anônimo")
    return {"url": url, "public": True, "role": "read", "canChangeProjectVisibility": False}


def ensure_public_project(repository, owner, number, publish=False, audit=None):
    board = project_state(owner, number)
    for item in board["items"]["nodes"]:
        content = item.get("content")
        if not content or content["__typename"] == "DraftIssue" or content.get("repository", {}).get("isPrivate"):
            fail("painel contém conteúdo privado, oculto ou rascunho: mantenha protegido antes de publicar")
    if board["public"]:
        return board.get("url", f"https://github.com/users/{owner}/projects/{number}")
    if not publish:
        fail(f"repositório público com painel privado: {owner}/projects/{number}")
    nonempty = bool(board["items"]["nodes"] or board.get("shortDescription") or board.get("readme"))
    if nonempty:
        reviewed = json.loads(Path(audit).read_text(encoding="utf-8")) if audit else {}
        if (reviewed.get("repositorio") != repository or reviewed.get("painel") != board["id"] or
                reviewed.get("sha256") != audit_digest(board) or not reviewed.get("sem_conteudo_sensivel") or
                not reviewed.get("revisor")):
            fail("painel existente exige auditoria revisada do conteúdo e dos campos no estado atual")
    query = """mutation($id:ID!){updateProjectV2(input:{projectId:$id,public:true}){projectV2{id public}}}"""
    github.run("api", "graphql", "-f", "query=" + query, "-f", "id=" + board["id"])
    # Only the visibility bit changes: no repository/project grants, collaborators or default role mutation.
    return board.get("url", f"https://github.com/users/{owner}/projects/{number}")


def verify(root, config):
    repository = config["projeto"]["repositorio"]
    state = discussion_state(repository)
    found = []
    if not state["hasDiscussionsEnabled"]:
        found.append("Discussions obrigatório desabilitado")
    elif not any(WELCOME_MARKER in item["body"] for item in state["discussions"]["nodes"]):
        found.append("falta o primeiro post da IA em Discussions")
    if config["projeto"].get("visibilidade") == "publico":
        for key in ("planejamento", "execucao", "bugs"):
            try:
                number = config["paineis"][key]
                if not number:
                    fail(f"painel obrigatório não configurado: {key}")
                anonymous_project(config["paineis"]["owner"], number)
            except BbError as exc:
                found.append(exc.message)
    return found
