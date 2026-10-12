"""Immutable SHA-256 manifests for package and static deploy artifacts (#179)."""
import argparse
import glob
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import tarfile

from .errors import BbError, EXIT_INVALID_CONFIG, EXIT_INVALID_STATE

MANIFEST = "manifesto.json"
MANIFEST_SUM = "manifesto.sha256"
ARCHIVE = "artefato.tar.gz"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def _fail(message, code=EXIT_INVALID_STATE):
    raise BbError(message, code)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        _fail(f"caminho inseguro no manifesto: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        _fail(f"caminho inseguro no manifesto: {value!r}")
    return path.as_posix()


def _check_source(root, path):
    if path.is_symlink():
        _fail(f"artefato não pode incluir link simbólico: {path}", EXIT_INVALID_CONFIG)
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        _fail(f"caminho do artefato aponta para fora do projeto: {path}", EXIT_INVALID_CONFIG)
    current = path.parent
    while current != root and current != current.parent:
        if current.is_symlink():
            _fail(f"caminho do artefato atravessa link simbólico: {current}", EXIT_INVALID_CONFIG)
        current = current.parent
    if not path.is_file():
        _fail(f"caminho do artefato não é um arquivo regular: {path}", EXIT_INVALID_CONFIG)
    return resolved


def _files(root, patterns):
    root = Path(root).resolve()
    if not isinstance(patterns, (list, tuple)) or not patterns:
        _fail("entrega.caminhos_artefato deve selecionar pelo menos um arquivo", EXIT_INVALID_CONFIG)
    found = {}
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern or "\\" in pattern:
            _fail(f"padrão de artefato inválido: {pattern!r}", EXIT_INVALID_CONFIG)
        relative = PurePosixPath(pattern)
        if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
            _fail(f"padrão de artefato inseguro: {pattern!r}", EXIT_INVALID_CONFIG)
        matches = [Path(item) for item in glob.glob(str(root / pattern), recursive=True)]
        if not matches:
            _fail(f"padrão de artefato sem correspondência: {pattern}", EXIT_INVALID_CONFIG)
        for match in matches:
            if match.is_symlink():
                _fail(f"artefato não pode incluir link simbólico: {match}", EXIT_INVALID_CONFIG)
            if match.is_dir():
                for folder, directories, filenames in os.walk(match, followlinks=False):
                    directory = Path(folder)
                    for name in directories:
                        if (directory / name).is_symlink():
                            _fail(f"artefato não pode atravessar link simbólico: {directory / name}",
                                  EXIT_INVALID_CONFIG)
                    for name in filenames:
                        candidate = directory / name
                        if candidate.is_symlink():
                            _fail(f"artefato não pode incluir link simbólico: {candidate}", EXIT_INVALID_CONFIG)
                        resolved = _check_source(root, candidate)
                        found[resolved.relative_to(root).as_posix()] = resolved
            else:
                resolved = _check_source(root, match)
                found[resolved.relative_to(root).as_posix()] = resolved
    if not found:
        _fail("os padrões de artefato não selecionaram arquivos", EXIT_INVALID_CONFIG)
    if len(found) > 10000:
        _fail("entrega.caminhos_artefato selecionou mais de 10000 arquivos", EXIT_INVALID_CONFIG)
    return [(name, found[name]) for name in sorted(found)]


def _write_archive(destination, files):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, source in files:
                info = tarfile.TarInfo(name)
                info.size = source.stat().st_size
                info.mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with source.open("rb") as stream:
                    archive.addfile(info, stream)


def build(root, format_name, patterns, output_dir):
    """Build the selected files into a deterministic bundle and write a detached hash for the manifest."""
    if format_name not in ("pacote", "estatico"):
        _fail(f"formato não suportado para manifesto SHA-256: {format_name}", EXIT_INVALID_CONFIG)
    root = Path(root).resolve()
    files = _files(root, patterns)
    if format_name == "pacote" and len(files) != 1:
        _fail("formato pacote exige exatamente um arquivo em entrega.caminhos_artefato", EXIT_INVALID_CONFIG)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE
    _write_archive(archive_path, files)
    payload = {
        "versao": 1,
        "formato": format_name,
        "artefato": {"arquivo": ARCHIVE, "sha256": _sha256(archive_path), "tamanho": archive_path.stat().st_size},
        "arquivos": [
            {"caminho": name, "sha256": _sha256(path), "tamanho": path.stat().st_size}
            for name, path in files
        ],
    }
    manifest_bytes = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_path = output_dir / MANIFEST
    manifest_path.write_bytes(manifest_bytes)
    (output_dir / MANIFEST_SUM).write_text(
        f"{hashlib.sha256(manifest_bytes).hexdigest()}  {MANIFEST}\n", encoding="ascii", newline="\n")
    return manifest_path


def build_from_config(root, output_dir):
    from . import config
    loaded = config.load(root)
    return build(root, loaded["deploy"]["artefato"], loaded["entrega"]["caminhos_artefato"], output_dir)


def verify(manifest_path):
    """Verify the detached manifest hash, archive hash, safe tar paths and every source-file digest."""
    manifest_path = Path(manifest_path)
    try:
        if manifest_path.is_symlink() or (manifest_path.parent / MANIFEST_SUM).is_symlink():
            _fail("manifesto ou hash do manifesto é link simbólico")
        data = manifest_path.read_bytes()
        if len(data) > MAX_MANIFEST_BYTES:
            _fail("manifesto excede o limite permitido")
        expected = (manifest_path.parent / MANIFEST_SUM).read_text(encoding="ascii").split()
        if len(expected) != 2 or expected[1] != manifest_path.name or not hmac.compare_digest(
                expected[0], hashlib.sha256(data).hexdigest()):
            _fail("SHA-256 do manifesto não confere")
        manifest = json.loads(data)
    except BbError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"manifesto inválido ou incompleto ({exc})")
    if not isinstance(manifest, dict) or set(manifest) != {"versao", "formato", "artefato", "arquivos"}:
        _fail("estrutura do manifesto inválida")
    if manifest["versao"] != 1 or manifest["formato"] not in ("pacote", "estatico"):
        _fail("versão ou formato do manifesto não suportado")
    artifact = manifest["artefato"]
    if not isinstance(artifact, dict) or set(artifact) != {"arquivo", "sha256", "tamanho"} or \
            type(artifact.get("tamanho")) is not int or artifact["tamanho"] < 0:
        _fail("identidade do artefato no manifesto inválida")
    archive_name = _safe_relative(artifact["arquivo"])
    if archive_name != ARCHIVE or not isinstance(artifact["sha256"], str) or len(artifact["sha256"]) != 64 or \
            any(char not in "0123456789abcdef" for char in artifact["sha256"]):
        _fail("identidade SHA-256 do artefato inválida")
    archive_path = manifest_path.parent / archive_name
    if archive_path.is_symlink() or not archive_path.is_file() or archive_path.stat().st_size != artifact["tamanho"] or \
            not hmac.compare_digest(_sha256(archive_path), artifact["sha256"]):
        _fail("SHA-256 ou tamanho do pacote não confere")
    entries = manifest["arquivos"]
    if not isinstance(entries, list) or not entries or len(entries) > 10000:
        _fail("lista de arquivos do manifesto inválida")
    expected_files = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"caminho", "sha256", "tamanho"}:
            _fail("entrada de arquivo no manifesto inválida")
        name = _safe_relative(entry["caminho"])
        digest = entry["sha256"]
        size = entry["tamanho"]
        if name in expected_files or not isinstance(digest, str) or len(digest) != 64 or \
                any(char not in "0123456789abcdef" for char in digest) or type(size) is not int or size < 0:
            _fail(f"entrada inválida no manifesto: {name}")
        expected_files[name] = (digest, size)
    if manifest["formato"] == "pacote" and len(expected_files) != 1:
        _fail("manifesto de pacote deve conter um arquivo")
    actual = set()
    try:
        with tarfile.open(archive_path, "r|gz") as archive:
            for member in archive:
                name = _safe_relative(member.name)
                if not member.isfile() or name in actual or name not in expected_files:
                    _fail(f"entrada suspeita ou inesperada no pacote: {member.name}")
                source = archive.extractfile(member)
                if source is None:
                    _fail(f"não foi possível ler o arquivo do pacote: {name}")
                expected_digest, expected_size = expected_files[name]
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
                    if size > expected_size:
                        _fail(f"tamanho excedido no arquivo do pacote: {name}")
                if size != expected_size or not hmac.compare_digest(digest.hexdigest(), expected_digest):
                    _fail(f"SHA-256 ou tamanho não confere para {name}")
                actual.add(name)
    except BbError:
        raise
    except (OSError, tarfile.TarError) as exc:
        _fail(f"pacote inválido ou corrompido ({exc})")
    if actual != set(expected_files):
        _fail("arquivos do pacote divergem do manifesto")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cria e confere manifestos de artefatos SHA-256")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--root", default=".")
    build_parser.add_argument("--output", default="candidata")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("manifest")
    args = parser.parse_args(argv)
    if args.command == "build":
        manifest = build_from_config(args.root, args.output)
        print(manifest)
    else:
        manifest = verify(args.manifest)
        print(f"{manifest['formato']} sha256:{_sha256(args.manifest)}")


if __name__ == "__main__":
    main()
