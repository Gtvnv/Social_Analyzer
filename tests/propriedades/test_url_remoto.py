"""Teste de propriedade da validação da URL do remoto."""
import string

from hypothesis import given, settings, strategies as st

from scripts.validar_publicacao import url_remoto_valida

_PERMITIDOS = frozenset(string.ascii_letters + string.digits + "._-")
_PREFIXOS = ("https://github.com/Gtvnv/", "git@github.com:Gtvnv/")
_SUFIXO = ".git"


def _oraculo(url: str) -> bool:
    """Oráculo independente: sem regex, decompõe prefixo, nome e sufixo."""
    for prefixo in _PREFIXOS:
        if url.startswith(prefixo) and url.endswith(_SUFIXO):
            if len(url) < len(prefixo) + len(_SUFIXO):
                continue
            nome = url[len(prefixo):len(url) - len(_SUFIXO)]
            if 1 <= len(nome) <= 100 and all(c in _PERMITIDOS for c in nome):
                return True
    return False


_nome_valido = st.text(alphabet=sorted(_PERMITIDOS), min_size=1, max_size=100)
_prefixo = st.sampled_from(_PREFIXOS)

_validas = st.builds(lambda p, n: p + n + _SUFIXO, _prefixo, _nome_valido)


@st.composite
def _mutacoes(draw):
    prefixo = draw(_prefixo)
    nome = draw(_nome_valido)
    tipo = draw(st.sampled_from([
        "nome_vazio", "nome_101", "outro_usuario", "http", "sufixo",
        "newline_final", "char_invalido", "sem_sufixo",
    ]))
    if tipo == "nome_vazio":
        return prefixo + _SUFIXO
    if tipo == "nome_101":
        n = draw(st.text(alphabet=sorted(_PERMITIDOS), min_size=101, max_size=101))
        return prefixo + n + _SUFIXO
    if tipo == "outro_usuario":
        outro = draw(st.text(alphabet=sorted(_PERMITIDOS), min_size=1, max_size=15)
                     .filter(lambda u: u != "Gtvnv"))
        return prefixo.replace("Gtvnv", outro) + nome + _SUFIXO
    if tipo == "http":
        return "http://github.com/Gtvnv/" + nome + _SUFIXO
    if tipo == "sufixo":
        extra = draw(st.text(min_size=1, max_size=5))
        return prefixo + nome + _SUFIXO + extra
    if tipo == "newline_final":
        return prefixo + nome + _SUFIXO + draw(st.sampled_from(["\n", "\r\n", " "]))
    if tipo == "char_invalido":
        ruim = draw(st.sampled_from(["/", " ", "@", ":", "ç", "\n", "*"]))
        pos = draw(st.integers(0, len(nome)))
        return prefixo + nome[:pos] + ruim + nome[pos:] + _SUFIXO
    return prefixo + nome


# Feature: neo4j-graph-portfolio-project, Property 8: Validação da URL do remoto
# **Validates: Requirements 10.1**
@settings(max_examples=200)
@given(st.one_of(_validas, _mutacoes(), st.text(max_size=150)))
def test_url_remoto_valida_equivale_ao_oraculo(url):
    assert url_remoto_valida(url) == _oraculo(url)


@settings(max_examples=100)
@given(_validas)
def test_urls_validas_sao_aceitas(url):
    assert url_remoto_valida(url) is True


@settings(max_examples=200)
@given(_mutacoes())
def test_mutacoes_invalidas_sao_rejeitadas(url):
    assert url_remoto_valida(url) is _oraculo(url)
