"""Deploy adapters are discovered by contract, and invalid delivery choices never write workflows (#175)."""
import contextlib
import copy
import io
from pathlib import Path
import shutil
import tempfile
import unittest

from _raiz import RAIZ, exemplo_toml, ignorar_para_copia, importar_bb

importar_bb()
from bb import cli, config, deploy_catalog, generator, verify  # noqa: E402
from bb.errors import BbError, EXIT_INVALID_CONFIG, EXIT_VERIFICATION_FAILED  # noqa: E402


TARGET = '''descricao = "Adaptador de teste"
situacao = "implementado"
artefatos = ["imagem"]
operacoes = ["publicar", "migrar", "saude", "voltar"]
variaveis = ["TESTE_APP"]
segredos = ["TESTE_TOKEN"]
'''


class CatalogoDeploy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'projeto'
        shutil.copytree(RAIZ, self.root, ignore=ignorar_para_copia('bigbang.toml', 'STACK.md'))
        (self.root / 'bigbang.toml').write_text(exemplo_toml(), encoding='utf-8')
        self.targets = self.root / '.bigbang/esteira/perfis/deploy/alvos'
        self.artifacts = self.root / '.bigbang/esteira/perfis/deploy/artefatos'

    def tearDown(self):
        self.temp.cleanup()

    def target(self, name='novo-provedor', text=TARGET):
        folder = self.targets / name
        (folder / 'scripts').mkdir(parents=True, exist_ok=True)
        (folder / 'alvo.toml').write_text(text, encoding='utf-8')
        (folder / 'scripts/alvo.sh').write_text('#!/usr/bin/env bash\nexit 0\n', encoding='utf-8')
        return folder

    def select(self, name, artifact=None):
        text = exemplo_toml().replace('alvo = "vps-docker"', f'alvo = "{name}"')
        if artifact:
            text = text.replace('[deploy]', f'[deploy]\nartefato = "{artifact}"')
        (self.root / 'bigbang.toml').write_text(text, encoding='utf-8')

    def command(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(['--raiz', str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_configuracao_atual_resolve_imagem_sem_chave_nova(self):
        cfg = config.load(self.root)
        target, artifact = deploy_catalog.resolve(self.root, cfg)
        self.assertEqual(target.name, 'vps-docker')
        self.assertEqual(artifact.name, 'imagem')
        self.assertEqual(artifact.identity, 'digest')
        self.assertEqual(config.get(cfg, 'deploy.artefato'), 'imagem')

    def test_novo_alvo_sem_editar_enum_ou_nucleo(self):
        folder = self.target()
        generated = folder / 'arquivos/.github/bb-novo.md'
        generated.parent.mkdir(parents=True)
        generated.write_text('# Novo alvo\n', encoding='utf-8')
        self.select('novo-provedor')
        plan = generator.build_plan(self.root, install_pipeline=True)
        self.assertIn('.github/bb-novo.md', plan.expected)
        self.assertFalse((self.root / '.github/bb-novo.md').exists())

    def test_formato_tem_sua_camada_antes_do_alvo(self):
        relative = 'arquivos/.github/bb-camada.md'
        base = self.root / '.bigbang/esteira/perfis/deploy'
        for folder, text in ((base / 'arquivos/.github', '# Perfil\n'),
                             (self.artifacts / 'imagem/arquivos/.github', '# Artefato\n')):
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'bb-camada.md').write_text(text, encoding='utf-8')
        plan = generator.build_plan(self.root, install_pipeline=True)
        self.assertIn('# Artefato', plan.expected['.github/bb-camada.md'])
        target_file = self.targets / 'vps-docker' / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text('# Alvo\n', encoding='utf-8')
        self.assertIn('# Alvo', generator.build_plan(self.root, install_pipeline=True).expected['.github/bb-camada.md'])

    def test_alvo_desconhecido_ou_reservado_nao_grava_nada(self):
        before = (self.root / 'AGENTS.md').read_bytes()
        for name in ('inexistente', 'aws', 'paas', 'tsuru', 'personalizado'):
            with self.subTest(name=name):
                self.select(name)
                code, _, err = self.command('gerar', '--esteira')
                self.assertEqual(code, EXIT_INVALID_CONFIG, err)
                self.assertIn(name, err)
                self.assertEqual((self.root / 'AGENTS.md').read_bytes(), before)
                self.assertFalse((self.root / '.github/workflows/bb-candidata.yml').exists())

    def test_adaptador_sem_script_e_recusado_antes_de_gerar(self):
        folder = self.target()
        (folder / 'scripts/alvo.sh').unlink()
        self.select('novo-provedor')
        code, _, err = self.command('gerar', '--esteira')
        self.assertEqual(code, EXIT_INVALID_CONFIG)
        self.assertIn('scripts/alvo.sh', err)

    def test_artefato_reservado_ou_desconhecido_e_recusado(self):
        for name in ('pacote', 'estatico', 'desconhecido'):
            with self.subTest(name=name):
                self.select('vps-docker', name)
                code, _, err = self.command('gerar', '--esteira')
                self.assertEqual(code, EXIT_INVALID_CONFIG)
                self.assertIn(name, err)

    def test_capacidade_incompativel_e_recusada(self):
        self.target(text=TARGET.replace('["imagem"]', '["pacote"]'))
        self.select('novo-provedor')
        with self.assertRaisesRegex(BbError, 'não aceita.*imagem'):
            generator.build_plan(self.root, install_pipeline=True)

    def test_artefato_sem_script_de_promocao_e_recusado(self):
        script = self.root / '.bigbang/esteira/perfis/deploy/scripts/promover.sh'
        script.unlink()
        code, _, err = self.command('gerar', '--esteira')
        self.assertEqual(code, EXIT_INVALID_CONFIG)
        self.assertIn('promover.sh', err)

    def test_formato_por_hashes_nao_e_entregue_pela_esteira_de_imagens(self):
        path = self.artifacts / 'imagem/artefato.toml'
        path.write_text(path.read_text().replace('identidade = "digest"', 'identidade = "sha256"'))
        code, _, err = self.command('gerar', '--esteira')
        self.assertEqual(code, EXIT_INVALID_CONFIG)
        self.assertIn('entrega por hashes', err)

    def test_verificar_detecta_contrato_invalido_no_template(self):
        (self.root / 'bigbang.toml').unlink()
        self.target(text=TARGET.replace('implementado', 'errado'))
        self.assertTrue(any('situacao' in problem for problem in verify.run(self.root)))

    def test_contrato_invalido_e_recusado(self):
        invalid = [TARGET + 'segredoo = "x"\n',
                   TARGET.replace('implementado', 'pronto'),
                   TARGET.replace('"voltar"', '"checar"'),
                   TARGET.replace('["imagem"]', '[]'),
                   TARGET.replace('["TESTE_TOKEN"]', '["TOKEN", "TOKEN"]'),
                   TARGET.replace('["TESTE_APP"]', '["TESTE_TOKEN"]'),
                   TARGET.replace('["TESTE_TOKEN"]', '["TOKEN=${{secrets.X}}"]'),
                   TARGET.replace('["TESTE_APP"]', '["teste-app"]'),
                   TARGET.replace('situacao =', 'situacao = [')]
        for text in invalid:
            with self.subTest(text=text):
                self.target(text=text)
                self.select('novo-provedor')
                with self.assertRaises(BbError):
                    generator.build_plan(self.root, install_pipeline=True)

    def test_nao_le_script_por_link_fora_do_adaptador(self):
        folder = self.target()
        script = folder / 'scripts/alvo.sh'
        script.unlink()
        script.symlink_to(self.root / '.bigbang/bin/bb')
        self.select('novo-provedor')
        with self.assertRaisesRegex(BbError, 'fora'):
            generator.build_plan(self.root, install_pipeline=True)

    def test_nome_nao_escapa_do_catalogo(self):
        for name in ('../vps-docker', 'VPS', 'vps-docker/../../..'):
            with self.subTest(name=name):
                with self.assertRaises(BbError):
                    deploy_catalog.read_target(self.root, name)

    def test_catalogo_funciona_antes_da_fundacao_e_nao_escreve(self):
        (self.root / 'bigbang.toml').unlink()
        code, out, err = self.command('alvos')
        self.assertEqual((code, err), (0, ''))
        self.assertIn('vps-docker: implementado', out)
        self.assertIn('tsuru: reservado', out)
        self.assertIn('imagem: implementado', out)
        self.assertFalse((self.root / 'bigbang.toml').exists())

    def test_catalogo_exibe_adaptador_quebrado_e_sai_com_falha(self):
        self.target(text=TARGET.replace('implementado', 'desconhecido'))
        code, out, err = self.command('alvos')
        self.assertEqual(code, EXIT_VERIFICATION_FAILED)
        self.assertIn('novo-provedor: inválido', out)
        self.assertIn('situacao', err)

    def test_troca_de_alvo_remove_arquivo_obsoleto(self):
        folder = self.target()
        extra = folder / 'arquivos/.github/bb-antigo.md'
        extra.parent.mkdir(parents=True)
        extra.write_text('# Antigo\n', encoding='utf-8')
        self.select('novo-provedor')
        generator.apply(generator.build_plan(self.root, install_pipeline=True), self.root)
        self.select('vps-docker')
        plan = generator.build_plan(self.root)
        self.assertIn('.github/bb-antigo.md', plan.stale)

    def test_compilado_nao_depende_de_catalogo_deploy(self):
        text = exemplo_toml().replace('perfil = "deploy"', 'perfil = "compilado"').replace('alvo = "vps-docker"', 'alvo = ""')
        (self.root / 'bigbang.toml').write_text(text, encoding='utf-8')
        shutil.rmtree(self.root / '.bigbang/esteira/perfis/deploy')
        plan = generator.build_plan(self.root, install_pipeline=True)
        self.assertIn('.github/workflows/bb-candidata.yml', plan.expected)

    def test_esquema_recusa_injecao_em_seletores(self):
        cfg = config.parse(exemplo_toml())
        for section, key in [('entrega', 'alvo'), ('deploy', 'artefato')]:
            for value in ('../imagem', '${{secrets.X}}', 'imagem\nnome: novo', 'imagem\n'):
                with self.subTest(section=section, value=value):
                    changed = copy.deepcopy(cfg)
                    changed[section][key] = value
                    self.assertTrue(config.validate(changed))


if __name__ == '__main__':
    unittest.main()
