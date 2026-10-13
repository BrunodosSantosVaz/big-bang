"""The single table of Big Bang v3 names (ADR-0024): English identifiers, with the v2 Portuguese names as aliases.

Every translation goes through this module, so a legacy name is never spelled in two places. Legacy projects keep
their Portuguese configuration, labels and branches; v3 projects use the English ones. Nothing here touches files.
"""

# --- bigbang.toml: sections and keys (legacy -> v3) ------------------------------------------------------------------

SECTIONS = {
    "bigbang": "bigbang", "projeto": "project", "entrega": "delivery", "compilado": "compiled", "deploy": "deploy",
    "comandos": "commands", "testes": "tests", "seguranca": "security", "paineis": "board", "ias": "agents",
    "flags": "flags",
}
KEYS = {
    "bigbang": {"versao": "version", "origem": "origin"},
    "projeto": {"nome": "name", "slug": "slug", "dono": "owner", "repositorio": "repository",
                "visibilidade": "visibility", "licenca": "license", "modo": "mode"},
    "entrega": {"perfil": "profile", "alvo": "target", "caminhos_artefato": "artifact_paths",
                "arquivo_versao": "version_file", "ecossistemas": "ecosystems"},
    "compilado": {"sistemas": "systems"},  # plus build_<system>, identical in both
    "deploy": {"artefato": "artifact", "imagem": "image", "url_staging": "staging_url",
               "url_producao": "production_url", "smoke": "smoke", "servicos": "services",
               "plataformas": "platforms", "caminho_saude": "health_path", "servico_migrar": "migrate_service",
               "servico_checar": "check_service", "runner": "runner", "preparar_rede": "network_setup",
               "script_publicar": "custom_publish_script", "script_migrar": "custom_migrate_script",
               "script_saude": "custom_health_script", "script_voltar": "custom_rollback_script",
               "variaveis_personalizado": "custom_variables"},
    "comandos": {"instalar": "install", "lint": "lint", "tipos": "types", "testes": "test",
                 "testes_aceite": "acceptance_test", "arquitetura": "architecture", "cobertura": "coverage",
                 "build": "build", "testes_alterados": "affected_tests"},
    "testes": {"cobertura_minima": "min_coverage", "marca_pendente": "pending_marker",
               "padrao_teste": "test_pattern", "caminhos_estruturais": "structural_paths"},
    "seguranca": {"nivel_asvs": "asvs_level", "banco_no_navegador": "browser_database",
                  "zonas_sensiveis": "sensitive_paths"},
    "paineis": {"owner": "owner", "planejamento": "planning", "execucao": "execution", "bugs": "bugs"},
    "ias": {"nomes": "names", "tarefas_por_ia": "tasks_per_agent", "trava_expira_horas": "lease_hours",
            "espera_confirmacao_segundos": "confirm_seconds"},
    "flags": {"validade_maxima_dias": "max_age_days"},
}
# Values that are identifiers too (legacy -> v3), by legacy section.key.
VALUES = {
    "projeto.modo": {"padrao": "normal", "flash": "flash"},
    "projeto.visibilidade": {"privado": "private", "publico": "public"},
    "entrega.perfil": {"compilado": "compiled", "deploy": "deploy"},
    "entrega.alvo": {"personalizado": "custom"},
    "deploy.artefato": {"imagem": "image", "pacote": "package", "estatico": "static"},
}
# Keys that only exist in v3 files: (section, key) -> default when a legacy file is read.
V3_ONLY = {
    ("board", "model"): "three-boards",
    ("board", "number"): 0,
    ("board", "labels"): "legacy",
    ("workflow", "model"): "epic-branch",
}
# v3-only values with the closest legacy behavior (legacy code paths read the Portuguese view).
V3_VALUES_IN_LEGACY_VIEW = {"projeto.modo": {"autonomous": "flash"}}

# --- CLI: commands and options (legacy -> v3, scoped by parent command; legacy names stay as aliases) ---------------

