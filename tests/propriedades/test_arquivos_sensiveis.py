"""Teste de propriedade para a detecção de arquivos sensíveis no commit."""
from hypothesis import given, settings, strategies as st

from scripts.validar_publicacao import arquivo_sensivel

_SEGMENTO = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), max_codepoint=127)
    | st.sampled_from("-_."),
    min_size=1,
    max_size=8,
).filter(lambda s: s not in (".", ".."))

_DIRETORIO = st.lists(_SEGMENTO, max_size=4).flatmap(
    lambda partes: st.sampled_from(["/", "\\"]).map(
        lambda sep: "".join(p + sep for p in partes)
    )
)

_PREFIXO = st.text(alphabet="abcxyz019_-", min_size=1, max_size=8)

_SENSIVEIS = st.one_of(
    st.just(".env"),
    st.just(".ENV"),
    _PREFIXO.map(lambda p: p + ".pem"),
    _PREFIXO.map(lambda p: p + ".KEY"),
    _PREFIXO.map(lambda p: p + ".key"),
    st.tuples(_PREFIXO, st.sampled_from(["credentials", "credenciais", "service-account", "secret"]))
    .map(lambda t: f"{t[0]}-{t[1]}.json"),
)

_NAO_SENSIVEIS = st.one_of(
    st.just(".env.example"),
    st.just(".ENV.EXAMPLE"),
    _PREFIXO.map(lambda p: p + ".txt"),
    _PREFIXO.map(lambda p: p + ".py"),
    _PREFIXO.map(lambda p: "dados" + p + ".json"),
    _PREFIXO.map(lambda p: p + ".pem.txt"),
    _PREFIXO.map(lambda p: p + ".keys"),
    _PREFIXO.map(lambda p: "env" + p),
)

_CANDIDATO = st.tuples(
    _DIRETORIO,
    st.one_of(
        _SENSIVEIS.map(lambda b: (b, True)),
        _NAO_SENSIVEIS.map(lambda b: (b, False)),
    ),
).map(lambda t: (t[0] + t[1][0], t[1][1]))


# Feature: neo4j-graph-portfolio-project, Property 10: Detecção de arquivos sensíveis no commit
# **Validates: Requirements 10.5, 10.6**
@settings(max_examples=200, deadline=None)
@given(st.lists(_CANDIDATO, max_size=15))
def test_deteccao_de_arquivos_sensiveis(candidatos):
    caminhos = [c for c, _ in candidatos]
    sinalizados = [c for c in caminhos if arquivo_sensivel(c)]
    esperados = [c for c, sensivel in candidatos if sensivel]

    assert sinalizados == esperados
    assert not any(
        arquivo_sensivel(c) for c in caminhos if c.lower().endswith(".env.example")
    )
    # Commit interrompido se ao menos um caminho for sinalizado.
    interrompe = any(arquivo_sensivel(c) for c in caminhos)
    assert interrompe == any(s for _, s in candidatos)
