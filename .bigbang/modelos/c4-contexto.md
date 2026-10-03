# {{projeto.nome}} — Contexto (C4, nível 1)

<!-- Salve como docs/arquitetura/contexto.md. Modelo C4: https://c4model.com -->

```mermaid
C4Context
  title Contexto — {{projeto.nome}}
  Person(usuario, "<Perfil de usuário>", "<o que faz no sistema>")
  System(sistema, "{{projeto.nome}}", "<o que o sistema faz, numa frase>")
  System_Ext(externo, "<Sistema externo>", "<para que é usado>")
  Rel(usuario, sistema, "Usa")
  Rel(sistema, externo, "<o que troca>", "<protocolo>")
```

| Elemento | Responsabilidade |
| --- | --- |
| <Perfil de usuário> | |
| <Sistema externo> | |
