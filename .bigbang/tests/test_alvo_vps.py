"""Deploy target vps-docker (spec 14.4).

Fast tests use a fake ssh/scp. The end-to-end test (BB_TESTE_DOCKER=1) runs a real flow: a local registry, a
container acting as the VPS (sshd + Docker CLI over the host's socket) and two versions of an app: publicar, migrar,
saude and voltar, always by digest."""
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from _raiz import BIGBANG, exemplo_toml

ALVO = os.path.join(BIGBANG, "esteira", "perfis", "deploy", "alvos", "vps-docker", "scripts", "alvo.sh")
BB = os.path.join(BIGBANG, "bin", "bb.py")
DIGEST = "ghcr.io/dono/app@sha256:" + "a" * 64
FAKE = """#!/usr/bin/env bash
printf '%s\\n' "$(basename "$0") $*" >> "$LOG"
if [ "$(basename "$0")" = ssh ]; then
  entrada=$(cat); printf '%s\\n' "$entrada" >> "$LOG"
  if [ -n "${FALHAR_SE:-}" ] && [[ "$entrada" == *"$FALHAR_SE"* ]]; then exit 1; fi
fi
exit 0
"""
DIGEST_WEB = "ghcr.io/dono/app-web@sha256:" + "b" * 64


def projeto(pasta, url="https://staging.exemplo.com", deploy=""):
    """A project from the example bigbang.toml; `deploy` adds lines to [deploy]."""
    os.makedirs(os.path.join(pasta, ".bigbang"))
    shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(pasta, ".bigbang", "VERSION"))
    toml = exemplo_toml().replace('url_staging = "https://staging.exemplo.com"', f'url_staging = "{url}"')
    toml = toml.replace('smoke = "npm run test:smoke"\n', 'smoke = "npm run test:smoke"\n' + deploy)
    with open(os.path.join(pasta, "bigbang.toml"), "w", encoding="utf-8") as arquivo:
        arquivo.write(toml)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "bash indisponível")
class AlvoComSshFalso(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta)
        projeto(self.pasta)
        os.makedirs(os.path.join(self.pasta, "deploy"))
        with open(os.path.join(self.pasta, "deploy", "compose.yaml"), "w", encoding="utf-8") as arquivo:
            arquivo.write("services:\n  app:\n    image: ${BB_IMAGEM}\n")
        self.bin = os.path.join(self.pasta, "bin")
        os.makedirs(self.bin)
        for nome in ("ssh", "scp"):
            caminho = os.path.join(self.bin, nome)
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write(FAKE)
            os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.pasta, "log")

    def alvo(self, *args, **env):
        ambiente = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"], "LOG": self.log,
                    "BB": f"{sys.executable} {BB} --raiz {self.pasta}", "VPS_HOST": "vps.exemplo",
                    "VPS_USUARIO": "deploy", "VPS_CHAVE_SSH": "CHAVE-FICTICIA",
                    "VPS_KNOWN_HOSTS": "vps.exemplo ssh-ed25519 AAAA", **env}
        return subprocess.run(["bash", ALVO, *args], cwd=self.pasta, env=ambiente, capture_output=True, text=True,
                              check=False)

    def registro(self):
        with open(self.log, encoding="utf-8") as arquivo:
            return arquivo.read()

    def test_publicar_por_digest(self):
        r = self.alvo("publicar", "staging", DIGEST)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = self.registro()
        self.assertIn("StrictHostKeyChecking=yes", log)
        self.assertIn("deploy/compose.yaml deploy@vps.exemplo:/opt/meu-sistema/staging/compose.yaml", log)
        self.assertIn(f"BB_IMAGEM_APP={DIGEST}\\nBB_IMAGEM={DIGEST}", log)
        self.assertIn("cp imagem.env imagem.anterior.env", log)
        self.assertIn("docker compose -p meu-sistema-staging --env-file imagem.env up -d --remove-orphans app", log)
        self.assertNotIn("CHAVE-FICTICIA", log)  # the key goes to a file, never into a command line

    def test_sudo_e_env_do_servidor(self):
        r = self.alvo("publicar", "producao", DIGEST, VPS_DOCKER_SUDO="true", VPS_ENV_ARQUIVO="/srv/app/.env")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sudo -n docker compose -p meu-sistema-producao --env-file imagem.env --env-file /srv/app/.env "
                      "up -d --remove-orphans app", self.registro())

    def test_recusa_tag_e_servidor_sem_chave_conhecida(self):
        self.assertEqual(self.alvo("publicar", "staging", "ghcr.io/dono/app:latest").returncode, 2)
        r = self.alvo("publicar", "staging", DIGEST, VPS_KNOWN_HOSTS="")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("VPS_KNOWN_HOSTS", r.stderr)

    def test_migrar_antes_com_a_imagem_nova(self):
        r = self.alvo("migrar", "producao", DIGEST)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("docker compose -p meu-sistema-producao --env-file imagem.novo.env --profile migrar run --rm -T migrar",
                      self.registro())

    def test_ambiente_invalido(self):
        self.assertEqual(self.alvo("publicar", "teste", DIGEST).returncode, 2)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "bash indisponível")
