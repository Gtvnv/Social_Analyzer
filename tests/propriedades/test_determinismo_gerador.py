"""Teste de propriedade do determinismo do gerador de dataset por semente."""
from hypothesis import given, settings, strategies as st

from scripts.gerar_dataset import gerar, serializar

_sementes = st.integers(min_value=0, max_value=2**32 - 1)


def _saida(semente: int) -> dict[str, bytes]:
    return serializar(gerar(semente))


# Feature: neo4j-graph-portfolio-project, Property 3: Determinismo do gerador por semente
# **Validates: Requirements 3.6**
@settings(max_examples=100, deadline=None)
@given(s1=_sementes, s2=_sementes)
def test_determinismo_do_gerador_por_semente(s1, s2):
    primeira = _saida(s1)
    segunda = _saida(s1)

    # Mesma semente: mesmos arquivos e bytes idênticos.
    assert primeira.keys() == segunda.keys()
    for nome in primeira:
        assert primeira[nome] == segunda[nome], nome

    # Sementes distintas: ao menos um arquivo difere.
    if s1 != s2:
        outra = _saida(s2)
        assert primeira.keys() != outra.keys() or any(
            primeira[nome] != outra[nome] for nome in primeira
        )
