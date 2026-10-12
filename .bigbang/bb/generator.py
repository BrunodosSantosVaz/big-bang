"""The generated layer (spec 5.1): what `bb gerar` writes and `bb verificar` compares (ADR-0007).

Sources, in composition order (a later layer may replace a file of an earlier one):
  .bigbang/esteira/sempre/arquivos/                 always (also before the Foundation)
  .bigbang/esteira/nucleo/arquivos/                 once the pipeline is installed (F5)
  .bigbang/esteira/perfis/<perfil>/arquivos/        idem
  .bigbang/esteira/perfis/deploy/alvos/<alvo>/arquivos/   idem, deploy profile only
  .bigbang/skills/bb-*/                             always, written to .agents/skills/ and .claude/skills/
  .bigbang/pipeline/skills/bb-*/                    v3 projects only: replaces the legacy folder of the same name
plus the marked blocks of AGENTS.md (always) and STACK.md (when it exists).
"""
import difflib
import os
import re
import tomllib

from . import config as config_module
from . import deploy_catalog, pipeline
from .errors import EXIT_INVALID_STATE, BbError
from .paths import framework_dir, framework_version, read_text, to_posix, write_text
from .render import TEMPLATE_SUFFIX, add_notice, has_notice, notice_text, substitute

AGENTS_FILE = "AGENTS.md"
STACK_FILE = "STACK.md"
AGENTS_BLOCK = re.compile(r"<!-- bigbang:inicio v[^ ]+ -->\n.*?<!-- bigbang:fim -->", re.S)
STACK_BLOCK_START = "<!-- bb:config:inicio -->"
STACK_BLOCK_END = "<!-- bb:config:fim -->"
SKILL_TARGETS = (".agents/skills", ".claude/skills")
FRAMEWORK_WORKFLOW_PREFIX = "bb-framework-"
IGNORED_NAMES = ("__pycache__", ".DS_Store")
ALWAYS_SENSITIVE = (".github/**", "tests/aceite/**", ".bigbang-docs.json", ".bigbang-producao.json", "STACK.md", "DESIGN.md", "PRODUTO.md", "bigbang.toml",
                    "flags.toml")


class Plan:
    """Expected content of every generated file, plus the generated files that must no longer exist."""

    def __init__(self, installed):
        self.installed = installed
        self.expected = {}  # relative posix path -> content
        self.sources = {}  # relative posix path -> where it comes from
        self.stale = []

    def add(self, path, content, source):
        self.expected[path] = content
        self.sources[path] = source


def pipeline_installed(root):
    """The pipeline counts as installed once .github/ holds any generated file other than the framework's own CI.

    Only the pipeline layers write into .github/ (the "sempre" layer is forbidden to), so this needs no state file.
    """
    return any(path.startswith(".github/") for path in _generated_candidates(root, installed=False))


def initial_context(root):
    """Values available before bigbang.toml exists: only the [bigbang] section."""
    example = os.path.join(framework_dir(root), "modelos", "bigbang.toml.exemplo")
    with open(example, "rb") as handle:
        origin = tomllib.load(handle)["bigbang"]["origem"]
    return {"bigbang": {"versao": framework_version(root), "origem": origin}}


def dependabot_entries(ecosystems):
    """YAML entries of the stack ecosystems: grouped, monthly, into main (they ship in a maintenance release)."""
    entries = []
    for ecosystem in ecosystems:
        entries.append(f"""  - package-ecosystem: "{ecosystem}"
    directory: "/"
    target-branch: "main"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
    labels: ["dependencies"]
    groups:
      {ecosystem}:
        patterns: ["*"]""")
    return "\n".join(entries)


