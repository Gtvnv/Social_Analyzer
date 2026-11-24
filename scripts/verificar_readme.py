"""Verificador do README do projeto Social Analyzer.

As funcoes de verificacao sao puras: recebem texto e devolvem uma lista de
problemas (``list[str]``). Lista vazia significa README conforme. A CLI le os
arquivos, imprime um problema por linha e sai com codigo 1 se houver problemas
(codigo 2 se um arquivo nao puder ser lido).

Uso::

    python scripts/verificar_readme.py [--readme README.md]
                                       [--consultas cypher/03_consultas.cypher]

FORMATO ESPERADO DO README
==========================

Cabecalhos em portugues. Blocos de codigo cercados (``` ou ~~~) sao ignorados
na deteccao de cabecalhos, listas e campos.

1. Abertura (5 primeiras linhas nao vazias)
   - A primeira linha nao vazia e o titulo, um cabecalho de nivel 1 (``# ...``).
   - Uma linha com o link ``https://github.com/Gtvnv/<repo>``.
   - Uma linha de resumo, que nao e cabecalho e nao contem o link: uma unica
     frase com no maximo 200 caracteres.

2. Secoes de nivel 2 obrigatorias (``## Titulo``, comparacao sem diferenciar
   maiusculas de minusculas)::

       ## Sumario            (com acento: "Sumário")
       ## Contexto
       ## Perguntas de negócio
       ## Consultas de negócio
       ## Estrutura do repositório
       ## Tecnologias
       ## Próximos passos
       ## Troubleshooting

   Outras secoes de nivel 2 (modelo, dataset, passo a passo etc.) sao
   permitidas, mas cada uma precisa de um link no sumario.

3. ``## Sumário``: lista com exatamente um link ``[texto](#ancora)`` para cada
   outra secao de nivel 2. A ancora e o titulo em minusculas, sem pontuacao e
   com espacos trocados por hifen (regra do GitHub), por exemplo
   ``[Próximos passos](#próximos-passos)``. Links para ancoras inexistentes
   sao problema. Linkar o proprio Sumario e opcional.

4. ``## Perguntas de negócio``: lista plana (``-``, ``*`` ou ``1.``) com 5 a 10
   itens, todos terminados em ``?``.

5. ``## Estrutura do repositório``: um bloco de codigo com a arvore, um item por
   linha, 4 caracteres de recuo por nivel e a descricao depois de ``#``::

       social-analyzer-neo4j/
       ├── data/             # CSVs do dataset sintetico
       ├── cypher/           # carga, verificacao e consultas
       ├── docs/
       │   └── images/       # diagrama do modelo e evidencias visuais
       └── scripts/          # gerador do dataset e verificadores

   Sao obrigatorios ``data/``, ``cypher/``, ``docs/images/`` e ``scripts/``,
   cada um com descricao de 1 a 120 caracteres. ``docs/images/`` pode aparecer
   aninhado em ``docs/`` ou com o caminho completo.

6. ``## Tecnologias``: lista (ou tabela Markdown) em que cada item traz uma
   versao, como ``Neo4j 5.x`` ou ``Python 3.12``. O numero deve vir separado
   do nome (``Neo4j`` sozinho nao conta como versao).

7. ``## Próximos passos``: lista com 2 a 10 itens.

8. ``## Troubleshooting``: no minimo 5 entradas, cada uma um cabecalho de nivel
   3 (``### Titulo``) contendo::

       - **Sintoma:** o que o usuario observa
       - **Causa:** por que acontece
       - **Solução:** o que fazer

       ```text
       mensagem de erro exata
       ```

   Os tres campos precisam de texto (na mesma linha ou nas linhas seguintes)
   e cada entrada precisa de ao menos um bloco de codigo nao vazio com a
   mensagem de erro.

9. ``## Consultas de negócio``: para cada consulta de
   ``cypher/03_consultas.cypher`` (um comentario ``// Pergunta?`` seguido do
   codigo terminado em ``;``), uma subsecao de nivel 3 com:
   - cabecalho ``### <pergunta>`` igual ao comentario do arquivo (um prefixo
     numerico como ``1. `` e aceito);
   - um bloco de codigo com a consulta, identica a do arquivo (espacos
     normalizados, ``;`` final opcional);
   - explicacao de 1 a 5 frases fora de blocos de codigo;
   - uma imagem ``![descricao](docs/images/<arquivo>.png)`` com texto
     alternativo (png, jpg, jpeg, gif ou webp).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

CAMINHO_README_PADRAO = "README.md"
CAMINHO_CONSULTAS_PADRAO = "cypher/03_consultas.cypher"

SECOES_OBRIGATORIAS = (
    "Sumário",
    "Contexto",
    "Perguntas de negócio",
    "Consultas de negócio",
    "Estrutura do repositório",
    "Tecnologias",
    "Próximos passos",
    "Troubleshooting",
)
DIRETORIOS_OBRIGATORIOS = ("data/", "cypher/", "docs/images/", "scripts/")
CAMPOS_TROUBLESHOOTING = ("Sintoma", "Causa", "Solução")

MIN_PERGUNTAS, MAX_PERGUNTAS = 5, 10
MIN_PASSOS, MAX_PASSOS = 2, 10
MIN_ENTRADAS_TROUBLESHOOTING = 5
MAX_DESCRICAO_DIRETORIO = 120
MAX_RESUMO = 200
MIN_FRASES, MAX_FRASES = 1, 5

_URL_REPO = re.compile(r"https://github\.com/Gtvnv/[A-Za-z0-9._-]{1,100}")
_CERCA = re.compile(r"^\s*(```|~~~)")
_TITULO = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM_LISTA = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_LINK_ANCORA = re.compile(r"\[[^\]]*\]\(#([^)\s]+)\)")
_IMAGEM = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_VERSAO = re.compile(r"(?<![\w.])v?\d+(?:\.(?:\d+|x))*(?!\w)")
_PREFIXO_ARVORE = re.compile(r"^(?P<prefixo>[\s│├└─|`+\\-]*)(?P<nome>\S.*)$")
_FIM_FRASE = re.compile(r"(?<=[.!?])\s+")
_EXT_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".webp")


class Linha(NamedTuple):
    texto: str
    codigo: bool  # dentro de bloco cercado ou delimitador dele
    delimitador: bool  # a propria linha ``` / ~~~


class Bloco(NamedTuple):
    titulo: str
    linhas: list[Linha]


class Consulta(NamedTuple):
    pergunta: str
    codigo: str


# ---------------------------------------------------------------- utilitarios


def _marcar_linhas(texto: str) -> list[Linha]:
    resultado: list[Linha] = []
    marcador: str | None = None
    for bruta in texto.splitlines():
        m = _CERCA.match(bruta)
        if marcador is None:
            if m:
                marcador = m.group(1)
                resultado.append(Linha(bruta, True, True))
            else:
                resultado.append(Linha(bruta, False, False))
        else:
            if m and m.group(1) == marcador:
                marcador = None
                resultado.append(Linha(bruta, True, True))
            else:
                resultado.append(Linha(bruta, True, False))
    return resultado


def _titulo(linha: Linha) -> tuple[int, str] | None:
    if linha.codigo:
        return None
    m = _TITULO.match(linha.texto)
    return (len(m.group(1)), m.group(2)) if m else None


def _blocos(linhas: list[Linha], nivel: int) -> list[Bloco]:
    """Divide em blocos que comecam em cabecalhos do nivel dado.

    O bloco termina no proximo cabecalho de nivel menor ou igual.
    """
    blocos: list[Bloco] = []
    atual: Bloco | None = None
    for linha in linhas:
        t = _titulo(linha)
        if t is not None and t[0] <= nivel:
            atual = None
            if t[0] == nivel:
                atual = Bloco(t[1], [])
                blocos.append(atual)
            continue
        if atual is not None:
            atual.linhas.append(linha)
    return blocos


def _normalizar_titulo(titulo: str) -> str:
    return " ".join(titulo.split()).casefold()


def _ancora(titulo: str) -> str:
    s = titulo.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def _texto_sem_codigo(linhas: list[Linha]) -> list[str]:
    return [l.texto for l in linhas if not l.codigo]


def _itens(linhas: list[str]) -> list[str]:
    """Itens de lista; linhas recuadas seguintes sao continuacao do item."""
    itens: list[str] = []
    for texto in linhas:
        m = _ITEM_LISTA.match(texto)
        if m:
            itens.append(m.group(1).strip())
        elif itens and texto.strip() and texto[:1].isspace():
            itens[-1] += " " + texto.strip()
    return itens


def _blocos_codigo(linhas: list[Linha]) -> list[str]:
    blocos: list[list[str]] = []
    dentro = False
    for l in linhas:
        if l.delimitador:
            if not dentro:
                blocos.append([])
            dentro = not dentro
        elif l.codigo and blocos:
            blocos[-1].append(l.texto)
    return ["\n".join(b) for b in blocos]


def _sem_markup_inline(texto: str) -> str:
    texto = re.sub(r"`[^`]*`", "", texto)
    texto = _IMAGEM.sub("", texto)
    return texto


def _contar_frases(texto: str) -> int:
    texto = " ".join(_sem_markup_inline(texto).split())
    return len([p for p in _FIM_FRASE.split(texto) if p.strip()])


def _normalizar_codigo(codigo: str) -> str:
    return " ".join(codigo.split()).rstrip(";").rstrip()


def _secoes(linhas: list[Linha]) -> dict[str, Bloco]:
    return {_normalizar_titulo(b.titulo): b for b in _blocos(linhas, 2)}


# ---------------------------------------------------------------- consultas


def extrair_consultas(cypher: str) -> list[Consulta]:
    """Le ``// Pergunta?`` + codigo terminado em ``;`` do arquivo de consultas."""
    consultas: list[Consulta] = []
    comentarios: list[str] = []
    codigo: list[str] = []
    for linha in cypher.splitlines():
        s = linha.strip()
        if not codigo and s.startswith("//"):
            comentarios.append(s[2:].strip())
        elif not s and not codigo:
            continue
        elif s.startswith("//"):
            continue
        else:
            codigo.append(linha.rstrip())
            if s.endswith(";"):
                consultas.append(
                    Consulta(" ".join(comentarios).strip(), "\n".join(codigo))
                )
                comentarios, codigo = [], []
    return consultas


