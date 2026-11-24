"""Verificação pré-publicação (somente leitura sobre o Git).

Checagens:
  1. URL do remoto `origin` válida (validar_publicacao.url_remoto_valida);
  2. `.env` ausente de `git ls-files`;
  3. nenhum arquivo sensível em staging (validar_publicacao.arquivo_sensivel);
  4. varredura de termos proibidos em arquivos, nomes, `git log` e metadados PNG.

O script só executa comandos de leitura do Git (`remote get-url`, `ls-files`,
`diff --cached`, `log`). Não faz add, commit, push, reset, clean nem remove branches.

Código de saída: 0 = pronto; 1 = há impedimentos (listados);
2 = nenhum termo proibido configurado (a varredura não pode ser feita).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:  # execução como pacote (testes) ou como script
    from scripts.validar_publicacao import arquivo_sensivel, url_remoto_valida
    from scripts.varrer_termos import (
        ARQUIVO_LOCAL,
        VARIAVEL_AMBIENTE,
        Ocorrencia,
        carregar_termos,
        varrer_repositorio,
    )
except ImportError:  # pragma: no cover
    from validar_publicacao import arquivo_sensivel, url_remoto_valida  # type: ignore
    from varrer_termos import (  # type: ignore
        ARQUIVO_LOCAL,
        VARIAVEL_AMBIENTE,
        Ocorrencia,
        carregar_termos,
        varrer_repositorio,
    )

CODIGO_OK = 0
CODIGO_IMPEDIMENTOS = 1
CODIGO_SEM_TERMOS = 2


def _git_leitura(raiz: Path, *args: str) -> tuple[int, str]:
    """Executa um comando Git de leitura e devolve (código, stdout)."""
    try:
        r = subprocess.run(["git", *args], cwd=raiz, capture_output=True, check=False)
    except OSError as erro:
        return 127, str(erro)
    return r.returncode, r.stdout.decode("utf-8", errors="ignore")


def _lista_z(saida: str) -> list[str]:
    return [c for c in saida.split("\0") if c]


def verificar_origin(raiz: Path) -> list[str]:
    codigo, saida = _git_leitura(raiz, "remote", "get-url", "origin")
    url = saida.strip()
    if codigo != 0 or not url:
        return ["remoto 'origin' não configurado"]
    if not url_remoto_valida(url):
        return [f"URL do remoto 'origin' inválida: {url}"]
    return []


def verificar_env_versionado(raiz: Path) -> list[str]:
    codigo, saida = _git_leitura(raiz, "ls-files", "-z")
    if codigo != 0:
        return ["não foi possível executar 'git ls-files' (não é um repositório Git?)"]
    return [
        f"arquivo .env versionado: {c}"
        for c in _lista_z(saida)
        if c.replace("\\", "/").split("/")[-1] == ".env"
    ]


def verificar_staging(raiz: Path) -> list[str]:
    codigo, saida = _git_leitura(raiz, "diff", "--cached", "--name-only", "-z")
    if codigo != 0:
        return ["não foi possível ler a área de staging ('git diff --cached')"]
    return [f"arquivo sensível em staging: {c}" for c in _lista_z(saida) if arquivo_sensivel(c)]


def verificar_termos(raiz: Path, termos: list[str]) -> list[str]:
    achadas: list[Ocorrencia] = varrer_repositorio(raiz, termos)
    return [
        f"termo proibido [{o.tipo}] {o.referencia} ({o.local})" for o in achadas
    ]


def preparar(raiz: Path, termos: list[str] | None = None) -> tuple[int, list[str]]:
    """Executa todas as checagens sobre o repositório em `raiz`.

    Se `termos` for None, carrega de TERMOS_PROIBIDOS ou do arquivo local.
    Retorna (código de saída, lista de motivos).
    """
    raiz = Path(raiz)
    if termos is None:
        termos = carregar_termos(raiz=raiz)
    if not termos:
        return CODIGO_SEM_TERMOS, [
            f"nenhum termo configurado: defina {VARIAVEL_AMBIENTE} ou crie {ARQUIVO_LOCAL}"
        ]
    motivos = (
        verificar_origin(raiz)
        + verificar_env_versionado(raiz)
        + verificar_staging(raiz)
        + verificar_termos(raiz, termos)
    )
    return (CODIGO_IMPEDIMENTOS if motivos else CODIGO_OK), motivos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verifica se o repositório está pronto para publicar.")
    ap.add_argument("--raiz", default=".", help="raiz do repositório Git")
    args = ap.parse_args(argv)
    codigo, motivos = preparar(Path(args.raiz).resolve())
    if codigo == CODIGO_OK:
        print("Repositório pronto para publicação.")
    else:
        print("Publicação bloqueada:", file=sys.stderr)
        for m in motivos:
            print(f"  - {m}", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