def with_computed(config, root):
    """Config plus `gerado.*`: values computed in code, so templates stay free of conditional logic."""
    context = dict(config)
    systems = config.get("compilado", {}).get("sistemas", []) if config["entrega"]["perfil"] == "compilado" else []
    context["gerado"] = {"dependabot": dependabot_entries(config["entrega"].get("ecossistemas", [])),
                         "matriz_compilado": pipeline.build_matrix(systems),
                         "modo_trabalho": (
                             "**Modo autônomo.** Você conduz o trabalho de ponta a ponta, mas só dentro do contrato "
                             "`autonomy.toml` (alvos, riscos, portões, flags, WIP, tentativas, custo e janela de "
                             "publicação). Fora dele, o portão fica bloqueado para você e só a decisão registrada do "
                             "dono libera; nunca amplie o contrato. Antes de começar, rode `bb autonomy check`. Testes "
                             "antes do código, revisão independente, scanners e documentação continuam obrigatórios; "
                             "todo recibo registra que quem aprovou foi um agente. Veja o ADR-0025."
                             if config_module.get(config, "project.mode") == "autonomous" else
                             "**Modo Flash.** Escreva os testes antes do código e preserve a ordem teste → tarefas. "
                             "Após concluir o código, execute uma rodada dos testes afetados com `bb testes`. "
                             "Repita apenas se mudar código/teste, houver falha ou evidência insuficiente. "
                             "Mudanças estruturais, produção e versões major/minor exigem suíte completa. "
                             "Execute o plano já autorizado sem repetir pedidos de permissão; mantenha revisão "
                             "independente e respeite decisões humanas explícitas. Veja `.bigbang/processo/17-flash.md`."
                             if config_module.get(config, "projeto.modo") == "flash" else
                             "**Modo padrão.** Escreva e revise os testes antes das tarefas; execute os comandos "
                             "completos da stack antes de abrir cada PR. Veja `.bigbang/processo/06-execucao.md`."
                         )}
    if is_v3_pipeline(config):  # the v3 layer cites the v3 process, never the epic-branch documents
        for legacy, current in ((".bigbang/processo/17-flash.md", ".bigbang/pipeline/process/modes.md"),
                                (".bigbang/processo/06-execucao.md", ".bigbang/pipeline/process/execution.md")):
            context["gerado"]["modo_trabalho"] = context["gerado"]["modo_trabalho"].replace(legacy, current)
    context['gerado'].update(env_alvo='          # Perfil compilado: sem credenciais de deploy.', runner_deploy='ubuntu-24.04', preparar_alvo=':',
                             publicar_producao='''      - name: Publicar ({{entrega.perfil}})
        run: |
          gh auth setup-git
          {{gerado.preparar_alvo}}
          bash .bigbang/esteira/nucleo/scripts/publicar-producao.sh
        env:
          GH_TOKEN: ${{ secrets.PROJETO_TOKEN }}
          SIMULAR: 'false'
          BB_SHA_TESTADO: ${{ needs.testes-producao.outputs.sha }}
          # perfil deploy: o servidor de produção (variáveis e segredos do ambiente producao)
{{gerado.env_alvo}}''',
                             voltar_producao='''      - name: Voltar produção pelo alvo {{entrega.alvo}}
        run: |
          bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh
          bash .bigbang/esteira/perfis/deploy/alvos/{{entrega.alvo}}/scripts/alvo.sh voltar producao "$VERSAO"
          bash .bigbang/esteira/perfis/deploy/alvos/{{entrega.alvo}}/scripts/alvo.sh saude producao
        env:
          GH_TOKEN: ${{ github.token }}
          VERSAO: ${{ inputs.versao }}
{{gerado.env_alvo}}''')
    if config['entrega']['perfil'] == 'deploy':
        target, artifact = deploy_catalog.resolve(root, config)
        hash_artifact = artifact.identity == 'sha256'
        context['gerado']['preparar_alvo'] = 'bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh'
        context['gerado'].update(
            env_testes_candidata=("\n        env:\n          GH_TOKEN: ${{ github.token }}"
                                 if config_module.get(config, 'project.mode') == 'flash' else ''),
            artifact_permissions=('' if hash_artifact else '      packages: write'),
            artifact_preparacao=('' if hash_artifact else '''      - name: Entrar no GHCR
        run: printf '%s' "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
        env:
          GH_TOKEN: ${{ github.token }}
      # QEMU só trabalha quando deploy.plataformas tem uma arquitetura diferente da do runner (ex.: linux/arm64).
      - uses: docker/setup-qemu-action@99012661954931238ded8c8b007157a8430204e1 # v4.4.0
      - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1'''),
            artifact_build_name=('Construir pacote/arquivos e manifesto SHA-256 sem credenciais'
                                 if hash_artifact else 'Imagens (uma vez, por digest) e Trivy'),
            artifact_build_env=('' if hash_artifact else '''        env:
          TAG: ${{ needs.preparar.outputs.tag }}'''),
            artifact_upload=('' if not hash_artifact else '''      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: bb-candidata-${{ github.run_id }}
          path: candidata/
          if-no-files-found: error
          retention-days: 90'''),
            artifact_download_stage=('' if not hash_artifact else '''      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: bb-candidata-${{ github.run_id }}
          path: candidata'''),
            artifact_download_publish=('' if not hash_artifact else '''      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: bb-candidata-${{ github.run_id }}
          path: candidata'''),
            artifact_permissions_publish=('      packages: write\n      id-token: write\n      attestations: write' if not hash_artifact else ''),
            artifact_registro_steps=('' if hash_artifact else '''      - name: Entrar no GHCR
        run: printf '%s' "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
        env:
          GH_TOKEN: ${{ github.token }}
      - name: Registro das imagens e SBOM (CycloneDX) de cada uma
        run: bash .bigbang/esteira/perfis/deploy/scripts/candidata-sbom.sh
        env:
          IMAGEM: ${{ needs.imagem.outputs.imagem }}
      # Atestados de procedência: grátis em repositório público; em privado exigem GitHub Enterprise Cloud.
      - name: Atestado de procedência das imagens
        if: ${{ github.event.repository.visibility == 'public' }}
        uses: actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2
        with:
          subject-checksums: candidata/imagens.sha256'''),
            artifact_publish_env=('''        env:
          GH_TOKEN: ${{ github.token }}
          TAG: ${{ needs.preparar.outputs.tag }}
          IMAGEM: ${{ needs.imagem.outputs.imagem }}'''
                                if hash_artifact else '''        env:
          GH_TOKEN: ${{ github.token }}
          TAG: ${{ needs.preparar.outputs.tag }}
          IMAGEM: ${{ needs.imagem.outputs.imagem }}'''))
        context['gerado']['artefato_promover'] = artifact.scripts['promover']
        context['gerado']['artifact_rollback_conferir'] = ('''      - name: Manifesto e pacote registrados na Release
        id: imagem
        run: |
          mkdir -p "$RUNNER_TEMP/rollback-artefato"
          gh release download "$VERSAO" --repo "$GITHUB_REPOSITORY" --dir "$RUNNER_TEMP/rollback-artefato" --pattern manifesto.json --pattern manifesto.sha256 --pattern artefato.tar.gz
          (cd "$RUNNER_TEMP/rollback-artefato" && sha256sum -c manifesto.sha256)
          esperado=$(python3 -c 'import json,os; print(json.load(open(os.path.join(os.environ["RUNNER_TEMP"],"rollback-artefato/manifesto.json")))["artefato"]["sha256"])')
          atual=$(sha256sum "$RUNNER_TEMP/rollback-artefato/artefato.tar.gz" | cut -d' ' -f1)
          [[ "$atual" == "$esperado" ]] || { echo "::error::SHA-256 do pacote não confere"; exit 1; }
          echo "imagem=sha256:$esperado" >> "$GITHUB_OUTPUT"
          echo "Voltaria produção para $VERSAO: sha256:$esperado (migrações não são desfeitas)."
        env:
          GH_TOKEN: ${{ github.token }}
          VERSAO: ${{ inputs.versao }}'''
            if hash_artifact else '''      - name: Imagem registrada na Release
        id: imagem
        run: |
          imagem=$(gh release download "$VERSAO" --repo "$GITHUB_REPOSITORY" --pattern imagem.txt --output - | tr -d ' \t\r' | grep -v '^$' | paste -sd, -)
          [[ -n "$imagem" ]] || { echo "::error::$VERSAO não registra uma imagem"; exit 1; }
          echo "imagem=$imagem" >> "$GITHUB_OUTPUT"
          echo "Voltaria produção para $VERSAO: $imagem (migrações não são desfeitas)."
        env:
          GH_TOKEN: ${{ github.token }}
          VERSAO: ${{ inputs.versao }}''')
        context['gerado']['env_alvo'] = '\n'.join(
            '          ' + name + ': ${{ ' + kind + '.' + name + ' }}'
            for kind, names in (('vars', target.variables), ('secrets', target.secrets)) for name in names)
        if target.name == 'aws':
            context['gerado']['publicar_producao'] = '''      - name: Autenticar na AWS via OIDC
        uses: aws-actions/configure-aws-credentials@ececac4a0913210359f1eb7dd4a942526ea9e201 # v4.1.0
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
          audience: sts.amazonaws.com
      - name: Publicar ({{entrega.perfil}})
        run: |
          gh auth setup-git
          {{gerado.preparar_alvo}}
          bash .bigbang/esteira/nucleo/scripts/publicar-producao.sh
        env:
          GH_TOKEN: ${{ secrets.PROJETO_TOKEN }}
          SIMULAR: 'false'
          BB_SHA_TESTADO: ${{ needs.testes-producao.outputs.sha }}
{{gerado.env_alvo}}'''
            context['gerado']['voltar_producao'] = '''      - name: Autenticar na AWS via OIDC
        uses: aws-actions/configure-aws-credentials@ececac4a0913210359f1eb7dd4a942526ea9e201 # v4.1.0
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
          audience: sts.amazonaws.com
      - name: Voltar produção pelo alvo {{entrega.alvo}}
        run: |
          bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh
          bash .bigbang/esteira/perfis/deploy/alvos/{{entrega.alvo}}/scripts/alvo.sh voltar producao "$VERSAO"
          bash .bigbang/esteira/perfis/deploy/alvos/{{entrega.alvo}}/scripts/alvo.sh saude producao
        env:
          GH_TOKEN: ${{ github.token }}
          VERSAO: ${{ inputs.versao }}
{{gerado.env_alvo}}'''
        elif target.name == 'personalizado':
            context['gerado']['env_alvo'] = '\n'.join(
                '          ' + name + ': ${{ vars.' + name + ' }}' for name in target.variables)
            context['gerado']['publicar_producao'] = '''      - name: Preparar publicação personalizada
        id: preparar-publicacao
        run: |
          gh auth setup-git
          BB_PUBLICACAO_PERSONALIZADA=preparar bash .bigbang/esteira/nucleo/scripts/publicar-producao.sh
        env:
          GH_TOKEN: ${{ secrets.PROJETO_TOKEN }}
          SIMULAR: 'false'
          BB_SHA_TESTADO: ${{ needs.testes-producao.outputs.sha }}
      - name: Retirar credencial do checkout antes dos scripts do projeto
        if: ${{ steps.preparar-publicacao.outputs.retomada != 'true' }}
        run: git config --local --unset-all http.https://github.com/.extraheader || true
      - name: Executar scripts personalizados sem credenciais
        if: ${{ steps.preparar-publicacao.outputs.retomada != 'true' }}
        run: |
          bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh
          bash .bigbang/esteira/perfis/deploy/scripts/publicar-personalizado.sh
        env:
          RC_TAG: ${{ steps.preparar-publicacao.outputs.rc_tag }}
          TAG: ${{ steps.preparar-publicacao.outputs.tag }}
          TARGET_SHA: ${{ steps.preparar-publicacao.outputs.target_sha }}
          IMAGEM: ${{ steps.preparar-publicacao.outputs.imagem }}
{{gerado.env_alvo}}
      - name: Finalizar publicação personalizada
        run: |
          gh auth setup-git
          BB_PUBLICACAO_PERSONALIZADA=finalizar bash .bigbang/esteira/nucleo/scripts/publicar-producao.sh
        env:
          GH_TOKEN: ${{ secrets.PROJETO_TOKEN }}
          SIMULAR: 'false'
          RETOMADA: ${{ steps.preparar-publicacao.outputs.retomada }}
          RC_TAG: ${{ steps.preparar-publicacao.outputs.rc_tag }}
          TAG: ${{ steps.preparar-publicacao.outputs.tag }}
          TARGET_SHA: ${{ steps.preparar-publicacao.outputs.target_sha }}
          IMAGEM: ${{ steps.preparar-publicacao.outputs.imagem }}'''
            context['gerado']['voltar_producao'] = '''      - name: Voltar produção pelo alvo personalizado sem credenciais
        run: |
          bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh
          bash .bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh voltar producao "$VERSAO" "$IMAGEM"
          bash .bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh saude producao
        env:
          VERSAO: ${{ inputs.versao }}
          IMAGEM: ${{ needs.conferir.outputs.imagem }}
{{gerado.env_alvo}}'''.replace('{{gerado.env_alvo}}', context['gerado']['env_alvo'])
            if hash_artifact:
                context['gerado']['publicar_producao'] = '''      - name: Preparar publicação personalizada
        id: preparar-publicacao
        run: |
          gh auth setup-git
          BB_PUBLICACAO_PERSONALIZADA=preparar bash .bigbang/esteira/nucleo/scripts/publicar-producao.sh
        env:
          GH_TOKEN: ${{ secrets.PROJETO_TOKEN }}
          SIMULAR: 'false'
          BB_SHA_TESTADO: ${{ needs.testes-producao.outputs.sha }}
      - name: Retirar credencial do checkout antes dos scripts do projeto
        if: ${{ steps.preparar-publicacao.outputs.retomada != 'true' }}
        run: git config --local --unset-all http.https://github.com/.extraheader || true
      - name: Executar scripts personalizados sem credenciais
        if: ${{ steps.preparar-publicacao.outputs.retomada != 'true' }}
        run: |
          bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh
          bash .bigbang/esteira/perfis/deploy/scripts/publicar-personalizado.sh
        env:
          RC_TAG: ${{ steps.preparar-publicacao.outputs.rc_tag }}
          TAG: ${{ steps.preparar-publicacao.outputs.tag }}
          TARGET_SHA: ${{ steps.preparar-publicacao.outputs.target_sha }}
          MANIFESTO: ${{ steps.preparar-publicacao.outputs.manifesto }}
{{gerado.env_alvo}}
      - name: Finalizar publicação personalizada
        run: |
          gh auth setup-git
          BB_PUBLICACAO_PERSONALIZADA=finalizar bash .bigbang/esteira/nucleo/scripts/publicar-producao.sh
        env:
          GH_TOKEN: ${{ secrets.PROJETO_TOKEN }}
          SIMULAR: 'false'
          RETOMADA: ${{ steps.preparar-publicacao.outputs.retomada }}
          RC_TAG: ${{ steps.preparar-publicacao.outputs.rc_tag }}
          TAG: ${{ steps.preparar-publicacao.outputs.tag }}
          TARGET_SHA: ${{ steps.preparar-publicacao.outputs.target_sha }}
          MANIFESTO: ${{ steps.preparar-publicacao.outputs.manifesto }}'''
                context['gerado']['publicar_producao'] = context['gerado']['publicar_producao'].replace(
                    'bash .bigbang/esteira/perfis/deploy/scripts/publicar-personalizado.sh',
                    'bash .bigbang/' + artifact.scripts['promover'])
                context['gerado']['voltar_producao'] = '''      - name: Baixar e conferir manifesto de rollback
        run: |
          mkdir -p candidata
          gh release download "$VERSAO" --repo "$GITHUB_REPOSITORY" --dir candidata --pattern manifesto.json --pattern manifesto.sha256 --pattern artefato.tar.gz
          (cd candidata && sha256sum -c manifesto.sha256)
          esperado=$(python3 -c 'import json; print(json.load(open("candidata/manifesto.json"))["artefato"]["sha256"])')
          atual=$(sha256sum candidata/artefato.tar.gz | cut -d' ' -f1)
          [[ "$atual" == "$esperado" ]] || { echo "::error::SHA-256 do pacote não confere"; exit 1; }
        env:
          GH_TOKEN: ${{ github.token }}
          VERSAO: ${{ inputs.versao }}
      - name: Voltar versão pelo alvo personalizado sem credenciais
        run: |
          bash .bigbang/esteira/perfis/deploy/scripts/preparar-alvo.sh
          bash .bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh voltar producao "$VERSAO" candidata/manifesto.json
          bash .bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh saude producao
        env:
          VERSAO: ${{ inputs.versao }}
{{gerado.env_alvo}}'''.replace('{{gerado.env_alvo}}', context['gerado']['env_alvo'])
        context['gerado']['runner_deploy'] = config_module.get(config, 'deploy.runner')
        context['gerado']['artefato_construir'] = artifact.scripts['construir']
        context['gerado']['artefato_candidata'] = artifact.scripts['candidata']
    context['gerado']['publicar_producao'] = (context['gerado']['publicar_producao']
                                              .replace('{{entrega.perfil}}', config['entrega']['perfil'])
                                              .replace('{{gerado.preparar_alvo}}', context['gerado']['preparar_alvo'])
                                              .replace('{{gerado.env_alvo}}', context['gerado']['env_alvo']))
    if config['entrega']['perfil'] == 'deploy':
        context['gerado']['voltar_producao'] = (context['gerado']['voltar_producao']
                                                .replace('{{entrega.alvo}}', target.name)
                                                .replace('{{gerado.env_alvo}}', context['gerado']['env_alvo']))
    return context


