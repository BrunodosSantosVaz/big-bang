# Fonte das skills `bb-*`

As 20 skills no padrão aberto Agent Skills (seção 15). O gerador as copia para `.agents/skills/` e `.claude/skills/`.

O catálogo segue a seção 15.2 da [especificação](https://github.com/BrunodosSantosVaz/big-bang/wiki/Especificacao). Cada skill encaminha aos processos e
comandos existentes, sem duplicar a lógica da esteira. Os caminhos citados são relativos à raiz do projeto.
As cópias são geradas desde o template, antes da Fundação; personalize com skills próprias sem prefixo `bb-`.

`bb-atualizar` usa o CLI `bb atualizar` para obter uma release oficial com hash e atestação verificados, regenerar
a camada do projeto e abrir um PR. Aprovações de produto, stack, design e produção continuam sendo do dono;
uma skill não concede permissões nem transforma CI verde em aprovação.
