"""Teste de propriedade para a validação do nome de branch de trabalho."""

from hypothesis import given, settings, strategies as st

from scripts.validar_publicacao import branch_valida

PREFIXOS = ("feature", "fix", "hotfix", "chore", "refactor", "docs", "test")
_ALFANUM = set("abcdefghijklmnopqrstuvwxyz0123456789")


def _oraculo(nome: str) -> bool:
    """Oráculo independente: sem regex, usa split e conjuntos de caracteres."""
    if "/" not in nome:
        return False
    prefixo, resto = nome.split("/", 1)
    if prefixo not in PREFIXOS or resto == "":
        return False
    segmentos = resto.split("-")
    return all(seg != "" and set(seg) <= _ALFANUM for seg in segmentos)


_segmento = st.text(alphabet=sorted(_ALFANUM), min_size=1, max_size=8)
_kebab = st.lists(_segmento, min_size=1, max_size=4).map("-".join)
_prefixo = st.sampled_from(PREFIXOS)

_validos = st.builds(lambda p, n: f"{p}/{n}", _prefixo, _kebab)

_invalidos = st.one_of(
    # prefixo errado
    st.builds(
        lambda p, n: f"{p}/{n}",
        st.sampled_from(["feat", "bugfix", "release", "main", "Feature", "FIX", "", "feature2", "docs/x"]),
        _kebab,
    ),
    # sem barra
    st.builds(lambda p, n: f"{p}-{n}", _prefixo, _kebab),
    # nome vazio
    st.builds(lambda p: f"{p}/", _prefixo),
    # maiúsculas
    st.builds(lambda p, n: f"{p}/{n}X", _prefixo, _kebab),
    st.builds(lambda p, n: f"{p}/A{n}", _prefixo, _kebab),
    # hífen duplo, inicial e final
    st.builds(lambda p, a, b: f"{p}/{a}--{b}", _prefixo, _segmento, _segmento),
    st.builds(lambda p, n: f"{p}/-{n}", _prefixo, _kebab),
    st.builds(lambda p, n: f"{p}/{n}-", _prefixo, _kebab),
    # underscore
    st.builds(lambda p, a, b: f"{p}/{a}_{b}", _prefixo, _segmento, _segmento),
    # espaços
    st.builds(lambda p, a, b: f"{p}/{a} {b}", _prefixo, _segmento, _segmento),
    st.builds(lambda p, n: f" {p}/{n}", _prefixo, _kebab),
    st.builds(lambda p, n: f"{p}/{n} ", _prefixo, _kebab),
    # newline final
    st.builds(lambda p, n: f"{p}/{n}\n", _prefixo, _kebab),
    # barra adicional no nome
    st.builds(lambda p, a, b: f"{p}/{a}/{b}", _prefixo, _segmento, _segmento),
)


# Feature: neo4j-graph-portfolio-project, Property 9: Validação de nome de branch de trabalho
# **Validates: Requirements 10.3**
@settings(max_examples=200)
@given(_validos)
def test_branches_validas_sao_aceitas(nome):
    assert _oraculo(nome) is True
    assert branch_valida(nome) is True


# Feature: neo4j-graph-portfolio-project, Property 9: Validação de nome de branch de trabalho
# **Validates: Requirements 10.3**
@settings(max_examples=200)
@given(_invalidos)
def test_branches_invalidas_sao_rejeitadas(nome):
    assert _oraculo(nome) is False
    assert branch_valida(nome) is False


# Feature: neo4j-graph-portfolio-project, Property 9: Validação de nome de branch de trabalho
# **Validates: Requirements 10.3**
@settings(max_examples=300)
@given(st.one_of(st.text(max_size=30), _validos, _invalidos))
def test_branch_valida_concorda_com_oraculo(nome):
    assert branch_valida(nome) == _oraculo(nome)
