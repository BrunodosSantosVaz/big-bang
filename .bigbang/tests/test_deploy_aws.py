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
import hashlib
import tarfile
from pathlib import Path

from _raiz import BIGBANG, RAIZ, exemplo_toml, ignorar_para_copia, importar_bb
from _scripts import CasoDeScript

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

        # Ações S3 mínimas necessárias para hospedagem estática (sem GetObject)
        self.assertIn("s3:ListBucket", all_actions)
        self.assertIn("s3:PutObject", all_actions)
        self.assertNotIn("s3:GetObject", all_actions)
        self.assertIn("s3:DeleteObject", all_actions)

        # Ações CloudFront mínimas para invalidação de cache (sem GetInvalidation)
        self.assertIn("cloudfront:CreateInvalidation", all_actions)
        self.assertNotIn("cloudfront:GetInvalidation", all_actions)

    def test_alvo_aws_trust_policy_restrito_a_ambientes_e_refs_protegidas(self):
        trust_path = self.aws_dir / "modelos/trust-policy.json"
        self.assertTrue(trust_path.is_file(), f"Arquivo não encontrado: {trust_path}")
        with open(trust_path, "r", encoding="utf-8") as f:
            trust = json.load(f)
        statement = trust["Statement"][0]
        condition = statement["Condition"]
        self.assertEqual(condition["StringEquals"]["token.actions.githubusercontent.com:aud"], "sts.amazonaws.com")
        sub_allowed = condition["StringLike"]["token.actions.githubusercontent.com:sub"]

        # Deve ser lista restrita ao ambiente parametrizado e nunca curinga amplo ou ambientes combinados
        self.assertIsInstance(sub_allowed, list)
        self.assertNotIn("repo:<OWNER>/<REPO>:*", sub_allowed)
        self.assertIn("repo:<OWNER>/<REPO>:environment:<AMBIENTE>", sub_allowed)
        self.assertNotIn("repo:<OWNER>/<REPO>:ref:refs/heads/main", sub_allowed)
        self.assertNotIn("repo:<OWNER>/<REPO>:ref:refs/tags/v*", sub_allowed)
        self.assertEqual(len(sub_allowed), 1)

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