def build_plan(root, install_pipeline=False, framework=False):
    from . import framework as own
    config = own.load(root, required=True) if framework else config_module.load(root, required=False)
    if config is not None and config.get("_framework"):
        return framework_plan(root, config)
    if install_pipeline and config is None:
        raise BbError("a esteira só pode ser gerada depois do bb init (falta o bigbang.toml)", EXIT_INVALID_STATE)
    installed = config is not None and (install_pipeline or pipeline_installed(root))
    if config is not None and config['entrega']['perfil'] == 'deploy':
        deploy_catalog.resolve(root, config)
    context = with_computed(config, root) if config is not None else initial_context(root)
    version = framework_version(root)
    plan = Plan(installed)

    for layer in _layers(config, installed):
        folder = "files" if layer.startswith("pipeline/") else "arquivos"
        _add_tree(plan, root, os.path.join(framework_dir(root), *layer.split("/"), folder), "", context, version)
        if layer == "esteira/sempre" and any(path.startswith(".github/") for path in plan.expected):
            raise BbError(".bigbang/esteira/sempre/ não pode gerar arquivos em .github/ (só a esteira gera)",
                          EXIT_INVALID_STATE)
    _add_skills(plan, root, context, version, v3=is_v3_pipeline(config))
    _add_agents_md(plan, root, context, version, founded=config is not None, v3=is_v3_pipeline(config))
    if config is not None:
        _add_stack_md(plan, root, config, version)
    plan.stale = sorted(set(_generated_candidates(root, installed)) - set(plan.expected))
    return plan


