"""Locations inside a project that uses the Big Bang."""
import os

FRAMEWORK_DIR = ".bigbang"
CONFIG_FILE = "bigbang.toml"


def framework_dir(root):
    return os.path.join(root, FRAMEWORK_DIR)


def config_path(root):
    return os.path.join(root, CONFIG_FILE)


def framework_version(root):
    with open(os.path.join(framework_dir(root), "VERSION"), encoding="utf-8") as handle:
        return handle.read().strip()


def default_root():
    """The project root is the parent of the .bigbang/ folder that holds this package."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def to_posix(path):
    return path.replace(os.sep, "/")


def read_text(path):
    """Read a text file normalizing CRLF, so Windows checkouts compare equal to Linux ones."""
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read().replace("\r\n", "\n")


def write_text(path, content):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
