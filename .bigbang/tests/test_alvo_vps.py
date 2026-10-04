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
[ "$(basename "$0")" = ssh ] && cat >> "$LOG"
exit 0
"""


def projeto(pasta, url="https://staging.exemplo.com"):
    os.makedirs(os.path.join(pasta, ".bigbang"))
    shutil.copy(os.path.join(BIGBANG, "VERSION"), os.path.join(pasta, ".bigbang", "VERSION"))
    toml = exemplo_toml().replace('url_staging = "https://staging.exemplo.com"', f'url_staging = "{url}"')
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
        self.assertIn(f"BB_IMAGEM=%s\\n' {DIGEST}", log)
        self.assertIn("cp imagem.env imagem.anterior.env", log)
        self.assertNotIn("CHAVE-FICTICIA", log)  # the key goes to a file, never into a command line

    def test_recusa_tag_e_servidor_sem_chave_conhecida(self):
        self.assertEqual(self.alvo("publicar", "staging", "ghcr.io/dono/app:latest").returncode, 2)
        r = self.alvo("publicar", "staging", DIGEST, VPS_KNOWN_HOSTS="")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("VPS_KNOWN_HOSTS", r.stderr)

    def test_migrar_antes_com_a_imagem_nova(self):
        r = self.alvo("migrar", "producao", DIGEST)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"BB_IMAGEM={DIGEST} docker compose -p meu-sistema-producao --profile migrar run --rm migrar",
                      self.registro())

    def test_ambiente_invalido(self):
        self.assertEqual(self.alvo("publicar", "teste", DIGEST).returncode, 2)


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
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = json.dumps({"status": "ok", "versao": os.environ["VERSAO"]}).encode()
        self.send_response(200 if self.path == "/api/health" else 404); self.end_headers(); self.wfile.write(corpo)
http.server.HTTPServer(("", 8080), H).serve_forever()
"""
COMPOSE = """services:
  app:
    image: ${BB_IMAGEM}
    ports: ["18080:8080"]
    volumes: ["bbteste-dados:/dados"]
  migrar:
    image: ${BB_IMAGEM}
    command: ["python", "/app.py", "migrar"]
    volumes: ["bbteste-dados:/dados"]
    profiles: ["migrar"]
volumes:
  bbteste-dados:
"""


@unittest.skipUnless(os.environ.get("BB_TESTE_DOCKER") == "1" and shutil.which("docker"),
                     "teste com Docker de verdade: rode com BB_TESTE_DOCKER=1")
class AlvoNumServidorEmConteiner(unittest.TestCase):
    """publicar → saude → (v2) migrar → publicar → voltar, against a container acting as the VPS."""

    @classmethod
    def docker(cls, *args, entrada=None):
        return subprocess.run(["docker", *args], capture_output=True, text=True, check=True, input=entrada).stdout

    @classmethod
    def setUpClass(cls):
        if not (livre(15000) and livre(2222) and livre(18080)):
            raise unittest.SkipTest("portas 15000, 2222 ou 18080 ocupadas")
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
        projeto(cls.projeto)
        with open(os.path.join(cls.projeto, "deploy", "compose.yaml"), "w", encoding="utf-8") as arquivo:
            arquivo.write(COMPOSE)
        with open(f"{p}/chave", encoding="utf-8") as arquivo:
            chave = arquivo.read()
        cls.env = {**os.environ, "BB": f"{sys.executable} {BB} --raiz {cls.projeto}", "VPS_HOST": "127.0.0.1",
                   "VPS_PORTA": "2222", "VPS_USUARIO": "root", "VPS_CHAVE_SSH": chave, "VPS_KNOWN_HOSTS": chave_host,
                   "VPS_PASTA": "/tmp/bbteste/staging", "SAUDE_INTERVALO": "1", "SAUDE_TENTATIVAS": "30",
                   "SAUDE_URL": "http://127.0.0.1:18080"}

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "compose", "-p", "meu-sistema-staging", "-f",
                        os.path.join(cls.projeto, "deploy", "compose.yaml"), "down", "-v"],
                       capture_output=True, env={**os.environ, "BB_IMAGEM": "x"})
        for nome in ("bbteste-vps", "bbteste-registro"):
            subprocess.run(["docker", "rm", "-f", nome], capture_output=True)
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def alvo(self, *args, env=None):
        r = subprocess.run(["bash", ALVO, *args], cwd=self.projeto, env={**self.env, **(env or {})},
                           capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def versao_no_ar(self):
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:18080/api/health", timeout=5) as resposta:
            return json.loads(resposta.read())["versao"]

    def migracoes(self):
        return subprocess.run(["docker", "run", "--rm", "-v", "meu-sistema-staging_bbteste-dados:/dados", "alpine:3.20",
                               "cat", "/dados/migracoes"], capture_output=True, text=True).stdout.split()

    def test_ciclo_completo(self):
        v1, v2 = self.digests["1.0.0"], self.digests["2.0.0"]
        self.alvo("migrar", "staging", v1)
        self.alvo("publicar", "staging", v1)
        self.alvo("saude", "staging")
        self.assertEqual(self.versao_no_ar(), "1.0.0")
        self.alvo("migrar", "staging", v2)  # migration runs with the NEW image before the switch
        self.assertEqual(self.versao_no_ar(), "1.0.0")
        self.alvo("publicar", "staging", v2)
        self.alvo("saude", "staging")
        self.assertEqual(self.versao_no_ar(), "2.0.0")
        self.assertEqual(self.migracoes(), ["1.0.0", "2.0.0"])
        # voltar: the image recorded in the Release v1.0.0 (gh is faked to return imagem.txt)
        falso = os.path.join(self.pasta, "gh")
        with open(falso, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"#!/usr/bin/env bash\necho {v1}\n")
        os.chmod(falso, 0o755)
        self.alvo("voltar", "staging", "v1.0.0",
                  env={"PATH": self.pasta + os.pathsep + os.environ["PATH"], "GITHUB_REPOSITORY": "dono/repo"})
        self.alvo("saude", "staging")
        self.assertEqual(self.versao_no_ar(), "1.0.0")
        self.assertEqual(self.migracoes(), ["1.0.0", "2.0.0"])  # going back never undoes a migration


if __name__ == "__main__":
    unittest.main()