class AlvoComVariosServicos(AlvoComSshFalso):
    """Two images (api and web), a pre-check service and a custom health path."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta)
        projeto(self.pasta, deploy='servicos = ["api=apps/api/Dockerfile", "web=apps/web/Dockerfile"]\n'
                                   'servico_checar = "checar"\ncaminho_saude = "/api/v1/health/live"\n')
        os.makedirs(os.path.join(self.pasta, "deploy"))
        with open(os.path.join(self.pasta, "deploy", "compose.yaml"), "w", encoding="utf-8") as arquivo:
            arquivo.write("services:\n  api:\n    image: ${BB_IMAGEM_API}\n")
        self.bin = os.path.join(self.pasta, "bin")
        os.makedirs(self.bin)
        for nome in ("ssh", "scp"):
            caminho = os.path.join(self.bin, nome)
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write(FAKE)
            os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.pasta, "log")

    CONJUNTO = f"api={DIGEST},web={DIGEST_WEB}"

    def test_publicar_por_digest(self):
        r = self.alvo("publicar", "staging", self.CONJUNTO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = self.registro()
        self.assertIn(f"BB_IMAGEM_API={DIGEST}\\nBB_IMAGEM_WEB={DIGEST_WEB}\\nBB_IMAGEM={DIGEST}", log)
        self.assertIn("pull api web", log)
        self.assertIn("up -d --remove-orphans api web", log)  # only the published services: the database stays up

    def test_sudo_e_env_do_servidor(self):
        r = self.alvo("publicar", "producao", self.CONJUNTO, VPS_DOCKER_SUDO="true")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sudo -n docker compose -p meu-sistema-producao --env-file imagem.env up -d --remove-orphans api web",
                      self.registro())

    def test_conjunto_incompleto_ou_por_tag(self):
        self.assertEqual(self.alvo("publicar", "staging", f"api={DIGEST}").returncode, 2)
        self.assertEqual(self.alvo("publicar", "staging", DIGEST).returncode, 2)
        self.assertEqual(self.alvo("publicar", "staging", f"api={DIGEST},web=ghcr.io/x:latest").returncode, 2)
        self.assertEqual(self.alvo("publicar", "staging", f"api={DIGEST},banco={DIGEST_WEB}").returncode, 2)

    def test_recusa_tag_e_servidor_sem_chave_conhecida(self):
        r = self.alvo("publicar", "staging", self.CONJUNTO, VPS_KNOWN_HOSTS="")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("VPS_KNOWN_HOSTS", r.stderr)

    def test_migrar_antes_com_a_imagem_nova(self):
        r = self.alvo("migrar", "producao", self.CONJUNTO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = self.registro()
        checar = log.index("--profile checar run --rm -T checar")
        self.assertLess(checar, log.index("--profile migrar run --rm -T migrar"))  # pre-check first

    def test_pre_checagem_que_falha_nao_troca_a_versao(self):
        r = self.alvo("migrar", "producao", self.CONJUNTO, FALHAR_SE="--profile checar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("a versão no ar não foi trocada", r.stdout + r.stderr)
        self.assertNotIn("up -d", self.registro())

    def test_saude_no_caminho_configurado(self):
        falso = os.path.join(self.bin, "curl")
        with open(falso, "w", encoding="utf-8") as arquivo:
            arquivo.write('#!/usr/bin/env bash\nprintf \'%s\\n\' "curl $*" >> "$LOG"\n')
        os.chmod(falso, 0o755)
        r = self.alvo("saude", "staging")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("https://staging.exemplo.com/api/v1/health/live", self.registro())

    def test_voltar_restaura_o_conjunto_da_release(self):
        falso = os.path.join(self.bin, "gh")
        with open(falso, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"#!/usr/bin/env bash\nprintf 'api={DIGEST}\\nweb={DIGEST_WEB}\\n'\n")
        os.chmod(falso, 0o755)
        r = self.alvo("voltar", "producao", "v1.0.0", GITHUB_REPOSITORY="dono/repo")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"BB_IMAGEM_WEB={DIGEST_WEB}", self.registro())
        self.assertNotIn("--profile migrar", self.registro())  # going back never migrates

    def test_ambiente_invalido(self):
        self.assertEqual(self.alvo("publicar", "teste", self.CONJUNTO).returncode, 2)


def livre(porta):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


VPS_DOCKERFILE = """FROM alpine:3.20
RUN apk add --no-cache openssh docker-cli docker-cli-compose bash curl && ssh-keygen -A \\
 && sed -i 's/#PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config && mkdir -p /root/.ssh