def framework_plan(root, config):
    """Same v3 layers, namespaced workflows only; the three transitional workflows remain owned by Git."""
    from . import framework
    plan = Plan(False)
    context = with_computed(config, root)
    version = framework_version(root)
    _add_tree(plan, root, os.path.join(framework_dir(root), "esteira/sempre/arquivos"), "", context, version)
    _add_skills(plan, root, context, version)
    _add_agents_md(plan, root, initial_context(root), version, founded=False)
    for layer in ("pipeline/core", "pipeline/profiles/compiled", "pipeline/framework"):
        folder = os.path.join(framework_dir(root), layer, "files/.github/workflows")
        temporary = Plan(False)
        _add_tree(temporary, root, folder, ".github/workflows/", context, version)
        for path, content in temporary.expected.items():
            name = os.path.basename(path)
            if name == "bb-ci.yml":
                continue  # Framework CI preserves Docker, shellcheck and gitleaks, aggregated by gate.
            destination = ".github/workflows/" + name.replace("bb-", FRAMEWORK_WORKFLOW_PREFIX, 1)
            content = content.replace("group: bb-", "group: bb-framework-")
            content = content.replace("workflows: [CI]", "workflows: [Framework gate]")
            if not re.search(r"^concurrency:", content, re.M):
                group = os.path.basename(destination).removesuffix(".yml")
                content = content.replace("\njobs:\n", f"\nconcurrency:\n  group: {group}\n  cancel-in-progress: false\n\njobs:\n")
            # Put the repository check on every job's own condition (including always() jobs).
            jobs = content.index("\njobs:\n") + len("\njobs:\n")
            header, body = content[:jobs], content[jobs:]
            marks = list(re.finditer(r"^  [\w-]+:[ \t]*(?:#.*)?$", body, re.M))
            sections = []
            for mark, following in zip(marks, marks[1:] + [None]):
                section = body[mark.start():following.start() if following else len(body)]
                found = re.search(r"^    if: (.+)$", section, re.M)
                condition = "github.repository == '" + framework.ORIGIN + "'"
                if found:
                    value = found[1].strip()
                    if value.startswith("${{") and value.endswith("}}"):
                        value = value[3:-2].strip()
                    condition += " && (" + value + ")"
                    section = section[:found.start()] + "    if: " + condition + section[found.end():]
                else:
                    section = section.replace("\n", "\n    if: " + condition + "\n", 1)
                sections.append(section)
            content = header + "".join(sections)
            plan.add(destination, content, temporary.sources[path])
    legacy = {".github/workflows/" + name for name in
              ("bb-framework-ci.yml", "bb-framework-faxina.yml", "bb-framework-release.yml")}
    candidates = {path for path in _generated_candidates(root, installed=True)
                  if path not in legacy}
    plan.stale = sorted(candidates - set(plan.expected))
    return plan


