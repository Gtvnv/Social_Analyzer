"""Teste de propriedade da integridade de identificadores e referências."""
from hypothesis import given, settings, strategies as st

from scripts.gerar_dataset import gerar, validar

_CHAVES = {"usuarios": "id", "postagens": "id", "hashtags": "tag", "comunidades": "id"}

# Relacionamento -> [(coluna, nó referenciado)]
_REFERENCIAS = {
    "segue": [("usuarioId", "usuarios"), ("seguidoId", "usuarios")],
    "publicou": [("usuarioId", "usuarios"), ("postagemId", "postagens")],
    "curtiu": [("usuarioId", "usuarios"), ("postagemId", "postagens")],
    "comentou": [("usuarioId", "usuarios"), ("postagemId", "postagens")],
    "usa_hashtag": [("postagemId", "postagens"), ("tag", "hashtags")],
    "participa_de": [("usuarioId", "usuarios"), ("comunidadeId", "comunidades")],
}


# Feature: neo4j-graph-portfolio-project, Property 2: Integridade de identificadores e referências
# **Validates: Requirements 3.8**
@settings(max_examples=100, deadline=None)
@given(semente=st.integers(min_value=0, max_value=2**32 - 1))
def test_ids_unicos_e_referencias_existentes(semente):
    ds = gerar(semente)

    conhecidos = {}
    for no, chave in _CHAVES.items():
        ids = [str(linha[chave]) for linha in ds.nos[no]]
        assert len(ids) == len(set(ids)), f"ids duplicados em {no}"
        conhecidos[no] = set(ids)

    for rel, referencias in _REFERENCIAS.items():
        for linha in ds.relacionamentos[rel]:
            for coluna, no in referencias:
                assert str(linha[coluna]) in conhecidos[no], (
                    f"{rel}.{coluna}={linha[coluna]!r} não existe em {no}"
                )

    assert validar(ds) == []