# ---------------------------------------------------------------- verificacoes


def verificar_abertura(readme: str) -> list[str]:
    """Titulo, resumo de uma frase e link do GitHub nas 5 primeiras linhas."""
    problemas: list[str] = []
    nao_vazias = [l.strip() for l in readme.splitlines() if l.strip()][:5]
    if not nao_vazias or not re.match(r"^#\s+\S", nao_vazias[0]):
        problemas.append("Abertura: a primeira linha não vazia deve ser o título (# ...).")
    if not any(_URL_REPO.search(l) for l in nao_vazias):
        problemas.append(
            "Abertura: link https://github.com/Gtvnv/<repo> ausente nas 5 primeiras linhas não vazias."
        )
    candidatas = [
        re.sub(r"^>\s*", "", l)
        for l in nao_vazias
        if not l.startswith("#") and not _URL_REPO.search(l)
    ]
    if not candidatas:
        problemas.append("Abertura: resumo de uma frase ausente nas 5 primeiras linhas não vazias.")
    else:
        resumo = candidatas[0]
        if len(resumo) > MAX_RESUMO:
            problemas.append(
                f"Abertura: resumo com {len(resumo)} caracteres (máximo {MAX_RESUMO})."
            )
        if _contar_frases(resumo) != 1:
            problemas.append("Abertura: o resumo deve ter exatamente uma frase.")
    return problemas