CLI = {
    (None, "alvos"): "targets", (None, "config"): "config", (None, "gerar"): "generate", (None, "init"): "init",
    (None, "verificar"): "verify", (None, "testes"): "test", (None, "assumir"): "claim", (None, "liberar"): "unclaim",
    (None, "status"): "status", (None, "aceite"): "acceptance", (None, "decisao"): "decision",
    (None, "revisao"): "review", (None, "checklist"): "checklist", (None, "esteira"): "pipeline",
    (None, "documentacao"): "docs", (None, "comunidade"): "community", (None, "atualizar"): "update",
    (None, "pacote"): "package", (None, "checksums"): "checksums", (None, "migrar"): "migrate",
    ("config", "get"): "get", ("aceite", "liberar"): "unpend", ("revisao", "aprovar"): "approve",
    ("checklist", "producao"): "production",
    ("documentacao", "ler"): "read", ("documentacao", "destino"): "path", ("documentacao", "preparar"): "prepare",
    ("documentacao", "gravar"): "write", ("documentacao", "propor"): "propose", ("documentacao", "validar"): "validate",
    ("documentacao", "publicar"): "publish", ("documentacao", "inventario"): "inventory",
    ("comunidade", "primeiro-post"): "welcome-post", ("comunidade", "painel"): "board",
    ("comunidade", "social-preview"): "social-preview",
    ("esteira", "formulario"): "form", ("esteira", "pronto"): "ready", ("esteira", "severidade"): "severity",
    ("esteira", "tarefas"): "tasks", ("esteira", "dependencias"): "dependencies", ("esteira", "branch"): "branch",
    ("esteira", "regra-branch"): "branch-rule", ("esteira", "titulo"): "title", ("esteira", "versao"): "version",
    ("esteira", "changelog"): "changelog", ("esteira", "artefato"): "artifact", ("esteira", "sensivel"): "sensitive",
    ("esteira", "documentacao"): "docs", ("esteira", "comunidade"): "community",
    ("esteira", "so-liberacao"): "only-unpend", ("esteira", "nome-candidata"): "candidate-name",
    ("esteira", "nome-producao"): "production-name", ("esteira", "trava-aceite"): "acceptance-lock",
    ("esteira", "pendentes"): "pending", ("esteira", "rastreabilidade"): "traceability",
    ("esteira", "guarda-stack"): "stack-guard", ("esteira", "osv-avaliar"): "osv-check", ("esteira", "rls"): "rls",
    ("esteira", "gravar-versao"): "write-version", ("esteira", "resumo-posses"): "claims-summary",
    ("esteira", "marcar-paradas"): "mark-stale", ("esteira", "liberar-posse"): "release-claim",
    ("esteira", "registrar-push"): "record-push", ("esteira", "limpar-deployments"): "clean-deployments",
}
OPTIONS = {
    "--raiz": "--root", "--simular": "--dry-run", "--esteira": "--pipeline", "--nome": "--name", "--dono": "--owner",
    "--repositorio": "--repository", "--visibilidade": "--visibility", "--licenca": "--license", "--modo": "--mode", "--fluxo": "--workflow",
    "--sem-github": "--no-github", "--fase": "--phase", "--versao": "--release", "--completo": "--full",
    "--forcar": "--force-claim", "--frase": "--quote", "--pasta": "--folder", "--ia": "--agent",
    "--relatorio": "--report", "--dados": "--content-dir", "--confirmo-migracao": "--confirm-migration",
    "--sem-atestacao": "--no-attestation", "--saida": "--output", "--notas": "--notes", "--escrever": "--write",
    "--arquivo": "--file", "--publicada": "--published", "--comunidade": "--community", "--texto": "--text",
    "--auditoria": "--audit", "--titulo-criado": "--created-title", "--antes": "--before", "--atual": "--current",
    "--data": "--date", "--pr-de-teste": "--test-pr", "--visibilidade-remota": "--remote-visibility",
    "--aprovado": "--approved", "--mudados": "--changed", "--padrao-dos-dados": "--content-test-pattern",
    "--aplicar": "--apply",
}
COMMANDS = {v3: [legacy] if legacy != v3 else [] for (parent, legacy), v3 in CLI.items() if parent is None}


