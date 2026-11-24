"""Varredura de termos proibidos em arquivos, nomes, commits e metadados PNG.

Os termos nunca ficam no repositório: são lidos da variável de ambiente
TERMOS_PROIBIDOS (separados por vírgula) ou do arquivo `.termos_proibidos.local`
(um termo por linha, ignorado pelo Git).
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import subprocess
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

VARIAVEL_AMBIENTE = "TERMOS_PROIBIDOS"
ARQUIVO_LOCAL = ".termos_proibidos.local"
ASSINATURA_PNG = b"\x89PNG\r\n\x1a\n"
_SEPARADORES = re.compile(r"[\s_\-]+")


@dataclass(frozen=True)
class Ocorrencia:
    """Uma ocorrência de termo proibido.

    tipo: "conteudo", "nome", "commit" ou "png".
    referencia: caminho do arquivo ou id do commit.
    local: linha, chunk PNG ou "nome"/"mensagem".
    """

    tipo: str
    referencia: str
    local: str
    termo: str


def _padrao(termo: str) -> re.Pattern[str] | None:
    """Regex tolerante a caixa e separador (nenhum, hífen, underscore, espaço).

    A forma de domínio (termo + extensão) é coberta pela busca por substring.
    """
    partes = [p for p in _SEPARADORES.split(termo.strip()) if p]
    if not partes:
        return None
    return re.compile(r"[\s_\-]*".join(re.escape(p) for p in partes), re.IGNORECASE)


def ocorrencias(texto: str, termos: list[str]) -> list[Ocorrencia]:
    """Retorna as ocorrências dos termos no texto (uma por linha e termo).

    O campo `local` traz o número da linha; `tipo` e `referencia` ficam vazios
    para o chamador preencher via `dataclasses.replace`.
    """
    padroes = [(t, _padrao(t)) for t in termos]
    achadas: list[Ocorrencia] = []
    for numero, linha in enumerate(texto.splitlines() or [texto], start=1):
        for termo, padrao in padroes:
            if padrao is not None and padrao.search(linha):
                achadas.append(Ocorrencia("", "", str(numero), termo))
    # Termos com separador (espaço) podem atravessar quebras de linha.
    if not achadas:
        for termo, padrao in padroes:
            if padrao is not None and padrao.search(texto):
                achadas.append(Ocorrencia("", "", "1", termo))
    return achadas


def _com_origem(achadas: list[Ocorrencia], tipo: str, referencia: str,
                local: str | None = None) -> list[Ocorrencia]:
    return [
        Ocorrencia(tipo, referencia, local if local is not None else o.local, o.termo)
        for o in achadas
    ]


def formatar_relatorio(achadas: list[Ocorrencia]) -> tuple[str, int]:
    """Função pura: devolve (texto do relatório, código de saída)."""
    if not achadas:
        return "Nenhuma ocorrência de termo proibido.", 0
    linhas = [f"{len(achadas)} ocorrência(s) de termo proibido:"]
    for o in achadas:
        linhas.append(f"  [{o.tipo}] {o.referencia} ({o.local})")
    return "\n".join(linhas), 1


def carregar_termos(env: dict[str, str] | None = None, raiz: Path | None = None) -> list[str]:
    env = os.environ if env is None else env
    bruto = env.get(VARIAVEL_AMBIENTE, "")
    termos = [t.strip() for t in bruto.split(",") if t.strip()]
    if termos:
        return termos
    arquivo = (raiz or Path.cwd()) / ARQUIVO_LOCAL
    if arquivo.is_file():
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        return [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]
    return []


def textos_png(dados: bytes) -> list[tuple[str, str]]:
    """Extrai (chunk, texto) de tEXt, zTXt, iTXt e eXIf, sem dependências."""
    if not dados.startswith(ASSINATURA_PNG):
        return []
    resultado: list[tuple[str, str]] = []
    pos = len(ASSINATURA_PNG)
    while pos + 8 <= len(dados):
        tamanho, tipo_b = struct.unpack(">I4s", dados[pos:pos + 8])
        corpo = dados[pos + 8:pos + 8 + tamanho]
        pos += 12 + tamanho
        tipo = tipo_b.decode("latin-1")
        try:
            if tipo == "tEXt":
                chave, _, valor = corpo.partition(b"\0")
                resultado.append((tipo, chave.decode("latin-1") + "\n" + valor.decode("latin-1")))
            elif tipo == "zTXt":
                chave, _, resto = corpo.partition(b"\0")
                valor = zlib.decompress(resto[1:])
                resultado.append((tipo, chave.decode("latin-1") + "\n" + valor.decode("latin-1", "ignore")))
            elif tipo == "iTXt":
                chave, _, resto = corpo.partition(b"\0")
                comprimido, resto = resto[0], resto[2:]
                _, _, resto = resto.partition(b"\0")  # idioma
                _, _, valor = resto.partition(b"\0")  # chave traduzida
                if comprimido:
                    valor = zlib.decompress(valor)
                resultado.append((tipo, chave.decode("utf-8", "ignore") + "\n" + valor.decode("utf-8", "ignore")))
            elif tipo == "eXIf":
                resultado.append((tipo, corpo.decode("latin-1")))
        except (zlib.error, IndexError):
            continue
        if tipo == "IEND":
            break
    return resultado


def varrer_png(caminho: str, dados: bytes, termos: list[str]) -> list[Ocorrencia]:
    achadas: list[Ocorrencia] = []
    for chunk, texto in textos_png(dados):
        achadas += _com_origem(ocorrencias(texto, termos), "png", caminho, chunk)
    return achadas


def varrer_arquivos(raiz: Path, caminhos: list[str], termos: list[str]) -> list[Ocorrencia]:
    achadas: list[Ocorrencia] = []
    for caminho in caminhos:
        # Nome do arquivo e de todos os diretórios do caminho.
        achadas += _com_origem(ocorrencias(caminho.replace("/", "\n"), termos), "nome", caminho, "nome")
        arquivo = raiz / caminho
        if not arquivo.is_file():
            continue
        dados = arquivo.read_bytes()
        if dados.startswith(ASSINATURA_PNG):
            achadas += varrer_png(caminho, dados, termos)
        elif b"\0" not in dados:
            texto = dados.decode("utf-8", errors="ignore")
            achadas += _com_origem(ocorrencias(texto, termos), "conteudo", caminho)
    return achadas


def varrer_commits(raiz: Path, termos: list[str]) -> list[Ocorrencia]:
    saida = _git(raiz, "log", "--all", "--format=%H%x1e%an%x1f%ae%x1f%B%x1d")
    achadas: list[Ocorrencia] = []
    for registro in saida.split("\x1d"):
        if "\x1e" not in registro:
            continue
        commit, _, resto = registro.strip().partition("\x1e")
        achadas += _com_origem(ocorrencias(resto.replace("\x1f", "\n"), termos), "commit", commit, "mensagem")
    return achadas


def _git(raiz: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=raiz, capture_output=True, check=False)
    if r.returncode != 0:
        return ""
    return r.stdout.decode("utf-8", errors="ignore")


def arquivos_versionados(raiz: Path) -> list[str]:
    saida = _git(raiz, "ls-files", "-z")
    return [c for c in saida.split("\0") if c]


def varrer_repositorio(raiz: Path, termos: list[str]) -> list[Ocorrencia]:
    return varrer_arquivos(raiz, arquivos_versionados(raiz), termos) + varrer_commits(raiz, termos)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Varre o repositório em busca de termos proibidos.")
    ap.add_argument("--raiz", default=".", help="raiz do repositório Git")
    args = ap.parse_args(argv)
    raiz = Path(args.raiz).resolve()
    termos = carregar_termos(raiz=raiz)
    if not termos:
        print(f"Nenhum termo configurado: defina {VARIAVEL_AMBIENTE} ou crie {ARQUIVO_LOCAL}.",
              file=sys.stderr)
        return 2
    relatorio, codigo = formatar_relatorio(varrer_repositorio(raiz, termos))
    print(relatorio)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