COPY chave.pub /root/.ssh/authorized_keys
CMD ["/usr/sbin/sshd", "-D", "-e"]
"""
APP_DOCKERFILE = """FROM python:3.12-alpine
ARG VERSAO
ENV VERSAO=$VERSAO
COPY app.py /app.py
CMD ["python", "/app.py"]
"""
APP = """import http.server, json, os, sys
if sys.argv[1:] == ["migrar"]:
    open("/dados/migracoes", "a").write(os.environ["VERSAO"] + "\\n"); sys.exit(0)
if sys.argv[1:] == ["checar"]:
    sys.exit(0 if os.environ.get("SEGREDO_DO_SERVIDOR") == "ok" else 1)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = json.dumps({"status": "ok", "versao": os.environ["VERSAO"], "papel": os.environ["PAPEL"]}).encode()
        self.send_response(200 if self.path == "/api/v1/health/live" else 404); self.end_headers(); self.wfile.write(corpo)
http.server.HTTPServer(("", 8080), H).serve_forever()
"""
# Two published services (api, web), a database that a deploy never recreates, the migration and a pre-check that
# needs a value from the server's env-file (VPS_ENV_ARQUIVO).
COMPOSE = """services:
  api:
    image: ${BB_IMAGEM_API}
    environment: {PAPEL: api}
    ports: ["18080:8080"]
    volumes: ["bbteste-dados:/dados"]
    depends_on: [banco]
  web:
    image: ${BB_IMAGEM_WEB}
    environment: {PAPEL: web}
    ports: ["18081:8080"]
  banco:
    image: alpine:3.20
    command: ["sleep", "infinity"]
  migrar:
    image: ${BB_IMAGEM_API}
    command: ["python", "/app.py", "migrar"]
    volumes: ["bbteste-dados:/dados"]
    profiles: ["migrar"]
  checar:
    image: ${BB_IMAGEM_API}
    command: ["python", "/app.py", "checar"]
    environment: {SEGREDO_DO_SERVIDOR: "${SEGREDO_DO_SERVIDOR:-}"}
    profiles: ["checar"]