def cli_name(parent, legacy):
    """add_parser keyword arguments: the v3 name, with the legacy name as an alias when it differs."""
    v3 = CLI[(parent, legacy)]
    return {"name": v3, "aliases": [legacy] if legacy != v3 else []}


def cli_option(legacy):
    """add_argument flags: the v3 flag first (shown in help), the legacy flag as an alias."""
    v3 = OPTIONS.get(legacy, legacy)
    return (v3, legacy) if v3 != legacy else (legacy,)


# --- GitHub: labels, branches, workflows, checks, environment, secrets (legacy -> v3) -------------------------------

LABELS = {
    "epic": "type:epic", "task": "type:task", "teste-aceite": "type:test", "documentacao": "type:docs",
    "bug": "type:bug", "fundacao": "type:foundation", "seguranca": "security", "sem-release": "no-release",
    "com-prototipo": "prototype:required", "sem-prototipo": "prototype:waived",
    "testes-revisao-ia": "tests-review:ai", "testes-revisao-humana": "tests-review:human",
    "revisao-ia": "review:ai", "revisao-humana": "review:human",
    "refinamento-aprovado": "approved:refinement", "prototipo-aprovado": "approved:prototype",
    "testes-aprovados": "approved:tests", "teste-alterado-aprovado": "approved:test-change",
    "homologado": "qa:approved", "reprovado": "qa:rejected", "dono:revisao-ia": "owner:ai-review",
    "pr-aprovado": "pr:approved", "conflito": "conflict", "bloqueia-producao": "blocks-production",
    "parada": "stale", "severidade:critica": "severity:critical", "severidade:alta": "severity:high",
    "severidade:media": "severity:medium", "severidade:baixa": "severity:low", "hotfix": "hotfix",
    "dependencies": "dependencies", "good first issue": "good first issue", "help wanted": "help wanted",
}
# Legacy labels with no v3 label: replaced by a native GitHub feature.
LABELS_REPLACED = {"tem-dependencia": "native issue dependency (blocked by)",
                   "prioridade:alta": "Priority field", "prioridade:media": "Priority field",
                   "prioridade:baixa": "Priority field"}
DECISIONS_LEGACY = ("refinamento-aprovado", "prototipo-aprovado", "testes-aprovados", "teste-alterado-aprovado",
                    "homologado", "reprovado", "dono:revisao-ia", "pr-aprovado")
V3_ONLY_DECISIONS = ("approved:backlog", "approved:selection", "approved:cancel")
DECISIONS = tuple(LABELS[label] for label in DECISIONS_LEGACY) + V3_ONLY_DECISIONS
CLAIM_PREFIX = {"legacy": "ia:", "v3": "agent:"}

BRANCH_PREFIXES = {"teste": "test", "feature": "feature", "docs": "docs", "bugfix": "fix", "hotfix": "hotfix",
                   "fundacao": "foundation", "framework": "framework", "sync": "sync", "release": "release",
                   "epico": None}  # epic branches only exist in the legacy model
V3_BRANCH_PREFIXES = ("test", "feature", "docs", "fix", "hotfix", "foundation", "framework", "sync", "release",
                      "maintenance")

