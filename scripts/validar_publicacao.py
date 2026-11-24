"""Validadores de publicação: URL do remoto, nome de branch e arquivos sensíveis."""

from __future__ import annotations

import re

_NOME_REPO = r"[A-Za-z0-9._-]{1,100}"
_PADRAO_URL = re.compile(
    rf"https://github\.com/Gtvnv/{_NOME_REPO}\.git"
    rf"|git@github\.com:Gtvnv/{_NOME_REPO}\.git",
    re.ASCII,
)

PREFIXOS_BRANCH = ("feature", "fix", "hotfix", "chore", "refactor", "docs", "test")
_PADRAO_BRANCH = re.compile(
    rf"(?:{'|'.join(PREFIXOS_BRANCH)})/[a-z0-9]+(?:-[a-z0-9]+)*",
    re.ASCII,
)

_TERMOS_CREDENCIAL = ("credentials", "credenciais", "service-account", "secret")


def url_remoto_valida(url: str) -> bool:
    """Aceita somente https://github.com/Gtvnv/<nome>.git ou git@github.com:Gtvnv/<nome>.git."""
    if not isinstance(url, str):
        return False
    return _PADRAO_URL.fullmatch(url) is not None


def branch_valida(nome: str) -> bool:
    """Prefixo permitido seguido de nome não vazio em kebab-case."""
    if not isinstance(nome, str):
        return False
    return _PADRAO_BRANCH.fullmatch(nome) is not None


def arquivo_sensivel(caminho: str) -> bool:
    """Indica se o nome base do caminho é um arquivo que não deve ser publicado."""
    if not isinstance(caminho, str):
        return False
    base = re.split(r"[\\/]", caminho)[-1].lower()
    if not base or base == ".env.example":
        return False
    if base == ".env" or base.endswith((".pem", ".key")):
        return True
    return base.endswith(".json") and any(t in base for t in _TERMOS_CREDENCIAL)