def verificar_secoes_obrigatorias(readme: str) -> list[str]:
    secoes = _secoes(_marcar_linhas(readme))
    return [
        f"Seção obrigatória ausente: ## {nome}"
        for nome in SECOES_OBRIGATORIAS
        if _normalizar_titulo(nome) not in secoes
    ]


def verificar_sumario(readme: str) -> list[str]:
    """Um link por secao de nivel 2 (alem do proprio Sumario)."""
    linhas = _marcar_linhas(readme)
    secoes = _blocos(linhas, 2)
    chave_sumario = _normalizar_titulo("Sumário")
    sumario = next((b for b in secoes if _normalizar_titulo(b.titulo) == chave_sumario), None)
    if sumario is None:
        return []  # ausencia ja reportada por verificar_secoes_obrigatorias
    ancoras = [
        m.group(1).lower()
        for t in _texto_sem_codigo(sumario.linhas)
        for m in _LINK_ANCORA.finditer(t)
    ]
    problemas: list[str] = []
    validas = set()
    for b in secoes:
        a = _ancora(b.titulo)
        validas.add(a)
        n = ancoras.count(a)
        propria = _normalizar_titulo(b.titulo) == chave_sumario
        if n == 0 and not propria:
            problemas.append(f"Sumário: falta link para a seção '{b.titulo}' (#{a}).")
        elif n > 1:
            problemas.append(f"Sumário: {n} links para a seção '{b.titulo}' (esperado 1).")
    for a in dict.fromkeys(ancoras):
        if a not in validas:
            problemas.append(f"Sumário: link para âncora inexistente (#{a}).")
    return problemas