def is_v3_pipeline(config):
    """The v3 tree (.bigbang/pipeline) is generated for the grouping workflow (ADR-0022)."""
    return config is not None and config_module.get(config, "workflow.model") == "grouping"


def _layers(config, installed):
    layers = ["esteira/sempre"]
    if installed and is_v3_pipeline(config):
        layers.append("pipeline/core")
        layers.append(f"pipeline/profiles/{config_module.get(config, 'delivery.profile')}")
        return layers
    if installed:
        perfil = config["entrega"]["perfil"]
        layers += ["esteira/nucleo", f"esteira/perfis/{perfil}"]
        if perfil == "deploy":
            artifact = config['deploy'].get('artefato', 'imagem')
            layers.append(f"esteira/perfis/deploy/artefatos/{artifact}")
            layers.append(f"esteira/perfis/deploy/alvos/{config['entrega']['alvo']}")
    return layers


def _walk(folder):
    for current, subfolders, names in os.walk(folder):
        subfolders[:] = sorted(s for s in subfolders if s not in IGNORED_NAMES)
        for name in sorted(names):
            if name not in IGNORED_NAMES:
                yield os.path.join(current, name)


def _add_tree(plan, root, folder, destination_prefix, context, version):
    for path in _walk(folder):
        relative = to_posix(os.path.relpath(path, folder))
        source = to_posix(os.path.relpath(path, root))
        destination = destination_prefix + relative
        content = read_text(path)
        if destination.endswith(TEMPLATE_SUFFIX):
            destination = destination[:-len(TEMPLATE_SUFFIX)]
            content = substitute(content, context, source)
        plan.add(destination, add_notice(content, destination, version, source), source)