WORKFLOWS = {
    "bb-kanban.yml": "bb-controller.yml", "bb-posses.yml": "bb-controller.yml",
    "bb-iniciar-sprint.yml": "bb-start-sprint.yml", "bb-criar-branches.yml": "bb-create-branches.yml",
    "bb-mesclar-pr.yml": "bb-merge-pr.yml", "bb-integrar-release.yml": "bb-cut-release.yml",
    "bb-candidata.yml": "bb-candidate.yml", "bb-publicar-producao.yml": "bb-publish.yml",
    "bb-publicar-sem-release.yml": "bb-publish-maintenance.yml", "bb-voltar-versao.yml": "bb-rollback.yml",
    "bb-encerrar.yml": "bb-close.yml", "bb-faxina.yml": "bb-cleanup.yml",
    "bb-ver-paineis.yml": "bb-board-report.yml", "bb-tarefa-de-correcao.yml": "bb-reject.yml",
    "bb-regras-pr.yml": "bb-pr-rules.yml", "bb-seguranca.yml": "bb-security.yml", "bb-ci.yml": "bb-ci.yml",
    "bb-codeql.yml": "bb-codeql.yml",
}
REQUIRED_CHECKS = {"legacy": ("check", "regras", "seguranca"), "v3": ("gate",)}
ENVIRONMENT = {"legacy": "producao", "v3": "production"}
SECRETS = {"PROJETO_TOKEN": "PROJECT_TOKEN"}
VARIABLES = {"PROJETO_OWNER": "PROJECT_OWNER", "PROJETO_PLANEJAMENTO": "PROJECT_NUMBER",
             "PROJETO_EXECUCAO": "PROJECT_NUMBER", "PROJETO_BUGS": "PROJECT_NUMBER"}

# --- reverse lookups --------------------------------------------------------------------------------------------------

SECTIONS_V3 = {v3: legacy for legacy, v3 in SECTIONS.items()}
KEYS_V3 = {SECTIONS[section]: {v3: legacy for legacy, v3 in keys.items()} for section, keys in KEYS.items()}
LABELS_V3 = {v3: legacy for legacy, v3 in LABELS.items()}


def is_build_key(key):
    return key.startswith("build_")


def key_to_v3(dotted):
    """'projeto.modo' -> 'project.mode'; an already-v3 or unknown key comes back unchanged."""
    section, _, key = dotted.partition(".")
    if section not in SECTIONS:
        return dotted
    new_key = key if is_build_key(key) else KEYS.get(section, {}).get(key, key)
    return f"{SECTIONS[section]}.{new_key}" if key else SECTIONS[section]


def key_to_legacy(dotted):
    """'project.mode' -> 'projeto.modo'; None for a v3-only key; a legacy key comes back unchanged."""
    section, _, key = dotted.partition(".")
    if section == "workflow" or (section, key) in V3_ONLY:
        return None
    if section in KEYS and (not key or key in KEYS[section] or (section == "compilado" and is_build_key(key))):
        return dotted
    if section not in SECTIONS_V3:
        return dotted
    legacy_section = SECTIONS_V3[section]
    if not key:
        return legacy_section
    if is_build_key(key):
        return f"{legacy_section}.{key}"
    legacy_key = KEYS_V3[section].get(key)
    return f"{legacy_section}.{legacy_key}" if legacy_key else None


def value_to_v3(legacy_dotted, value):
    return VALUES.get(legacy_dotted, {}).get(value, value) if isinstance(value, str) else value


def value_to_legacy(legacy_dotted, value):
    if not isinstance(value, str):
        return value
    reverse = {v3: legacy for legacy, v3 in VALUES.get(legacy_dotted, {}).items()}
    reverse.update(V3_VALUES_IN_LEGACY_VIEW.get(legacy_dotted, {}))
    return reverse.get(value, value)


def label_dialect(config):
    """'v3' when the project's GitHub labels were migrated to English, else 'legacy' (board.labels)."""
    board = config.get("board") if isinstance(config, dict) else None
    return board.get("labels", "legacy") if isinstance(board, dict) else "legacy"


def label(name, dialect):
    """Spell a label in the project's dialect ('legacy' or 'v3'), given either spelling."""
    if dialect == "v3":
        return LABELS.get(name, name)
    return LABELS_V3.get(name, name)
