"""Teste de propriedade do verificador de links relativos."""
from hypothesis import given, settings, strategies as st

from scripts.verificar_links import links_quebrados

_segmento = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=8)
_caminho = st.builds(
    lambda partes, ext: "/".join(partes) + "." + ext,
    st.lists(_segmento, min_size=1, max_size=3),
    st.sampled_from(["md", "png", "csv", "cypher"]),
)
_ancora = st.one_of(st.just(""), _segmento.map(lambda s: "#" + s))
_forma = st.sampled_from(["link", "imagem"])


@st.composite
def _cenarios(draw):
    existentes = draw(st.sets(_caminho, max_size=10))
    # Destinos: parte escolhida entre os existentes, parte arbitrária (pode não existir).
    destinos = []
    entradas = draw(st.lists(st.tuples(_caminho, _ancora, _forma, st.booleans()), max_size=12))
    lista_existentes = sorted(existentes)
    for caminho, ancora, forma, usar_existente in entradas:
        if usar_existente and lista_existentes:
            caminho = draw(st.sampled_from(lista_existentes))
        destinos.append((caminho, ancora, forma))
    return existentes, destinos


# Feature: neo4j-graph-portfolio-project, Property 5: Verificador de links relativos
# **Validates: Requirements 8.6, 8.7, 8.8**
@settings(max_examples=200, deadline=None)
@given(_cenarios())
def test_links_quebrados_retorna_exatamente_os_inexistentes(cenario):
    existentes, destinos = cenario
    linhas = ["# Documento", ""]
    for i, (caminho, ancora, forma) in enumerate(destinos):
        prefixo = "!" if forma == "imagem" else ""
        linhas.append(f"Item {i}: {prefixo}[texto{i}]({caminho}{ancora})")
    # Links que devem ser ignorados: externos e âncora pura.
    linhas.append("[site](https://exemplo.org/x.md) [ancora](#secao) [mail](mailto:a@b.c)")
    markdown = "\n".join(linhas)

    esperado = [c for c, _, _ in destinos if c not in existentes]
    resultado = links_quebrados(markdown, existentes)

    assert resultado == esperado
    assert (resultado == []) == all(c in existentes for c, _, _ in destinos)
