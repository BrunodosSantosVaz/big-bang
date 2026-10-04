# Checklist de produção

<!-- Salve como docs/operacao/checklist-producao.md. Exigido pelo "Publicar em produção" (bb checklist producao).
     Para cada item, troque "a definir" por como ESTE projeto verifica:
       cmd: <comando que precisa terminar com sucesso>
       portao: candidata | ci | seguranca | staging | testes | builtin   (um portão da esteira que já prova o item)
       nao-se-aplica: <motivo>
     Item sem verificação reprova a publicação. -->

- [ ] O backend sobe sem erro — verificação: `a definir`
- [ ] O front compila — verificação: `a definir`
- [ ] As migrações rodam do zero e a partir da versão anterior — verificação: `a definir`
- [ ] O ambiente sobe pelo método de deploy do alvo — verificação: `a definir`
- [ ] Nenhum segredo no pacote do front — verificação: `portao: seguranca`
- [ ] Rotas privadas exigem autenticação — verificação: `a definir`
- [ ] CORS de produção configurado por ambiente — verificação: `a definir`
- [ ] Testes de limite de requisições presentes e passando — verificação: `a definir`
- [ ] /api/health responde sem autenticação — verificação: `a definir`
- [ ] O README documenta as variáveis de ambiente sem valores — verificação: `portao: builtin`
- [ ] A auditoria de segurança não tem achado crítico ou alto aberto — verificação: `portao: builtin`
