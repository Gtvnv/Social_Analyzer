"""Testes de integração com Neo4j (Docker Compose).

Cobrem idempotência da carga, contagens esperadas, tipos das propriedades e
execução das consultas de negócio.

**Validates: Requirements 4.6, 4.7, 4.9, 5.7**
"""
import re
import subprocess

import pytest

from tests.integracao.conftest import (
    CYPHER,
    RAIZ,
    contagens_esperadas,
    dividir_consultas,
    linhas_plain,
)

pytestmark = pytest.mark.integracao

LIMITE_CONSULTA_S = 30


def _contagens(neo4j) -> dict[str, int]:
    r = neo4j.cypher_arquivo(CYPHER / "02_verificacao.cypher")
    assert r.returncode == 0, r.stderr
    return {l[0]: int(l[2]) for l in linhas_plain(r.stdout)}


@pytest.fixture(scope="module")
def carga_duas_vezes(neo4j):
    """Executa a carga duas vezes e devolve as contagens após cada execução."""
    carga = CYPHER / "01_carga.cypher"
    r1 = neo4j.cypher_arquivo(carga)
    assert r1.returncode == 0, r1.stderr
    primeira = _contagens(neo4j)
    r2 = neo4j.cypher_arquivo(carga)
    assert r2.returncode == 0, r2.stderr
    segunda = _contagens(neo4j)
    return primeira, segunda


def test_carga_idempotente(carga_duas_vezes):
    """Requisito 4.6: reexecutar a carga não altera as contagens."""
    primeira, segunda = carga_duas_vezes
    assert primeira == segunda
    assert len(primeira) == 10


def test_contagens_batem_com_csvs(carga_duas_vezes):
    """Requisito 4.9: contagens iguais às derivadas dos CSVs em data/."""
    _, segunda = carga_duas_vezes
    assert segunda == contagens_esperadas()


def test_contagens_batem_com_readme(carga_duas_vezes):
    """Requisito 4.9: contagens documentadas no README (quando existir)."""
    readme = RAIZ / "README.md"
    if not readme.exists():
        pytest.skip("README.md ainda não existe")
    texto = readme.read_text(encoding="utf-8")
    _, segunda = carga_duas_vezes
    ausentes = []
    for elemento, total in segunda.items():
        # Linha do README que cita o elemento e o total esperado.
        padrao = rf"{re.escape(elemento)}\b[^\n]*?(?<![\d.,]){total}(?![\d])"
        if not re.search(padrao, texto):
            ausentes.append(f"{elemento}={total}")
    assert not ausentes, f"Contagens não documentadas no README: {ausentes}"


@pytest.mark.parametrize(
    "consulta, esperado",
    [
        ("MATCH (n:Usuario) RETURN DISTINCT toString(valueType(n.id)) AS t", "INTEGER"),
        ("MATCH (n:Postagem) RETURN DISTINCT toString(valueType(n.id)) AS t", "INTEGER"),
        ("MATCH (n:Comunidade) RETURN DISTINCT toString(valueType(n.id)) AS t", "INTEGER"),
        ("MATCH (n:Usuario) RETURN DISTINCT toString(valueType(n.dataCadastro)) AS t", "DATE"),
        ("MATCH (n:Usuario) RETURN DISTINCT toString(valueType(n.verificado)) AS t", "BOOLEAN"),
        ("MATCH ()-[r:SEGUE]->() RETURN DISTINCT toString(valueType(r.desde)) AS t", "DATE"),
    ],
)
def test_tipos_das_propriedades(carga_duas_vezes, neo4j, consulta, esperado):
    """Requisito 4.7: inteiro, data e booleano convertidos explicitamente."""
    r = neo4j.cypher(consulta + ";")
    assert r.returncode == 0, r.stderr
    tipos = {l[0].strip('"') for l in linhas_plain(r.stdout)}
    assert len(tipos) == 1
    assert next(iter(tipos)).startswith(esperado)


def _consultas_negocio() -> list[str]:
    texto = (CYPHER / "03_consultas.cypher").read_text(encoding="utf-8")
    return dividir_consultas(texto)


@pytest.mark.parametrize(
    "consulta",
    _consultas_negocio(),
    ids=[f"consulta-{i}" for i in range(1, len(_consultas_negocio()) + 1)],
)
def test_consulta_de_negocio_retorna_linhas(carga_duas_vezes, neo4j, consulta):
    """Requisito 5.7: cada consulta termina em até 30 s e retorna >= 1 linha."""
    try:
        r = neo4j.cypher(consulta + ";", timeout=LIMITE_CONSULTA_S)
    except subprocess.TimeoutExpired:
        pytest.fail(f"Consulta excedeu {LIMITE_CONSULTA_S} s")
    assert r.returncode == 0, r.stderr
    assert len(linhas_plain(r.stdout)) >= 1
