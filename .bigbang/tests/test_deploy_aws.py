"""Unittests for AWS S3 + CloudFront deployment adapter with OIDC (#180)."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _raiz import RAIZ, exemplo_toml, ignorar_para_copia, importar_bb

importar_bb()
from bb import cli, config, deploy_catalog, generator  # noqa: E402


class TestDeployAws(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "projeto"
        shutil.copytree(RAIZ, self.root, ignore=ignorar_para_copia("bigbang.toml", "STACK.md"))
        (self.root / "bigbang.toml").write_text(exemplo_toml(), encoding="utf-8")
        self.aws_dir = self.root / ".bigbang/esteira/perfis/deploy/alvos/aws"

    def tearDown(self):
        self.temp.cleanup()

    def configure_aws(self):
        p = self.root / "bigbang.toml"
        p.write_text(
            p.read_text().replace('alvo = "vps-docker"', 'alvo = "aws"').replace('[deploy]', '[deploy]\nartefato = "estatico"'),
            encoding="utf-8"
        )

    def test_alvo_aws_contrato_implementado(self):
        target = deploy_catalog.read_target(self.root, "aws")
        self.assertEqual(target.name, "aws")
        self.assertEqual(target.state, "implementado")
        self.assertIn("estatico", target.artifacts)
        self.assertEqual(target.operations, ("publicar", "migrar", "saude", "voltar"))
        self.assertEqual(target.variables, ("AWS_REGION", "AWS_S3_BUCKET", "AWS_CLOUDFRONT_DISTRIBUTION_ID"))
        self.assertEqual(target.secrets, ("AWS_ROLE_ARN",))
        self.assertEqual(target.max_services, 1)
        self.assertIn("BETA", target.description)

    def test_alvo_aws_iam_policy_template_minima_sem_curingas(self):
        policy_path = self.aws_dir / "modelos/iam-policy.json"
        self.assertTrue(policy_path.is_file(), f"Arquivo não encontrado: {policy_path}")
        with open(policy_path, "r", encoding="utf-8") as f:
            policy = json.load(f)

        self.assertEqual(policy.get("Version"), "2012-10-17")
        statements = policy.get("Statement", [])
        self.assertGreater(len(statements), 0)

        all_actions = []
        for stmt in statements:
            self.assertEqual(stmt.get("Effect"), "Allow")
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            all_actions.extend(actions)
            # Sem ações curinga gerais
            self.assertNotIn("*", actions)
            self.assertNotIn("s3:*", actions)
            self.assertNotIn("cloudfront:*", actions)

        # Ações S3 mínimas para hospedagem estática
        self.assertIn("s3:ListBucket", all_actions)
        self.assertIn("s3:PutObject", all_actions)
        self.assertIn("s3:GetObject", all_actions)
        self.assertIn("s3:DeleteObject", all_actions)

        # Ações CloudFront mínimas para invalidação de cache
        self.assertIn("cloudfront:CreateInvalidation", all_actions)
        self.assertIn("cloudfront:GetInvalidation", all_actions)

    def test_alvo_aws_trust_policy_restrito_a_ambientes_e_refs_protegidas(self):
        trust_path = self.aws_dir / "modelos/trust-policy.json"
        self.assertTrue(trust_path.is_file(), f"Arquivo não encontrado: {trust_path}")
        with open(trust_path, "r", encoding="utf-8") as f:
            trust = json.load(f)
        statement = trust["Statement"][0]
        condition = statement["Condition"]
        self.assertEqual(condition["StringEquals"]["token.actions.githubusercontent.com:aud"], "sts.amazonaws.com")
        sub_allowed = condition["StringLike"]["token.actions.githubusercontent.com:sub"]

        # Deve ser lista restrita e nunca curinga amplo
        self.assertIsInstance(sub_allowed, list)
        self.assertNotIn("repo:<OWNER>/<REPO>:*", sub_allowed)
        self.assertIn("repo:<OWNER>/<REPO>:environment:staging", sub_allowed)
        self.assertIn("repo:<OWNER>/<REPO>:environment:producao", sub_allowed)
        self.assertIn("repo:<OWNER>/<REPO>:ref:refs/heads/main", sub_allowed)
        self.assertIn("repo:<OWNER>/<REPO>:ref:refs/tags/v*", sub_allowed)

    def test_alvo_aws_script_operacoes_e_aviso_beta(self):
        script = self.aws_dir / "scripts/alvo.sh"
        self.assertTrue(script.is_file(), f"Script alvo.sh não encontrado: {script}")

        # Execução sem argumentos deve falhar com código 2
        res = subprocess.run(["bash", str(script)], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)

        # Migração estática informa que não há banco e sai com 0
        res = subprocess.run(["bash", str(script), "migrar", "staging"],
                             cwd=self.root, capture_output=True, text=True,
                             env=dict(os.environ, BB=f"{sys.executable} .bigbang/bin/bb.py"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("316", res.stdout + res.stderr)
        self.assertIn("BETA", res.stdout + res.stderr)

        # Publicar sem variáveis obrigatórias deve falhar
        res = subprocess.run(["bash", str(script), "publicar", "staging", "teste"],
                             cwd=self.root, capture_output=True, text=True,
                             env=dict(os.environ, BB=f"{sys.executable} .bigbang/bin/bb.py"))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("316", res.stdout + res.stderr)

    def test_alvo_aws_publicar_rejeita_pasta_vazia_para_proteger_s3(self):
        script = self.aws_dir / "scripts/alvo.sh"
        empty_dir = self.root / "pasta_vazia"
        empty_dir.mkdir(parents=True, exist_ok=True)
        env = dict(
            os.environ,
            BB=f"{sys.executable} .bigbang/bin/bb.py",
            AWS_REGION="us-east-1",
            AWS_S3_BUCKET="meu-bucket",
            AWS_CLOUDFRONT_DISTRIBUTION_ID="EDIST123",
            AWS_SIMULAR="true"
        )
        res = subprocess.run(["bash", str(script), "publicar", "staging", str(empty_dir)],
                             cwd=self.root, capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("vazio ou inexistente", res.stderr + res.stdout)
        self.assertNotIn("aws s3 sync", res.stdout)

    def test_alvo_aws_rollback_aborta_em_falha_de_download_para_proteger_s3(self):
        script = self.aws_dir / "scripts/alvo.sh"
        # Sem gh CLI ou com erro de download, voltar deve falhar imediatamente sem chamar sync
        env = dict(
            os.environ,
            BB=f"{sys.executable} .bigbang/bin/bb.py",
            AWS_REGION="us-east-1",
            AWS_S3_BUCKET="meu-bucket",
            AWS_CLOUDFRONT_DISTRIBUTION_ID="EDIST123",
            AWS_SIMULAR="true",
            PATH="/usr/bin:/bin"
        )
        env.pop("GITHUB_REPOSITORY", None)
        res = subprocess.run(["bash", str(script), "voltar", "producao", "v1.0.0"],
                             cwd=self.root, capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("aws s3 sync", res.stdout)

    def test_alvo_aws_issue_template_relato_teste(self):
        source_template = self.aws_dir / "arquivos/.github/ISSUE_TEMPLATE/bb-aws-beta-relato.yml"
        self.assertTrue(source_template.is_file(), f"Template fonte não encontrado: {source_template}")
        content = source_template.read_text(encoding="utf-8")
        self.assertIn("316", content)
        self.assertIn("https://github.com/BrunodosSantosVaz/big-bang/issues/316", content)
        self.assertIn("NUNCA inclua segredos", content)

        # Valida que o template faz parte do plano gerado para o alvo aws usando artefatos reais
        self.configure_aws()
        plan = generator.build_plan(self.root, install_pipeline=True)
        self.assertIn(".github/ISSUE_TEMPLATE/bb-aws-beta-relato.yml", plan.expected)

    def test_alvo_aws_readme_contem_aviso_beta_e_link_issue_316(self):
        readme = self.aws_dir / "README.md"
        content = readme.read_text(encoding="utf-8")
        self.assertIn("BETA", content)
        self.assertIn("316", content)
        self.assertIn("https://github.com/BrunodosSantosVaz/big-bang/issues/316", content)
        self.assertIn("OIDC", content)
        self.assertIn("AWS_ROLE_ARN", content)

    def test_alvo_aws_geracao_workflow_com_oidc_e_sem_docker(self):
        # Valida plano do gerador com o artefato estático real do repositório
        self.configure_aws()

        plan = generator.build_plan(self.root, install_pipeline=True)
        workflows = {name: plan.expected[".github/workflows/" + name] for name in
                     ("bb-candidata.yml", "bb-publicar-producao.yml", "bb-voltar-versao.yml")}

        for name, wf in workflows.items():
            self.assertIn("role-to-assume: ${{ secrets.AWS_ROLE_ARN }}", wf, f"OIDC ausente em {name}")
            self.assertIn("aws-region: ${{ vars.AWS_REGION }}", wf, f"Região ausente em {name}")
            self.assertIn("id-token: write", wf, f"Permissão id-token ausente em {name}")
            self.assertIn("AWS_S3_BUCKET: ${{ vars.AWS_S3_BUCKET }}", wf, f"Bucket ausente em {name}")
            self.assertIn("AWS_CLOUDFRONT_DISTRIBUTION_ID: ${{ vars.AWS_CLOUDFRONT_DISTRIBUTION_ID }}", wf)
            # Garantir ausência de chaves fixas
            self.assertNotIn("AWS_ACCESS_KEY_ID", wf)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", wf)

        candidata_wf = workflows["bb-candidata.yml"]
        # Workflow para site estático não deve usar Docker/GHCR/Trivy
        self.assertNotIn("docker login", candidata_wf)
        self.assertNotIn("setup-buildx", candidata_wf)
        self.assertNotIn("candidata-sbom.sh", candidata_wf)
        self.assertIn("candidata-arquivos.sh", candidata_wf)
        self.assertIn("actions/upload-artifact", candidata_wf)
        self.assertIn("actions/download-artifact", candidata_wf)

    def test_alvo_aws_aviso_beta_na_saida_do_comando(self):
        self.configure_aws()

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--raiz", str(self.root), "gerar", "--esteira"])
        self.assertEqual(code, 0)
        output = out.getvalue()
        self.assertIn("316", output)
        self.assertIn("BETA", output)
        self.assertIn("https://github.com/BrunodosSantosVaz/big-bang/issues/316", output)


if __name__ == "__main__":
    unittest.main()
