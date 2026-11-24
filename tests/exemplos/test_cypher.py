"""Testes de exemplo para os scripts Cypher em cypher/."""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CYPHER = RAIZ / "cypher"

CSVS = [
    "usuarios", "postagens", "hashtags", "comunidades", "segue",
    "publicou", "curtiu", "comentou", "usa_hashtag", "participa_de",
]
LABELS = ["Usuario", "Postagem", "Hashtag", "Comunidade"]
TIPOS = ["SEGUE", "PUBLICOU", "CURTIU", "COMENTOU", "USA_HASHTAG", "PARTICIPA_DE"]
ESCRITA = ["CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DETACH"]


def ler(nome: str) -> str:
    return (CYPHER / nome).read_text(encoding="utf-8")


def blocos(texto: str):
    """Divide o script em blocos separados por linha em branco.

    Retorna lista de (linhas_de_comentario, linhas_de_codigo).
    """
    resultado = []
    for bloco in re.split(r"\n\s*\n", texto.strip()):
        linhas = [l for l in bloco.splitlines() if l.strip()]
        comentarios = [l for l in linhas if l.lstrip().startswith("//")]
        codigo = [l for l in linhas if not l.lstrip().startswith("//")]
        resultado.append((comentarios, codigo, linhas))
    return resultado


def sem_comentarios(texto: str) -> str:
    return "\n".join(
        l for l in texto.splitlines() if not l.lstrip().startswith("//")
    )


def tem_palavra(texto: str, palavra: str) -> bool:
    return re.search(rf"\b{palavra}\b", texto, re.IGNORECASE) is not None


# ---------- 01_carga.cypher ----------

def test_carga_todo_bloco_tem_comentario_em_portugues_antes():
    for comentarios, codigo, linhas in blocos(ler("01_carga.cypher")):
        assert codigo, "bloco sem código"
        assert comentarios, f"bloco sem comentário: {codigo[0]}"
        assert linhas[0].lstrip().startswith("//"), (
            f"comentário não precede o bloco: {codigo[0]}"
        )
        # Comentários em português: contêm ao menos uma palavra comum do idioma.
        texto = " ".join(comentarios).lower()
        assert re.search(
            r"\b(de|do|da|dos|das|para|com|entre|por|nós|relacionamento)\b", texto
        ), f"comentário possivelmente fora do português: {texto}"


def test_carga_constraints_antes_do_primeiro_load_csv_de_nos():
    codigo = sem_comentarios(ler("01_carga.cypher"))
    primeiro_load = codigo.index("LOAD CSV")
    constraints = [m.start() for m in re.finditer(r"CREATE CONSTRAINT", codigo)]
    assert len(constraints) == 4
    assert all(pos < primeiro_load for pos in constraints)
    for alvo in ["Usuario", "Postagem", "Hashtag", "Comunidade"]:
        assert re.search(rf"CREATE CONSTRAINT .*\(\w+:{alvo}\)", codigo)


def test_carga_sem_create_para_dados():
    codigo = sem_comentarios(ler("01_carga.cypher"))
    for ocorrencia in re.finditer(r"\bCREATE\b(?!\s+CONSTRAINT)", codigo, re.IGNORECASE):
        pytest.fail(f"CREATE de dados na posição {ocorrencia.start()}")
    assert "MERGE" in codigo


def test_carga_um_load_csv_with_headers_por_csv():
    codigo = sem_comentarios(ler("01_carga.cypher"))
    assert len(CSVS) == 10
    total = len(re.findall(r"LOAD CSV WITH HEADERS", codigo))
    assert total == 10
    assert len(re.findall(r"LOAD CSV", codigo)) == 10
    for nome in CSVS:
        achados = re.findall(
            rf"LOAD CSV WITH HEADERS FROM 'file:///{nome}\.csv'", codigo
        )
        assert len(achados) == 1, f"{nome}.csv carregado {len(achados)} vez(es)"


# ---------- 03_consultas.cypher ----------

def consultas():
    """Lista de (comentarios, corpo) de cada consulta."""
    itens = []
    for comentarios, codigo, _ in blocos(ler("03_consultas.cypher")):
        itens.append((comentarios, "\n".join(codigo)))
    return itens


def test_consultas_somente_leitura():
    codigo = sem_comentarios(ler("03_consultas.cypher"))
    for palavra in ESCRITA:
        assert not tem_palavra(codigo, palavra), f"{palavra} em consulta"
    assert not re.search(r"DETACH\s+DELETE", codigo, re.IGNORECASE)


def test_consultas_ao_menos_cinco_com_pergunta_de_ate_200_caracteres():
    itens = consultas()
    assert len(itens) >= 5
    for comentarios, corpo in itens:
        assert corpo.strip(), "bloco sem consulta"
        assert len(comentarios) == 1, f"esperado um comentário: {corpo[:40]}"
        pergunta = comentarios[0].strip()
        assert re.fullmatch(r"//\s*.+\?", pergunta), f"não é pergunta: {pergunta}"
        texto = pergunta[2:].strip()
        assert len(texto) <= 200


def test_consultas_cobrem_dois_saltos_shortestpath_e_agregacao():
    corpos = [c for _, c in consultas()]

    def dois_saltos(c: str) -> bool:
        encadeado = re.search(r"\)-\[[^\]]*\]->\([^)]*\)-\[[^\]]*\]->", c)
        variavel = re.search(r"\*\s*(\d*)\s*\.\.\s*(\d+)", c)
        variavel_2 = variavel and int(variavel.group(2)) >= 2
        return bool(encadeado or variavel_2)

    assert any(dois_saltos(c) for c in corpos)
    assert any(re.search(r"shortestPath\s*\(", c) for c in corpos)
    assert any(
        re.search(r"\b(count|sum|avg|min|max|collect)\s*\(", c, re.IGNORECASE)
        for c in corpos
    )


# ---------- 02_verificacao.cypher ----------

def test_verificacao_somente_leitura():
    codigo = sem_comentarios(ler("02_verificacao.cypher"))
    for palavra in ESCRITA:
        assert not tem_palavra(codigo, palavra), f"{palavra} na verificação"


def test_verificacao_cobre_quatro_labels_e_seis_tipos():
    codigo = sem_comentarios(ler("02_verificacao.cypher"))
    for label in LABELS:
        assert re.search(rf"\(\w*:{label}\)", codigo), label
    for tipo in TIPOS:
        assert re.search(rf"\[\w*:{tipo}\]", codigo), tipo
    assert len(LABELS) + len(TIPOS) == 10
    assert len(re.findall(r"\bMATCH\b", codigo)) == 10
