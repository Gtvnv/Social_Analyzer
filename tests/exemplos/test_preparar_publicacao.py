"""Testes de exemplo para scripts/preparar_publicacao.py.

Usam repositórios Git temporários (tmp_path). Identidade de commit passada por
`git -c`, sem tocar em configuração global. O termo proibido é fictício.

Validates: Requirements 6.6, 10.1, 10.5, 10.6
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.preparar_publicacao import (
    CODIGO_IMPEDIMENTOS,
    CODIGO_OK,
    CODIGO_SEM_TERMOS,
    main,
    preparar,
)

TERMO = "zorgblat"
URL_VALIDA = "https://github.com/Gtvnv/exemplo.git"
IDENTIDADE = ["-c", "user.name=Teste", "-c", "user.email=teste@example.com",
              "-c", "commit.gpgsign=false"]


def git(raiz: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=raiz, capture_output=True, check=True)
    return r.stdout.decode("utf-8", errors="ignore")


def commitar(raiz: Path, mensagem: str = "commit inicial") -> None:
    git(raiz, *IDENTIDADE, "commit", "-m", mensagem)


@pytest.fixture(autouse=True)
def _sem_termos_no_ambiente(monkeypatch):
    monkeypatch.delenv("TERMOS_PROIBIDOS", raising=False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositório limpo, com um commit e remoto origin válido."""
    git(tmp_path, "init", "-q")
    (tmp_path / "leiame.txt").write_text("conteúdo neutro\n", encoding="utf-8")
    git(tmp_path, "add", "leiame.txt")
    commitar(tmp_path)
    git(tmp_path, "remote", "add", "origin", URL_VALIDA)
    return tmp_path


def estado(raiz: Path) -> tuple[str, str, str]:
    return (
        git(raiz, "rev-parse", "HEAD"),
        git(raiz, "ls-files", "-s"),
        git(raiz, "status", "--porcelain"),
    )


def test_repositorio_limpo_retorna_zero(repo):
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_OK
    assert motivos == []


def test_arquivo_sensivel_em_staging_bloqueia(repo):
    (repo / "chave.pem").write_text("segredo\n", encoding="utf-8")
    git(repo, "add", "chave.pem")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any("chave.pem" in m and "staging" in m for m in motivos)


def test_env_versionado_bloqueia(repo):
    (repo / ".env").write_text("NEO4J_PASSWORD=x\n", encoding="utf-8")
    git(repo, "add", ".env")
    commitar(repo, "adiciona env")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any(".env" in m for m in motivos)


def test_remoto_invalido_bloqueia(repo):
    git(repo, "remote", "set-url", "origin", "https://example.com/outro/repo.git")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any("origin" in m for m in motivos)


def test_remoto_ausente_bloqueia(repo):
    git(repo, "remote", "remove", "origin")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any("origin" in m for m in motivos)


def test_remoto_ssh_valido_retorna_zero(repo):
    git(repo, "remote", "set-url", "origin", "git@github.com:Gtvnv/exemplo.git")
    codigo, _ = preparar(repo, [TERMO])
    assert codigo == CODIGO_OK


def test_termo_no_conteudo_bloqueia(repo):
    (repo / "notas.txt").write_text(f"texto com {TERMO.upper()} aqui\n", encoding="utf-8")
    git(repo, "add", "notas.txt")
    commitar(repo, "notas")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any("conteudo" in m and "notas.txt" in m for m in motivos)


def test_termo_no_nome_do_arquivo_bloqueia(repo):
    (repo / f"{TERMO}_notas.txt").write_text("neutro\n", encoding="utf-8")
    git(repo, "add", ".")
    commitar(repo, "arquivo")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any("nome" in m for m in motivos)


def test_termo_na_mensagem_de_commit_bloqueia(repo):
    (repo / "outro.txt").write_text("neutro\n", encoding="utf-8")
    git(repo, "add", "outro.txt")
    commitar(repo, f"ajuste do {TERMO}")
    codigo, motivos = preparar(repo, [TERMO])
    assert codigo == CODIGO_IMPEDIMENTOS
    assert any("commit" in m for m in motivos)


def test_sem_termos_configurados_retorna_dois(repo):
    codigo, motivos = preparar(repo, [])
    assert codigo == CODIGO_SEM_TERMOS
    assert motivos


def test_main_sem_termos_retorna_dois(repo):
    assert main(["--raiz", str(repo)]) == CODIGO_SEM_TERMOS


def test_main_com_termos_do_ambiente(repo, monkeypatch):
    monkeypatch.setenv("TERMOS_PROIBIDOS", TERMO)
    assert main(["--raiz", str(repo)]) == CODIGO_OK


def test_main_com_termo_no_conteudo_retorna_um(repo, monkeypatch):
    (repo / "notas.txt").write_text(f"{TERMO}\n", encoding="utf-8")
    git(repo, "add", "notas.txt")
    commitar(repo, "notas")
    monkeypatch.setenv("TERMOS_PROIBIDOS", TERMO)
    assert main(["--raiz", str(repo)]) == CODIGO_IMPEDIMENTOS


@pytest.mark.parametrize("cenario", ["limpo", "sensivel", "sem_termos", "sem_origin"])
def test_script_nao_altera_head_nem_staging(repo, cenario):
    termos = [TERMO]
    if cenario == "sensivel":
        (repo / "chave.pem").write_text("segredo\n", encoding="utf-8")
        git(repo, "add", "chave.pem")
    elif cenario == "sem_termos":
        termos = []
    elif cenario == "sem_origin":
        git(repo, "remote", "remove", "origin")
    (repo / "nao_rastreado.txt").write_text("x\n", encoding="utf-8")

    antes = estado(repo)
    preparar(repo, termos)
    assert estado(repo) == antes
    assert (repo / "nao_rastreado.txt").exists()