def _add_skills(plan, root, context, version, v3=False):
    """Framework skills for every project; a v3 project gets the v3 version of the adapted ones and the v3-only
    skills from .bigbang/pipeline/skills/ (a folder there replaces the legacy folder of the same name)."""
    sources = {}
    bases = [os.path.join(framework_dir(root), "skills")]
    if v3:
        bases.append(os.path.join(framework_dir(root), "pipeline", "skills"))
    for base in bases:
        for name in sorted(os.listdir(base)):
            folder = os.path.join(base, name)
            if not os.path.isdir(folder) or name in IGNORED_NAMES:
                continue
            if not name.startswith("bb-"):
                raise BbError(f"{os.path.relpath(folder, root)}: skills do framework precisam do prefixo bb-",
                              EXIT_INVALID_STATE)
            sources[name] = folder
    for name, folder in sorted(sources.items()):
        for target in SKILL_TARGETS:
            _add_tree(plan, root, folder, f"{target}/{name}/", context, version)


def agents_block(root, context, version, founded, v3=False):
    source = (".bigbang/pipeline/AGENTS.base.md" if v3 else ".bigbang/AGENTS.base.md") if founded else \
        ".bigbang/AGENTS.inicial.md"
    body = substitute(read_text(os.path.join(root, *source.split("/"))), context, source)
    return (f"<!-- bigbang:inicio v{version} -->\n<!-- {notice_text(version, source)} -->\n\n"
            f"{body.rstrip()}\n\n<!-- bigbang:fim -->")


