# {{projeto.nome}} — Contêineres (C4, nível 2)

<!-- Salve como docs/arquitetura/conteineres.md. Modelo C4: https://c4model.com
     O front fala só com o backend da própria aplicação (ARQ-06, SEG-IA-01). -->

```mermaid
C4Container
  title Contêineres — {{projeto.nome}}
  Person(usuario, "<Perfil de usuário>")
  System_Boundary(sistema, "{{projeto.nome}}") {
    Container(front, "Front-end", "<tecnologia>", "Interface; fala só com a API")
    Container(api, "API", "<tecnologia>", "Casos de uso, autorização, regras de negócio")
    ContainerDb(banco, "Banco de dados", "<tecnologia>", "<o que guarda>")
  }
  System_Ext(externo, "<Sistema externo>")
  Rel(usuario, front, "Usa", "HTTPS")
  Rel(front, api, "Chama", "HTTPS/JSON em /api")
  Rel(api, banco, "Lê e grava")
  Rel(api, externo, "<o que troca>", "<protocolo>")
```

| Contêiner | Tecnologia | Responsabilidade | Onde roda |
| --- | --- | --- | --- |
| Front-end | | | |
| API | | | |
| Banco de dados | | | |