def verificar_perguntas(readme: str) -> list[str]:
    sec = _secoes(_marcar_linhas(readme)).get(_normalizar_titulo("Perguntas de negócio"))
    if sec is None:
        return []
    itens = _itens(_texto_sem_codigo(sec.linhas))
    problemas: list[str] = []
    if not MIN_PERGUNTAS <= len(itens) <= MAX_PERGUNTAS:
        problemas.append(
            f"Perguntas de negócio: {len(itens)} itens (esperado {MIN_PERGUNTAS} a {MAX_PERGUNTAS})."
        )
    for item in itens:
        if not item.rstrip("*_ ").endswith("?"):
            problemas.append(f"Perguntas de negócio: item não termina em '?': {item!r}.")
    return problemas


def verificar_estrutura(readme: str) -> list[str]:
    sec = _secoes(_marcar_linhas(readme)).get(_normalizar_titulo("Estrutura do repositório"))
    if sec is None:
        return []
    blocos = _blocos_codigo(sec.linhas)
    if not blocos:
        return ["Estrutura do repositório: bloco de código com a árvore ausente."]
    pilha: list[str] = []
    encontrados: dict[str, str] = {}
    for linha in blocos[0].splitlines():
        if not linha.strip():
            continue
        m = _PREFIXO_ARVORE.match(linha)
        if not m:
            continue
        profundidade = len(m.group("prefixo")) // 4
        corpo = m.group("nome")
        nome, _, descricao = corpo.partition("#")
        nome = nome.strip()
        pilha = pilha[:profundidade]
        pilha.append(nome)
        completo = "".join(pilha)
        for req in DIRETORIOS_OBRIGATORIOS:
            if nome == req or completo == req or completo.endswith("/" + req):
                encontrados.setdefault(req, descricao.strip())
    problemas: list[str] = []
    for req in DIRETORIOS_OBRIGATORIOS:
        if req not in encontrados:
            problemas.append(f"Estrutura do repositório: diretório {req} ausente da árvore.")
            continue
        d = encontrados[req]
        if not d:
            problemas.append(f"Estrutura do repositório: {req} sem descrição (após '#').")
        elif len(d) > MAX_DESCRICAO_DIRETORIO:
            problemas.append(
                f"Estrutura do repositório: descrição de {req} com {len(d)} caracteres "
                f"(máximo {MAX_DESCRICAO_DIRETORIO})."
            )
    return problemas


def _entradas_tecnologia(linhas: list[str]) -> list[str]:
    entradas: list[str] = []
    em_tabela = False
    for texto in linhas:
        s = texto.strip()
        if s.startswith("|"):
            if re.match(r"^\|?\s*:?-{3,}", s):
                continue
            if em_tabela:
                entradas.append(s)
            em_tabela = True  # primeira linha da tabela e o cabecalho
        else:
            em_tabela = False
    return entradas + _itens([l for l in linhas if not l.strip().startswith("|")])


def verificar_tecnologias(readme: str) -> list[str]:
    sec = _secoes(_marcar_linhas(readme)).get(_normalizar_titulo("Tecnologias"))
    if sec is None:
        return []
    entradas = _entradas_tecnologia(_texto_sem_codigo(sec.linhas))
    if not entradas:
        return ["Tecnologias: nenhuma tecnologia listada."]
    return [
        f"Tecnologias: sem versão em {e!r}." for e in entradas if not _VERSAO.search(e)
    ]


def verificar_proximos_passos(readme: str) -> list[str]:
    sec = _secoes(_marcar_linhas(readme)).get(_normalizar_titulo("Próximos passos"))
    if sec is None:
        return []
    n = len(_itens(_texto_sem_codigo(sec.linhas)))
    if not MIN_PASSOS <= n <= MAX_PASSOS:
        return [f"Próximos passos: {n} itens (esperado {MIN_PASSOS} a {MAX_PASSOS})."]
    return []


def _campo(texto: str) -> tuple[str, str] | None:
    for nome in CAMPOS_TROUBLESHOOTING:
        padrao = (
            r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?" + nome +
            r"(?:\s*:(?:\*\*|__)|(?:\*\*|__)\s*:|\s*:)\s*(.*)$"
        )
        m = re.match(padrao, texto)
        if m:
            return nome, m.group(1).strip()
    return None