def _add_agents_md(plan, root, context, version, founded, v3=False):
    block = agents_block(root, context, version, founded, v3)
    path = os.path.join(root, AGENTS_FILE)
    if os.path.exists(path):
        current = read_text(path)
        found = AGENTS_BLOCK.findall(current)
        if len(found) > 1:
            raise BbError("AGENTS.md tem mais de um bloco do Big Bang; deixe só um", EXIT_INVALID_STATE)
        content = AGENTS_BLOCK.sub(lambda _: block, current) if found else f"{block}\n\n{current}"
    else:
        project = read_text(os.path.join(framework_dir(root), "modelos", "AGENTS.projeto.md"))
        content = f"{block}\n\n{project}"
    plan.add(AGENTS_FILE, content, "bloco do .bigbang/AGENTS.*.md")


def stack_block(config, version):
    entrega, seguranca = config["entrega"], config["seguranca"]
    lines = [STACK_BLOCK_START, f"<!-- {notice_text(version, 'bigbang.toml')} -->", ""]
    alvo = f" · **Alvo:** `{entrega['alvo']}`" if entrega["alvo"] else ""
    lines += [f"**Perfil de entrega:** `{entrega['perfil']}`{alvo}", ""]
    lines += ["**Caminhos do artefato** (mudança aqui exige release):", ""]
    lines += [f"- `{item}`" for item in entrega["caminhos_artefato"]] + [""]
    lines += ["**Zonas sensíveis** (revisão humana):", ""]
    lines += [f"- `{item}`" for item in seguranca["zonas_sensiveis"]]
    lines += ["- Sempre: " + ", ".join(f"`{item}`" for item in ALWAYS_SENSITIVE)
              + " e os arquivos de dependência da stack.", "", STACK_BLOCK_END]
    return "\n".join(lines)


