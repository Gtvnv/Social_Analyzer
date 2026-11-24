"""Testes de fumaça do ambiente (Requisitos 6.5, 6.6, 6.7, 6.8)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "docker-compose.yml"
ENV_EXAMPLE = RAIZ / ".env.example"
GITIGNORE = RAIZ / ".gitignore"

VARIAVEIS_ESPERADAS = {
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_HTTP_PORT",
    "NEO4J_BOLT_PORT",
}


def _rodar(args, **kw):
    return subprocess.run(
        args, cwd=RAIZ, capture_output=True, text=True, timeout=60, **kw
    )


def _git_disponivel():
    if shutil.which("git") is None:
        return False
    try:
        r = _rodar(["git", "rev-parse", "--is-inside-work-tree"])
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def _variaveis_env_example():
    nomes = {}
    for linha in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", linha)
        if m:
            nomes[m.group(1)] = m.group(2)
    return nomes


def _linhas_gitignore():
    return [
        l.strip()
        for l in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


# ---------- .env.example ----------

def test_env_example_existe_com_conteudo_correto():
    assert ENV_EXAMPLE.is_file(), ".env.example não existe"
    variaveis = _variaveis_env_example()
    assert VARIAVEIS_ESPERADAS <= set(variaveis)
    assert variaveis["NEO4J_HTTP_PORT"].isdigit()
    assert variaveis["NEO4J_BOLT_PORT"].isdigit()
    assert variaveis["NEO4J_PASSWORD"] != ""


def test_env_example_define_variaveis_usadas_no_compose():
    texto = COMPOSE.read_text(encoding="utf-8")
    usadas = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", texto))
    assert usadas, "nenhuma variável ${...} encontrada no docker-compose.yml"
    ausentes = usadas - set(_variaveis_env_example())
    assert not ausentes, f".env.example não define: {sorted(ausentes)}"


# ---------- .env / .gitignore ----------

def test_env_nao_esta_versionado():
    if not _git_disponivel():
        pytest.skip("sem repositório Git")
    r = _rodar(["git", "ls-files"])
    assert r.returncode == 0
    arquivos = r.stdout.splitlines()
    assert ".env" not in arquivos


def test_gitignore_exclui_env():
    linhas = _linhas_gitignore()
    assert ".env" in linhas or "/.env" in linhas
    if _git_disponivel():
        r = _rodar(["git", "check-ignore", "-q", ".env"])
        assert r.returncode == 0, ".env não é ignorado pelo Git"


def test_gitignore_mantem_env_example_rastreado():
    linhas = _linhas_gitignore()
    assert ".env.example" not in linhas and "/.env.example" not in linhas
    assert "!.env.example" in linhas or not any(
        l in (".env*", "*.example", ".env.*") for l in linhas
    )
    if _git_disponivel():
        r = _rodar(["git", "check-ignore", "-q", ".env.example"])
        assert r.returncode == 1, ".env.example está sendo ignorado"


# ---------- docker compose ----------

def _docker_compose_disponivel():
    if shutil.which("docker") is None:
        return False
    try:
        r = _rodar(["docker", "compose", "version"])
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def test_docker_compose_config_valido():
    if not _docker_compose_disponivel():
        pytest.skip("Docker Compose indisponível")
    r = _rodar(
        ["docker", "compose", "--env-file", ".env.example", "config"]
    )
    assert r.returncode == 0, r.stderr
    assert "neo4j" in r.stdout
