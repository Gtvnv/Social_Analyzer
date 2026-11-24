# -*- coding: utf-8 -*-
"""Testes de consistência entre os artefatos do repositório.

Compara labels, tipos de relacionamento e propriedades entre
`cypher/01_carga.cypher`, a tabela do modelo no `README.md`,
`docs/modelo.arrows.json` e os cabeçalhos dos CSVs em `data/` (com o
dicionário de dados do README). Também executa o verificador de links e o de
README sobre o `README.md` real.

**Validates: Requirements 2.8, 3.5, 8.8**
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from scripts import verificar_links, verificar_readme

RAIZ = Path(__file__).resolve().parents[2]
README = (RAIZ / "README.md").read_text(encoding="utf-8")
CARGA = (RAIZ / "cypher" / "01_carga.cypher").read_text(encoding="utf-8")
CONSULTAS = (RAIZ / "cypher" / "03_consultas.cypher").read_text(encoding="utf-8")
ARROWS = json.loads((RAIZ / "docs" / "modelo.arrows.json").read_text(encoding="utf-8"))

PENDENTE = "pendente do autor: capturas PNG / troubleshooting reais"

Props = dict[str, str]  # nome da propriedade -> tipo canônico


# --------------------------------------------------------------------- tipos
def _tipo_readme(texto: str) -> str:
    t = texto.strip().lower()
    if t.startswith("inteiro"):
        return "Integer"
    if t.startswith("booleano"):
        return "Boolean"
    if t.startswith("data e hora"):
        return "DateTime"
    if t.startswith("data"):
        return "Date"
    if t.startswith("texto"):
        return "String"
    raise AssertionError(f"Tipo desconhecido no README: {texto!r}")


def _tipo_cypher(expr: str) -> str:
    e = expr.strip()
    for prefixo, tipo in (
        ("tointeger(", "Integer"),
        ("toboolean(", "Boolean"),
        ("datetime(", "DateTime"),
        ("date(", "Date"),
    ):
        if e.lower().startswith(prefixo):
            return tipo
    return "String"


# ------------------------------------------------------------------ arrows
def _arrows() -> tuple[dict[str, Props], dict[str, tuple[str, str, Props]]]:
    rotulo_por_id = {n["id"]: n["labels"][0] for n in ARROWS["nodes"]}
    nos = {n["labels"][0]: dict(n["properties"]) for n in ARROWS["nodes"]}
    rels = {
        r["type"]: (rotulo_por_id[r["fromId"]], rotulo_por_id[r["toId"]], dict(r["properties"]))
        for r in ARROWS["relationships"]
    }
    return nos, rels


# ------------------------------------------------------------------- README
def _tabela(readme: str, titulo_negrito: str) -> list[list[str]]:
    """Linhas (células) da primeira tabela após `**titulo_negrito**`."""
    linhas = readme.splitlines()
    inicio = next(i for i, l in enumerate(linhas) if l.strip() == f"**{titulo_negrito}**")
    linhas_tab: list[str] = []
    for l in linhas[inicio + 1:]:
        if l.strip().startswith("|"):
            linhas_tab.append(l)
        elif linhas_tab:
            break
    celulas = [[c.strip() for c in l.strip().strip("|").split("|")] for l in linhas_tab]
    return celulas[2:]  # descarta cabeçalho e separador


def _props_readme(celula: str) -> Props:
    return {nome: _tipo_readme(tipo) for nome, tipo in re.findall(r"`(\w+)` \(([^)]+)\)", celula)}


def _readme_modelo() -> tuple[dict[str, Props], dict[str, tuple[str, str, Props]]]:
    nos = {
        re.sub(r"`", "", l[0]): _props_readme(l[2]) for l in _tabela(README, "Nós")
    }
    rels: dict[str, tuple[str, str, Props]] = {}
    for l in _tabela(README, "Relacionamentos"):
        origem, destino = (re.sub(r"`", "", p).strip() for p in l[2].split("→"))
        rels[re.sub(r"`", "", l[0])] = (origem, destino, _props_readme(l[3]))
    return nos, rels


def _identificadores_readme() -> dict[str, str]:
    return {re.sub(r"`", "", l[0]): re.sub(r"`", "", l[3]) for l in _tabela(README, "Nós")}


def _dicionario_readme() -> dict[str, list[tuple[str, str]]]:
    """Arquivo CSV -> lista ordenada de (coluna, tipo do README)."""
    saida: dict[str, list[tuple[str, str]]] = {}
    linhas = README.splitlines()
    i = 0
    while i < len(linhas):
        m = re.fullmatch(r"`data/(\w+\.csv)`", linhas[i].strip())
        if m:
            colunas: list[tuple[str, str]] = []
            j = i + 1
            while j < len(linhas) and not linhas[j].strip().startswith("|"):
                j += 1
            j += 2  # cabeçalho e separador
            while j < len(linhas) and linhas[j].strip().startswith("|"):
                cel = [c.strip() for c in linhas[j].strip().strip("|").split("|")]
                colunas.append((cel[0].strip("`"), cel[1]))
                j += 1
            saida[m.group(1)] = colunas
            i = j
        else:
            i += 1
    return saida


# ------------------------------------------------------------------- Cypher
class _Bloco:
    def __init__(self, arquivo: str, colunas: set[str], colunas_match: set[str],
                 nos: dict[str, Props], rels: dict[str, tuple[str, str, Props]]):
        self.arquivo = arquivo
        self.colunas = colunas
        self.colunas_match = colunas_match
        self.nos = nos
        self.rels = rels


def _blocos_carga() -> list[_Bloco]:
    sem_comentario = "\n".join(l for l in CARGA.splitlines() if not l.strip().startswith("//"))
    blocos: list[_Bloco] = []
    for texto in (b.strip() for b in sem_comentario.split(";")):
        m = re.search(r"LOAD CSV WITH HEADERS FROM 'file:///(\w+\.csv)'", texto)
        if not m:
            continue
        colunas = set(re.findall(r"linha\.(\w+)", texto))
        colunas_match = {
            c for l in texto.splitlines() if l.strip().startswith("MATCH")
            for c in re.findall(r"linha\.(\w+)", l)
        }
        rotulo_por_var = dict(re.findall(r"\((\w+):(\w+)", texto))
        # SET var.prop = expr, ...
        sets: dict[str, dict[str, str]] = {}
        m_set = re.search(r"\bSET\b(.*)$", texto, re.S)
        if m_set:
            for item in m_set.group(1).split(","):
                a = re.match(r"\s*(\w+)\.(\w+)\s*=\s*(.+?)\s*$", item, re.S)
                if a:
                    sets.setdefault(a.group(1), {})[a.group(2)] = a.group(3)
        nos: dict[str, Props] = {}
        rels: dict[str, tuple[str, str, Props]] = {}
        mn = re.search(r"MERGE \((\w+):(\w+)(?: \{([^}]*)\})?\)\s*(?:SET|$)", texto)
        mr = re.search(r"MERGE \((\w+)\)-\[(\w*):(\w+)(?: \{([^}]*)\})?\]->\((\w+)\)", texto)
        if mr:
            origem, var, tipo, mapa, destino = mr.groups()
            props: Props = {}
            for k, v in re.findall(r"(\w+):\s*(.+?)(?:,|$)", mapa or ""):
                props[k] = _tipo_cypher(v)
            for k, v in sets.get(var, {}).items():
                props[k] = _tipo_cypher(v)
            rels[tipo] = (rotulo_por_var[origem], rotulo_por_var[destino], props)
        elif mn:
            var, rotulo, mapa = mn.groups()
            props = {k: _tipo_cypher(v) for k, v in re.findall(r"(\w+):\s*(.+?)(?:,|$)", mapa or "")}
            for k, v in sets.get(var, {}).items():
                props[k] = _tipo_cypher(v)
            nos[rotulo] = props
        blocos.append(_Bloco(m.group(1), colunas, colunas_match, nos, rels))
    return blocos


def _cypher_modelo() -> tuple[dict[str, Props], dict[str, tuple[str, str, Props]]]:
    nos: dict[str, Props] = {}
    rels: dict[str, tuple[str, str, Props]] = {}
    for b in _blocos_carga():
        nos.update(b.nos)
        rels.update(b.rels)
    return nos, rels


def _cabecalho(arquivo: str) -> list[str]:
    with (RAIZ / "data" / arquivo).open(encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


# ============================================================ sanidade dos parsers
def test_parsers_extraem_o_modelo_completo():
    nos, rels = _cypher_modelo()
    assert set(nos) == {"Usuario", "Postagem", "Hashtag", "Comunidade"}
    assert set(rels) == {"SEGUE", "PUBLICOU", "CURTIU", "COMENTOU", "USA_HASHTAG", "PARTICIPA_DE"}
    assert len(_blocos_carga()) == 10
    assert len(_dicionario_readme()) == 10


# ======================================== labels, tipos e propriedades (Req. 2.8)
def test_labels_iguais_entre_cypher_readme_e_arrows():
    c, r, a = _cypher_modelo()[0], _readme_modelo()[0], _arrows()[0]
    assert set(c) == set(r) == set(a)


def test_tipos_de_relacionamento_iguais_entre_cypher_readme_e_arrows():
    c, r, a = _cypher_modelo()[1], _readme_modelo()[1], _arrows()[1]
    assert set(c) == set(r) == set(a)


@pytest.mark.parametrize("label", ["Usuario", "Postagem", "Hashtag", "Comunidade"])
def test_propriedades_de_nos_iguais_entre_artefatos(label):
    cypher = _cypher_modelo()[0][label]
    readme = _readme_modelo()[0][label]
    arrows = _arrows()[0][label]
    assert cypher == readme == arrows


@pytest.mark.parametrize(
    "tipo", ["SEGUE", "PUBLICOU", "CURTIU", "COMENTOU", "USA_HASHTAG", "PARTICIPA_DE"]
)
def test_direcao_e_propriedades_de_relacionamentos_iguais_entre_artefatos(tipo):
    cypher = _cypher_modelo()[1][tipo]
    readme = _readme_modelo()[1][tipo]
    arrows = _arrows()[1][tipo]
    assert cypher == readme == arrows


def test_constraints_de_unicidade_cobrem_o_identificador_de_cada_label():
    constraints = set(
        re.findall(r"FOR \(\w+:(\w+)\) REQUIRE \w+\.(\w+) IS UNIQUE", CARGA)
    )
    assert constraints == set(_identificadores_readme().items())


# ================================== CSVs e dicionário de dados (Req. 3.5)
def test_todo_csv_de_data_esta_no_dicionario_e_na_carga():
    em_disco = {p.name for p in (RAIZ / "data").glob("*.csv")}
    assert em_disco == set(_dicionario_readme()) == {b.arquivo for b in _blocos_carga()}


@pytest.mark.parametrize("arquivo", sorted(p.name for p in (RAIZ / "data").glob("*.csv")))
def test_cabecalho_do_csv_igual_ao_dicionario_de_dados(arquivo):
    colunas = [c for c, _ in _dicionario_readme()[arquivo]]
    assert _cabecalho(arquivo) == colunas


@pytest.mark.parametrize("arquivo", sorted(p.name for p in (RAIZ / "data").glob("*.csv")))
def test_colunas_lidas_pela_carga_iguais_ao_cabecalho_do_csv(arquivo):
    bloco = next(b for b in _blocos_carga() if b.arquivo == arquivo)
    assert bloco.colunas == set(_cabecalho(arquivo))


@pytest.mark.parametrize("arquivo", sorted(p.name for p in (RAIZ / "data").glob("*.csv")))
def test_colunas_de_propriedade_do_csv_correspondem_ao_modelo(arquivo):
    """Colunas de nós e colunas não-chave de relacionamentos viram propriedades
    com o mesmo nome e o mesmo tipo do dicionário de dados."""
    bloco = next(b for b in _blocos_carga() if b.arquivo == arquivo)
    tipos_dicionario = {c: _tipo_readme(t) for c, t in _dicionario_readme()[arquivo]}
    if bloco.nos:
        (props,) = bloco.nos.values()
        colunas_prop = bloco.colunas
    else:
        (_, _, props), = bloco.rels.values()
        colunas_prop = bloco.colunas - bloco.colunas_match
    assert colunas_prop == set(props)
    assert {c: tipos_dicionario[c] for c in colunas_prop} == props


# ============================================= links do README real (Req. 8.8)
def _links_quebrados_readme() -> list[str]:
    existentes = verificar_links._listar_existentes(RAIZ)
    return verificar_links.links_quebrados(README, existentes)


@pytest.mark.xfail(strict=False, reason=PENDENTE)
def test_nenhuma_imagem_ausente_em_docs_images():
    ausentes = [l for l in _links_quebrados_readme() if l.startswith("docs/images/")]
    assert ausentes == []


def test_links_quebrados_alem_das_imagens_pendentes_do_autor():
    outros = [l for l in _links_quebrados_readme() if not l.startswith("docs/images/")]
    assert outros == []


# ========================================== verificador de README (Req. 8.8)
def _problemas_readme() -> list[str]:
    return verificar_readme.verificar_readme(README, CONSULTAS)


def _e_contagem_troubleshooting(problema: str) -> bool:
    return problema.startswith("Troubleshooting:") and "entradas (mínimo" in problema


@pytest.mark.xfail(strict=False, reason=PENDENTE)
def test_troubleshooting_tem_o_minimo_de_entradas():
    assert [p for p in _problemas_readme() if _e_contagem_troubleshooting(p)] == []


def test_verificador_de_readme_sem_problemas_alem_do_troubleshooting_pendente():
    outros = [p for p in _problemas_readme() if not _e_contagem_troubleshooting(p)]
    assert outros == []