def _add_stack_md(plan, root, config, version):
    if config["projeto"].get("visibilidade") == "publico":
        return  # Public documentation belongs to the separately reviewed Wiki Git history.
    path = os.path.join(root, STACK_FILE)
    if not os.path.exists(path):
        return  # STACK.md is born in F2
    current = read_text(path)
    if current.count(STACK_BLOCK_START) != 1 or current.count(STACK_BLOCK_END) != 1:
        raise BbError(f"STACK.md precisa ter uma vez {STACK_BLOCK_START} e {STACK_BLOCK_END}", EXIT_INVALID_STATE)
    start = current.index(STACK_BLOCK_START)
    end = current.index(STACK_BLOCK_END) + len(STACK_BLOCK_END)
    plan.add(STACK_FILE, current[:start] + stack_block(config, version) + current[end:], "bloco do bigbang.toml")


def _generated_candidates(root, installed):
    """Files on disk that belong to the generated layer (to find the stale ones)."""
    github = os.path.join(root, ".github")
    if os.path.isdir(github):
        for path in _walk(github):
            relative = to_posix(os.path.relpath(path, root))
            name = os.path.basename(path)
            if name.startswith(FRAMEWORK_WORKFLOW_PREFIX) and relative.startswith(".github/workflows/"):
                if installed:
                    yield relative  # F5 removes the framework's own CI from the project
                continue
            if name.startswith("bb-") or _text_has_notice(path):
                yield relative
    for target in SKILL_TARGETS:
        folder = os.path.join(root, *target.split("/"))
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.startswith("bb-"):
                    for path in _walk(os.path.join(folder, name)):
                        yield to_posix(os.path.relpath(path, root))
    agents = os.path.join(root, ".claude", "agents")
    if os.path.isdir(agents):
        for name in os.listdir(agents):
            if name.startswith("bb-"):
                yield f".claude/agents/{name}"
    if os.path.isfile(os.path.join(root, ".claude", "settings.json")):
        yield ".claude/settings.json"  # JSON has no generated notice; this path is reserved by the spec.


def _text_has_notice(path):
    try:
        return has_notice(read_text(path))
    except UnicodeDecodeError:
        return False  # binary files (images) are never generated


def changes(plan, root):
    """List of (kind, path): criar, alterar or remover."""
    result = []
    for path, content in sorted(plan.expected.items()):
        disk = os.path.join(root, *path.split("/"))
        if not os.path.exists(disk):
            result.append(("criar", path))
        elif read_text(disk) != content:
            result.append(("alterar", path))
    result += [("remover", path) for path in plan.stale]
    return result


def diff(plan, root, path):
    disk = os.path.join(root, *path.split("/"))
    before = read_text(disk).splitlines(keepends=True) if os.path.exists(disk) else []
    after = plan.expected.get(path, "").splitlines(keepends=True)
    return "".join(difflib.unified_diff(before, after, f"a/{path}", f"b/{path}"))


def apply(plan, root):
    applied = changes(plan, root)
    for kind, path in applied:
        disk = os.path.join(root, *path.split("/"))
        if kind == "remover":
            os.remove(disk)
            _remove_empty_parents(os.path.dirname(disk), root)
        else:
            write_text(disk, plan.expected[path])
    return applied


def _remove_empty_parents(folder, root):
    root = os.path.abspath(root)
    folder = os.path.abspath(folder)
    while folder != root and os.path.isdir(folder) and not os.listdir(folder):
        os.rmdir(folder)
        folder = os.path.dirname(folder)