def verificar_troubleshooting(readme: str) -> list[str]:
    sec = _secoes(_marcar_linhas(readme)).get(_normalizar_titulo("Troubleshooting"))
    if sec is None:
        return []
    entradas = _blocos(sec.linhas, 3)
    problemas: list[str] = []
    if len(entradas) < MIN_ENTRADAS_TROUBLESHOOTING:
        problemas.append(
            f"Troubleshooting: {len(entradas)} entradas (mínimo {MIN_ENTRADAS_TROUBLESHOOTING})."
        )
    for entrada in entradas:
        campos: dict[str, str] = {}
        atual: str | None = None
        for l in entrada.linhas:
            if l.codigo:
                continue
            c = _campo(l.texto)
            if c:
                atual = c[0]
                campos[atual] = c[1]
            elif atual and l.texto.strip():
                campos[atual] = (campos[atual] + " " + l.texto.strip()).strip()
        for nome in CAMPOS_TROUBLESHOOTING:
            if nome not in campos:
                problemas.append(f"Troubleshooting '{entrada.titulo}': campo {nome} ausente.")
            elif not campos[nome]:
                problemas.append(f"Troubleshooting '{entrada.titulo}': campo {nome} vazio.")
        if not any(b.strip() for b in _blocos_codigo(entrada.linhas)):
            problemas.append(
                f"Troubleshooting '{entrada.titulo}': mensagem de erro em bloco de código ausente."
            )
    return problemas


def verificar_consultas(readme: str, consultas: list[Consulta]) -> list[str]:
    linhas = _marcar_linhas(readme)
    subsecoes = _blocos(linhas, 3)
    por_titulo: dict[str, Bloco] = {}
    for b in subsecoes:
        chave = _normalizar_titulo(re.sub(r"^\d+[.)]\s*", "", b.titulo))
        por_titulo.setdefault(chave, b)
    problemas: list[str] = []
    if not consultas:
        problemas.append("Consultas: nenhuma consulta encontrada no arquivo .cypher.")
    for q in consultas:
        rotulo = q.pergunta or "(sem pergunta)"
        if not q.pergunta.endswith("?"):
            problemas.append(f"Consulta {rotulo!r}: comentário de pergunta ausente ou sem '?' no .cypher.")
            continue
        sub = por_titulo.get(_normalizar_titulo(q.pergunta))
        if sub is None:
            problemas.append(f"Consulta {rotulo!r}: subseção '### {q.pergunta}' ausente no README.")
            continue
        alvo = _normalizar_codigo(q.codigo)
        if not any(_normalizar_codigo(b) == alvo for b in _blocos_codigo(sub.linhas)):
            problemas.append(f"Consulta {rotulo!r}: bloco de código igual ao do .cypher ausente.")
        texto = _texto_sem_codigo(sub.linhas)
        imagens = [m for t in texto for m in _IMAGEM.finditer(t)]
        validas = [
            m for m in imagens
            if m.group(1).strip()
            and m.group(2).startswith("docs/images/")
            and m.group(2).lower().endswith(_EXT_IMAGEM)
        ]
        if not validas:
            problemas.append(
                f"Consulta {rotulo!r}: imagem ![texto](docs/images/arquivo.png) ausente."
            )
        explicacao = " ".join(t.strip() for t in texto if t.strip())
        n = _contar_frases(explicacao)
        if not MIN_FRASES <= n <= MAX_FRASES:
            problemas.append(
                f"Consulta {rotulo!r}: explicação com {n} frases (esperado {MIN_FRASES} a {MAX_FRASES})."
            )
    return problemas


def verificar_readme(readme: str, cypher_consultas: str) -> list[str]:
    """Executa todas as verificacoes e devolve a lista de problemas."""
    return (
        verificar_abertura(readme)
        + verificar_secoes_obrigatorias(readme)
        + verificar_sumario(readme)
        + verificar_perguntas(readme)
        + verificar_estrutura(readme)
        + verificar_tecnologias(readme)
        + verificar_proximos_passos(readme)
        + verificar_troubleshooting(readme)
        + verificar_consultas(readme, extrair_consultas(cypher_consultas))
    )


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verifica o formato do README.")
    ap.add_argument("--readme", default=CAMINHO_README_PADRAO)
    ap.add_argument("--consultas", default=CAMINHO_CONSULTAS_PADRAO)
    args = ap.parse_args(argv)
    try:
        readme = Path(args.readme).read_text(encoding="utf-8")
        cypher = Path(args.consultas).read_text(encoding="utf-8")
    except OSError as e:
        print(f"Erro ao ler arquivo: {e}", file=sys.stderr)
        return 2
    problemas = verificar_readme(readme, cypher)
    for p in problemas:
        print(p)
    if problemas:
        print(f"{len(problemas)} problema(s) encontrado(s) no README.", file=sys.stderr)
        return 1
    print("README conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