class TestDeployAwsScripts(CasoDeScript):
    def setUp(self):
        super().setUp()
        self.projeto = os.path.join(self.pasta, "projeto")
        os.makedirs(os.path.join(self.projeto, ".bigbang", "esteira", "perfis", "deploy", "scripts"), exist_ok=True)
        shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(self.projeto, ".bigbang", "VERSION"))
        shutil.copytree(os.path.join(BIGBANG, "esteira", "perfis", "deploy", "alvos"),
                        os.path.join(self.projeto, ".bigbang", "esteira", "perfis", "deploy", "alvos"))
        shutil.copytree(os.path.join(BIGBANG, "esteira", "perfis", "deploy", "artefatos"),
                        os.path.join(self.projeto, ".bigbang", "esteira", "perfis", "deploy", "artefatos"))
        shutil.copytree(os.path.join(BIGBANG, "bb"),
                        os.path.join(self.projeto, ".bigbang", "bb"))
        os.makedirs(os.path.join(self.projeto, ".bigbang", "bin"))
        shutil.copy(os.path.join(BIGBANG, "bin", "bb.py"),
                    os.path.join(self.projeto, ".bigbang", "bin", "bb.py"))
        shutil.copy(os.path.join(BIGBANG, "esteira", "perfis", "deploy", "scripts", "promover.sh"),
                    os.path.join(self.projeto, ".bigbang", "esteira", "perfis", "deploy", "scripts", "promover.sh"))

        cfg = exemplo_toml().replace('alvo = "vps-docker"', 'alvo = "aws"').replace('[deploy]', '[deploy]\nartefato = "estatico"')
        with open(os.path.join(self.projeto, "bigbang.toml"), "w", encoding="utf-8") as f:
            f.write(cfg)

        self.env = {
            "BB": f"{sys.executable} {os.path.join(self.projeto, '.bigbang', 'bin', 'bb.py')} --raiz {self.projeto}",
            "PATH": f"{self.bin}:{os.environ.get('PATH', '')}",
            "GITHUB_REPOSITORY": "dono/repo",
            "GH_TOKEN": "token",
            "AWS_REGION": "us-east-1",
            "AWS_S3_BUCKET": "meu-bucket",
            "AWS_CLOUDFRONT_DISTRIBUTION_ID": "EDIST123",
            "AWS_SIMULAR": "true",
            "FAKE_GH_STATE": self.estado_arquivo,
            "FAKE_GH_LOG": self.log,
        }

    def test_alvo_aws_rollback_rejeita_pacote_corrompido(self):
        script = os.path.join(self.projeto, ".bigbang/esteira/perfis/deploy/alvos/aws/scripts/alvo.sh")
        rel_dir = os.path.join(self.pasta, "rel_v1")
        os.makedirs(rel_dir, exist_ok=True)
        tar_valido = os.path.join(rel_dir, "artefato.tar.gz")
        with open(tar_valido, "wb") as f:
            f.write(b"conteudo original legitimo")
        hash_valido = hashlib.sha256(b"conteudo original legitimo").hexdigest()

        manifesto = {
            "versao": 1,
            "formato": "estatico",
            "artefato": {"arquivo": "artefato.tar.gz", "sha256": hash_valido, "tamanho": 26},
            "arquivos": [{"caminho": "index.html", "sha256": hash_valido, "tamanho": 26}]
        }
        with open(os.path.join(rel_dir, "manifesto.json"), "w", encoding="utf-8") as f:
            json.dump(manifesto, f)
        with open(os.path.join(rel_dir, "manifesto.json"), "rb") as f:
            manifesto_hash = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(rel_dir, "manifesto.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{manifesto_hash}  manifesto.json\n")

        # Corrompe o artefato.tar.gz
        with open(tar_valido, "wb") as f:
            f.write(b"conteudo adulterado ou corrompido!")

        self.estado.setdefault("releases", []).append("v1.0.0")
        self.estado.setdefault("release_dirs", {})["v1.0.0"] = rel_dir
        self.estado.setdefault("release_assets", {})["v1.0.0"] = ["manifesto.json", "manifesto.sha256", "artefato.tar.gz"]
        self.gravar_estado()

        env = dict(self.env, PYTHONPATH="")
        res = subprocess.run(["bash", script, "voltar", "producao", "v1.0.0"],
                             cwd=self.projeto, capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0, res.stdout)
        self.assertNotIn("aws s3 sync", res.stdout)

    def test_alvo_aws_rollback_rejeita_pacote_corrompido_no_fallback(self):
        script = os.path.join(self.projeto, ".bigbang/esteira/perfis/deploy/alvos/aws/scripts/alvo.sh")
        rel_dir = os.path.join(self.pasta, "rel_v2")
        os.makedirs(rel_dir, exist_ok=True)
        tar_valido = os.path.join(rel_dir, "artefato.tar.gz")
        tmp_orig = os.path.join(self.pasta, "orig_index.html")
        with open(tmp_orig, "w", encoding="utf-8") as f:
            f.write("<h1>legitimo</h1>")
        with tarfile.open(tar_valido, "w:gz") as tar:
            tar.add(tmp_orig, arcname="index.html")
        with open(tar_valido, "rb") as f:
            hash_valido = hashlib.sha256(f.read()).hexdigest()

        manifesto = {
            "versao": 1,
            "formato": "estatico",
            "artefato": {"arquivo": "artefato.tar.gz", "sha256": hash_valido, "tamanho": 26},
            "arquivos": [{"caminho": "index.html", "sha256": hash_valido, "tamanho": 26}]
        }
        with open(os.path.join(rel_dir, "manifesto.json"), "w", encoding="utf-8") as f:
            json.dump(manifesto, f)
        with open(os.path.join(rel_dir, "manifesto.json"), "rb") as f:
            manifesto_hash = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(rel_dir, "manifesto.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{manifesto_hash}  manifesto.json\n")

        # Agora sobrescreve artefato.tar.gz com outro tar.gz válido (adulterado)
        tmp_evil = os.path.join(self.pasta, "evil_index.html")
        with open(tmp_evil, "w", encoding="utf-8") as f:
            f.write("<h1>adulterado</h1>")
        with tarfile.open(tar_valido, "w:gz") as tar:
            tar.add(tmp_evil, arcname="index.html")

        self.estado.setdefault("releases", []).append("v2.0.0")
        self.estado.setdefault("release_dirs", {})["v2.0.0"] = rel_dir
        self.estado.setdefault("release_assets", {})["v2.0.0"] = ["manifesto.json", "manifesto.sha256", "artefato.tar.gz"]
        self.gravar_estado()

        # Cria wrapper do python3 que falha especificamente ao importar bb.artifacts
        py_mock_dir = os.path.join(self.pasta, "mock_py_bin")
        os.makedirs(py_mock_dir, exist_ok=True)
        py_mock = os.path.join(py_mock_dir, "python3")
        with open(py_mock, "w", encoding="utf-8") as f:
            f.write('#!/usr/bin/env bash\nif [[ "$*" == *"bb.artifacts"* ]]; then exit 1; fi\nexec /usr/bin/python3 "$@"\n')
        os.chmod(py_mock, 0o755)

        env = dict(self.env, PATH=f"{py_mock_dir}:{self.env['PATH']}")
        res = subprocess.run(["bash", script, "voltar", "producao", "v2.0.0"],
                             cwd=self.projeto, capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0, res.stdout)
        self.assertNotIn("aws s3 sync", res.stdout)

    def test_alvo_aws_rollback_sucesso_com_pacote_integro_no_fallback(self):
        script = os.path.join(self.projeto, ".bigbang/esteira/perfis/deploy/alvos/aws/scripts/alvo.sh")
        rel_dir = os.path.join(self.pasta, "rel_v3")
        os.makedirs(rel_dir, exist_ok=True)
        tar_valido = os.path.join(rel_dir, "artefato.tar.gz")
        tmp_orig = os.path.join(self.pasta, "orig_index_v3.html")
        with open(tmp_orig, "w", encoding="utf-8") as f:
            f.write("<h1>conteudo estatico v3</h1>")
        with tarfile.open(tar_valido, "w:gz") as tar:
            tar.add(tmp_orig, arcname="index.html")
        with open(tar_valido, "rb") as f:
            hash_tar = hashlib.sha256(f.read()).hexdigest()

        # Manifesto com 'arquivos' antes de 'artefato', como produzido por json com sort_keys=True
        manifesto = {
            "arquivos": [{"caminho": "index.html", "sha256": "0" * 64, "tamanho": 28}],
            "artefato": {"arquivo": "artefato.tar.gz", "sha256": hash_tar, "tamanho": os.path.getsize(tar_valido)},
            "formato": "estatico",
            "versao": 1
        }
        with open(os.path.join(rel_dir, "manifesto.json"), "w", encoding="utf-8") as f:
            json.dump(manifesto, f, sort_keys=True)
        with open(os.path.join(rel_dir, "manifesto.json"), "rb") as f:
            manifesto_hash = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(rel_dir, "manifesto.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{manifesto_hash}  manifesto.json\n")

        self.estado.setdefault("releases", []).append("v3.0.0")
        self.estado.setdefault("release_dirs", {})["v3.0.0"] = rel_dir
        self.estado.setdefault("release_assets", {})["v3.0.0"] = ["manifesto.json", "manifesto.sha256", "artefato.tar.gz"]
        self.gravar_estado()

        # Wrapper python3 que falha completamente forçando o fallback em shell puro no alvo.sh
        py_mock_dir = os.path.join(self.pasta, "mock_py_bin_v3")
        os.makedirs(py_mock_dir, exist_ok=True)
        py_mock = os.path.join(py_mock_dir, "python3")
        with open(py_mock, "w", encoding="utf-8") as f:
            f.write('#!/usr/bin/env bash\nexit 1\n')
        os.chmod(py_mock, 0o755)

        env = dict(self.env, PATH=f"{py_mock_dir}:{self.env['PATH']}")
        res = subprocess.run(["bash", script, "voltar", "producao", "v3.0.0"],
                             cwd=self.projeto, capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("aws s3 sync", res.stdout)

    def test_alvo_aws_promocao_estatica_sem_imagem(self):
        promover = os.path.join(self.projeto, ".bigbang/esteira/perfis/deploy/scripts/promover.sh")
        rc_dir = os.path.join(self.pasta, "rc_dir")
        os.makedirs(rc_dir, exist_ok=True)
        tar_path = os.path.join(rc_dir, "artefato.tar.gz")
        tmp_content = os.path.join(self.pasta, "index.html")
        with open(tmp_content, "w", encoding="utf-8") as f:
            f.write("<h1>Hello World</h1>")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(tmp_content, arcname="index.html")

        with open(tar_path, "rb") as f:
            tar_bytes = f.read()
        tar_sha = hashlib.sha256(tar_bytes).hexdigest()
        manifesto = {
            "versao": 1,
            "formato": "estatico",
            "artefato": {"arquivo": "artefato.tar.gz", "sha256": tar_sha, "tamanho": len(tar_bytes)},
            "arquivos": [{"caminho": "index.html", "sha256": hashlib.sha256(b"<h1>Hello World</h1>").hexdigest(), "tamanho": 20}]
        }
        with open(os.path.join(rc_dir, "manifesto.json"), "w", encoding="utf-8") as f:
            json.dump(manifesto, f)
        with open(os.path.join(rc_dir, "manifesto.json"), "rb") as f:
            man_hash = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(rc_dir, "manifesto.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{man_hash}  manifesto.json\n")

        self.estado.setdefault("releases", []).append("v1.0.0-rc.1")
        self.estado.setdefault("release_dirs", {})["v1.0.0-rc.1"] = rc_dir
        self.estado.setdefault("release_assets", {})["v1.0.0-rc.1"] = ["manifesto.json", "manifesto.sha256", "artefato.tar.gz"]
        self.gravar_estado()

        env = dict(self.env, RC_TAG="v1.0.0-rc.1", TAG="v1.0.0", TARGET_SHA="abc",
                   SAUDE_URL="http://127.0.0.1:9", SAUDE_TENTATIVAS="1", SAUDE_INTERVALO="0")
        res = subprocess.run(["bash", promover], cwd=self.projeto, capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.ler_estado()
        self.assertIn("v1.0.0", self.estado.get("releases", []))
        self.assertIn("artefato.tar.gz", self.estado.get("release_assets", {}).get("v1.0.0", []))


if __name__ == "__main__":
    unittest.main()
