"""Verificador de links relativos em documentos Markdown.

`links_quebrados` é uma função pura: recebe o texto Markdown e o conjunto de
caminhos existentes e devolve os destinos relativos que não existem.
A CLI aplica a função ao README.md usando os arquivos do disco.
"""
from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path
from typing import Iterable

# Links e imagens em linha: [texto](destino) ou ![alt](destino "título").
_LINK = re.compile(
    r'!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+(?:"[^"]*"|\'[^\']*\'))?\s*\)'
)
_CERCA = re.compile(r"^\s*(```|~~~)")
_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


def _normalizar(caminho: str) -> str:
    """Normaliza um caminho relativo para comparação (separador `/`, sem `./`)."""
    caminho = caminho.replace("\\", "/")
    normal = posixpath.normpath(caminho)
    return "" if normal == "." else normal


def _destinos(markdown: str) -> Iterable[str]:
    """Gera o destino de cada link fora de blocos de código cercados."""
    em_cerca = False
    for linha in markdown.splitlines():
        if _CERCA.match(linha):
            em_cerca = not em_cerca
            continue
        if em_cerca:
            continue
        for achado in _LINK.finditer(linha):
            destino = achado.group(1)
            if destino.startswith("<") and destino.endswith(">"):
                destino = destino[1:-1]
            yield destino.strip()


def links_quebrados(markdown: str, arquivos_existentes: Iterable[str]) -> list[str]:
    """Retorna os links relativos cujo destino não está em `arquivos_existentes`.

    Ignora URLs com esquema (http, https, mailto etc.), URLs iniciadas por `//`
    e âncoras puras (`#secao`). A âncora `#...` é removida do destino antes da
    verificação. O retorno traz o destino sem âncora, na ordem em que aparece
    no documento, com um item por link quebrado.
    """
    existentes = {_normalizar(a) for a in arquivos_existentes}
    quebrados: list[str] = []
    for destino in _destinos(markdown):
        if not destino or destino.startswith("#") or destino.startswith("//"):
            continue
        if _ESQUEMA.match(destino):
            continue
        sem_ancora = destino.split("#", 1)[0]
        if not sem_ancora:
            continue
        if _normalizar(sem_ancora) not in existentes:
            quebrados.append(sem_ancora)
    return quebrados


def _listar_existentes(raiz: Path) -> set[str]:
    """Lista arquivos e diretórios sob `raiz` como caminhos relativos com `/`."""
    existentes: set[str] = set()
    for caminho in raiz.rglob("*"):
        relativo = caminho.relative_to(raiz)
        if ".git" in relativo.parts:
            continue
        existentes.add(relativo.as_posix())
    return existentes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica links relativos de um Markdown.")
    parser.add_argument("arquivo", nargs="?", default="README.md", help="Markdown a verificar (padrão: README.md)")
    args = parser.parse_args(argv)

    caminho = Path(args.arquivo)
    if not caminho.is_file():
        print(f"Arquivo não encontrado: {caminho}", file=sys.stderr)
        return 2

    texto = caminho.read_text(encoding="utf-8")
    quebrados = links_quebrados(texto, _listar_existentes(caminho.resolve().parent))
    for destino in quebrados:
        print(f"Link quebrado: {destino}")
    print(f"{len(quebrados)} link(s) relativo(s) quebrado(s) em {caminho}.")
    return 1 if quebrados else 0


if __name__ == "__main__":
    sys.exit(main())
