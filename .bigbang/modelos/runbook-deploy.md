# Runbook: publicar em produção (perfil deploy)

<!-- Salve como docs/operacao/deploy.md e complete os campos do projeto. DOC-09. -->

## Antes

- O épico ou bug está `homologado` no staging, com a candidata `vX.Y.Z-rc.N`.
- O botão **Publicar em produção** com `simular=true` mostra "Portão aprovado".

## Publicar

1. Rode **Publicar em produção** com a versão e `simular=false`.
2. Aprove o ambiente `producao` em Actions (só o dono).
3. A esteira migra com a imagem nova, troca a versão pelo **mesmo digest** da candidata e confere `/api/health`.

## Conferir

- `curl -fsS <url_producao>/api/health`
- A Release `vX.Y.Z` (Latest) registra o digest em `imagem.txt`.
- No servidor: `cat /opt/<slug>/producao/imagem.env` (a anterior fica em `imagem.anterior.env`).

## Se o health check falhar

Siga o runbook [voltar versão](voltar-versao.md). Migrações não são desfeitas: o esquema continua compatível com a
versão anterior (expandir-e-contrair, DAD-02).

## Segredos da aplicação

<!-- Onde ficam (ex.: /opt/<slug>/producao/app.env), quem tem acesso, como trocar (rotação: SEG-15). -->
