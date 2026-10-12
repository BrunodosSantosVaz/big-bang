# Alvo `aws` (S3 + CloudFront via OIDC) [BETA]

> [!WARNING]
> **ESTÁGIO BETA / NÃO TESTADO EM CONTA AWS REAL**
> Este adaptador foi implementado e coberto por testes de unidade estruturais, mas **ainda não foi validado ponta a ponta contra uma conta AWS real**.
> Se você testar este adaptador em sua conta AWS, relate os resultados, dificuldades ou melhorias na issue de validação:
> **[#316 — AWS (beta): relatos de teste e melhorias do alvo S3 + CloudFront](https://github.com/BrunodosSantosVaz/big-bang/issues/316)**.
> NUNCA inclua segredos, tokens ou dados reais de credenciais em seus relatos.

---

## Visão Geral

O alvo `aws` entrega arquivos estáticos diretamente no Amazon S3 e realiza a invalidação da distribuição correspondente no Amazon CloudFront.

- **Formato consumido:** `estatico` (arquivos com manifesto de integridade SHA-256).
- **Autenticação:** OIDC via GitHub Actions (`role-to-assume`), **sem chaves estáticas de acesso** (sem `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).
- **Permissões mínimas:** Política IAM restrita aos recursos do bucket S3 e da distribuição CloudFront configurados.

---

## Configuração do Repositório

### Variáveis de Ambiente (`vars`)
- `AWS_REGION`: Região da AWS onde o bucket S3 está hospedado (ex.: `us-east-1`, `sa-east-1`).
- `AWS_S3_BUCKET`: Nome do bucket S3 que hospeda o site estático.
- `AWS_CLOUDFRONT_DISTRIBUTION_ID`: ID da distribuição do CloudFront (ex.: `E1234EXAMPLE56`).

### Segredos (`secrets`)
- `AWS_ROLE_ARN`: ARN da IAM Role configurada com OIDC para o repositório GitHub (ex.: `arn:aws:iam::123456789012:role/bigbang-deploy-role`).

---

## Configuração na AWS (OIDC e Permissões Mínimas)

### 1. Provedor de Identidade OIDC
No console IAM, configure o provedor OIDC para o GitHub Actions:
- **URL do provedor:** `https://token.actions.githubusercontent.com`
- **Audience:** `sts.amazonaws.com`

### 2. Trust Policy (Relação de Confiança)
Utilize o modelo em [`modelos/trust-policy.json`](modelos/trust-policy.json) ao criar a Role:
Substitua `<AWS_ACCOUNT_ID>`, `<OWNER>` e `<REPO>` pelos dados do seu repositório.

### 3. Política de Permissões Mínimas
Anexe a política baseada em [`modelos/iam-policy.json`](modelos/iam-policy.json):
- S3: `s3:ListBucket` no bucket e `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` nos objetos.
- CloudFront: `cloudfront:CreateInvalidation` e `cloudfront:GetInvalidation` restritos à distribuição.
- Não concede acesso de administração nem ações curinga (`*`).

---

## Operações da Esteira

1. `publicar <ambiente> <manifesto>`: Sincroniza os arquivos com `s3://${AWS_S3_BUCKET}` e dispara `create-invalidation` no CloudFront (`/*`).
2. `migrar <ambiente>`: Informativo (hospedagem estática não possui migrações de banco de dados).
3. `saude <ambiente>`: Consulta a URL configurada (`deploy.url_<ambiente>` + `deploy.caminho_saude`) até receber HTTP 200.
4. `voltar <ambiente> <versao>`: Baixa os arquivos estáticos da Release da versão desejada e reexecuta a publicação, sem rollback de banco.