volumes:
  bbteste-dados:
"""
DEPLOY = ('servicos = ["api=Dockerfile", "web=web/Dockerfile"]\nservico_checar = "checar"\n'
          'caminho_saude = "/api/v1/health/live"\n')


@unittest.skipUnless(os.environ.get("BB_TESTE_DOCKER") == "1" and shutil.which("docker"),
                     "teste com Docker de verdade: rode com BB_TESTE_DOCKER=1")
class AlvoNumServidorEmConteiner(unittest.TestCase):
    """publicar → saude → (v2) migrar → publicar → voltar, against a container acting as the VPS."""

    @classmethod
    def docker(cls, *args, entrada=None):
        return subprocess.run(["docker", *args], capture_output=True, text=True, check=True, input=entrada).stdout

    @classmethod
    def setUpClass(cls):
        if not all(livre(porta) for porta in (15000, 2222, 18080, 18081)):
            raise unittest.SkipTest("portas 15000, 2222, 18080 ou 18081 ocupadas")
        cls.pasta = tempfile.mkdtemp()
        p = cls.pasta
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", f"{p}/chave"], check=True)
        for nome, texto in (("Dockerfile.vps", VPS_DOCKERFILE), ("Dockerfile.app", APP_DOCKERFILE), ("app.py", APP)):
            with open(f"{p}/{nome}", "w", encoding="utf-8") as arquivo:
                arquivo.write(texto)
        cls.docker("run", "-d", "--rm", "--name", "bbteste-registro", "-p", "15000:5000", "registry:2")
        cls.docker("build", "-q", "-t", "bbteste-vps", "-f", f"{p}/Dockerfile.vps", p)
        cls.docker("run", "-d", "--rm", "--name", "bbteste-vps", "-p", "2222:22",
                   "-v", "/var/run/docker.sock:/var/run/docker.sock", "bbteste-vps")
        cls.docker("exec", "bbteste-vps", "sh", "-c", "mkdir -p /srv && echo SEGREDO_DO_SERVIDOR=ok > /srv/app.env")
        cls.digests = {}
        for versao in ("1.0.0", "2.0.0"):
            tag = f"localhost:15000/bbteste-app:{versao}"
            cls.docker("build", "-q", "-t", tag, "--build-arg", f"VERSAO={versao}", "-f", f"{p}/Dockerfile.app", p)
            cls.docker("push", "-q", tag)
            digest = json.loads(cls.docker("inspect", tag))[0]["RepoDigests"][0]
            cls.digests[versao] = digest
        time.sleep(2)
        chave_host = ""
        for _ in range(20):
            chave_host = subprocess.run(["ssh-keyscan", "-p", "2222", "-t", "ed25519", "127.0.0.1"],
                                        capture_output=True, text=True).stdout.strip()
            if chave_host:
                break
            time.sleep(1)
        cls.projeto = os.path.join(p, "projeto")
        os.makedirs(os.path.join(cls.projeto, "deploy"))
        projeto(cls.projeto, deploy=DEPLOY)
        with open(os.path.join(cls.projeto, "deploy", "compose.yaml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(COMPOSE)
        with open(f"{p}/chave", encoding="utf-8") as arquivo:
            chave = arquivo.read()
        cls.env = {**os.environ, "BB": f"{sys.executable} {BB} --raiz {cls.projeto}", "VPS_HOST": "127.0.0.1",
                   "VPS_PORTA": "2222", "VPS_USUARIO": "root", "VPS_CHAVE_SSH": chave, "VPS_KNOWN_HOSTS": chave_host,
                   "VPS_PASTA": "/tmp/bbteste/staging", "VPS_ENV_ARQUIVO": "/srv/app.env",
                   "SAUDE_INTERVALO": "1", "SAUDE_TENTATIVAS": "30",
                   "SAUDE_URL": "http://127.0.0.1:18080"}

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "compose", "-p", "meu-sistema-staging", "-f",
                        os.path.join(cls.projeto, "deploy", "compose.yaml"), "down", "-v"],
                       capture_output=True, env={**os.environ, "BB_IMAGEM_API": "x", "BB_IMAGEM_WEB": "x"})
        for nome in ("bbteste-vps", "bbteste-registro"):
            subprocess.run(["docker", "rm", "-f", nome], capture_output=True)
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def alvo(self, *args, env=None, codigo=0):
        r = subprocess.run(["bash", ALVO, *args], cwd=self.projeto, env={**self.env, **(env or {})},
                           capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, codigo, r.stdout + r.stderr)
        return r.stdout

    def versao_no_ar(self, porta=18080):
        """The version answering on the port; waits up to 30 s (the health check only looks at the first service)."""
        import urllib.request
        for tentativa in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/v1/health/live", timeout=5) as resposta:
                    return json.loads(resposta.read())["versao"]
            except OSError:
                if tentativa == 29:
                    raise
                time.sleep(1)

    def banco(self):
        return subprocess.run(["docker", "ps", "-q", "-f", "name=meu-sistema-staging-banco"], capture_output=True,
                              text=True).stdout.strip()

    @staticmethod
    def conjunto(digest):
        return f"api={digest},web={digest}"

    def migracoes(self):
        return subprocess.run(["docker", "run", "--rm", "-v", "meu-sistema-staging_bbteste-dados:/dados", "alpine:3.20",
                               "cat", "/dados/migracoes"], capture_output=True, text=True).stdout.split()

    def test_ciclo_completo(self):
        v1, v2 = self.conjunto(self.digests["1.0.0"]), self.conjunto(self.digests["2.0.0"])
        self.alvo("migrar", "staging", v1)
        self.alvo("publicar", "staging", v1)
        self.alvo("saude", "staging")
        self.assertEqual((self.versao_no_ar(), self.versao_no_ar(18081)), ("1.0.0", "1.0.0"))
        banco = self.banco()
        self.assertTrue(banco)
        # a pre-check that fails (the server's env-file lacks the value) stops before migrating, nothing changes
        self.alvo("migrar", "staging", v2, env={"VPS_ENV_ARQUIVO": "/srv/inexistente.env"}, codigo=1)
        self.assertEqual(self.migracoes(), ["1.0.0"])
        self.alvo("migrar", "staging", v2)  # migration runs with the NEW image before the switch
        self.assertEqual(self.versao_no_ar(), "1.0.0")
        self.alvo("publicar", "staging", v2)
        self.alvo("saude", "staging")
        self.assertEqual((self.versao_no_ar(), self.versao_no_ar(18081)), ("2.0.0", "2.0.0"))
        self.assertEqual(self.migracoes(), ["1.0.0", "2.0.0"])
        self.assertEqual(self.banco(), banco)  # the database is never recreated by a deploy
        # voltar: the image set recorded in the Release v1.0.0 (gh is faked to return imagem.txt)
        falso = os.path.join(self.pasta, "gh")
        with open(falso, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"#!/usr/bin/env bash\nprintf '%s\\n' api={self.digests['1.0.0']} "
                          f"web={self.digests['1.0.0']}\n")
        os.chmod(falso, 0o755)
        self.alvo("voltar", "staging", "v1.0.0",
                  env={"PATH": self.pasta + os.pathsep + os.environ["PATH"], "GITHUB_REPOSITORY": "dono/repo"})
        self.alvo("saude", "staging")
        self.assertEqual((self.versao_no_ar(), self.versao_no_ar(18081)), ("1.0.0", "1.0.0"))
        self.assertEqual(self.migracoes(), ["1.0.0", "2.0.0"])  # going back never undoes a migration
        self.assertEqual(self.banco(), banco)


if __name__ == "__main__":
    unittest.main()
