"""Teste de propriedade da detecção de termos proibidos (scripts/varrer_termos.py)."""
from hypothesis import given, settings, strategies as st

from scripts.varrer_termos import ocorrencias

# Termos FICTÍCIOS: nenhum termo real é usado nos testes.
TERMOS = ["zorbquux", "foo bar"]

# Fundo sem letras: não pode formar acidentalmente nenhum termo.
FUNDO = st.text(alphabet="0123456789.,;:!?/()\n\t ", max_size=40)

SEPARADORES = ["", " ", "-", "_"]


@st.composite
def variantes(draw, termo: str) -> str:
    """Termo com caixa arbitrária por caractere e separador variável entre as partes."""
    partes = termo.split()
    saida = []
    for i, parte in enumerate(partes):
        if i:
            saida.append(draw(st.sampled_from(SEPARADORES)))
        for c in parte:
            saida.append(draw(st.sampled_from([c.lower(), c.upper()])))
    return "".join(saida)


# Feature: neo4j-graph-portfolio-project, Property 6: Detecção de termos proibidos
# **Validates: Requirements 1.5, 9.1, 9.4**
@settings(max_examples=200, deadline=None)
@given(data=st.data(), antes=FUNDO, depois=FUNDO)
def test_texto_com_variacao_do_termo_e_detectado(data, antes, depois):
    termo = data.draw(st.sampled_from(TERMOS))
    variante = data.draw(variantes(termo))
    texto = antes + variante + depois
    assert len(ocorrencias(texto, TERMOS)) >= 1
    assert any(o.termo == termo for o in ocorrencias(texto, TERMOS))


# Feature: neo4j-graph-portfolio-project, Property 6: Detecção de termos proibidos
# **Validates: Requirements 1.5, 9.1, 9.4**
@settings(max_examples=200, deadline=None)
@given(texto=FUNDO)
def test_texto_sem_o_termo_nao_reporta_ocorrencias(texto):
    assert ocorrencias(texto, TERMOS) == []
