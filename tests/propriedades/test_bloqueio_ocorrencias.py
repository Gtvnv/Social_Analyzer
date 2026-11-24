"""Teste de propriedade do bloqueio por ocorrências de termos proibidos."""
from hypothesis import given, settings, strategies as st

from scripts.varrer_termos import Ocorrencia, formatar_relatorio

# Termos fictícios; nenhum termo real é usado.
_TERMOS = st.sampled_from(["termo-ficticio-a", "termo ficticio b", "zzz_exemplo"])
_TIPOS = st.sampled_from(["conteudo", "nome", "commit", "png"])
# Referências e locais com prefixos distintos, para a checagem de presença ser inequívoca.
_REFERENCIAS = st.one_of(
    st.text("abcdef0123456789", min_size=40, max_size=40).map(lambda h: "sha-" + h),
    st.text("abcdefghij/._", min_size=1, max_size=30).map(lambda c: "caminho/" + c),
)
_LOCAIS = st.one_of(
    st.integers(min_value=1, max_value=100000).map(lambda n: f"linha-{n}"),
    st.sampled_from(["nome", "mensagem", "tEXt", "iTXt", "zTXt", "eXIf"]),
)
_OCORRENCIAS = st.builds(Ocorrencia, tipo=_TIPOS, referencia=_REFERENCIAS,
                         local=_LOCAIS, termo=_TERMOS)


# Feature: neo4j-graph-portfolio-project, Property 7: Ocorrências bloqueiam a publicação
# Validates: Requirements 9.5
@settings(max_examples=100)
@given(st.lists(_OCORRENCIAS, min_size=1, max_size=30))
def test_ocorrencias_bloqueiam_publicacao(achadas):
    relatorio, codigo = formatar_relatorio(achadas)
    assert codigo != 0
    linhas = relatorio.splitlines()
    for o in achadas:
        assert any(o.referencia in l and o.local in l for l in linhas), o


# Feature: neo4j-graph-portfolio-project, Property 7: Ocorrências bloqueiam a publicação
# Validates: Requirements 9.5
def test_conjunto_vazio_nao_bloqueia():
    _, codigo = formatar_relatorio([])
    assert codigo == 0
