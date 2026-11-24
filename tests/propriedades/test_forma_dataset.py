"""Teste de propriedade da forma e do formato do dataset gerado."""
import csv
import io

from hypothesis import HealthCheck, given, settings, strategies as st

from scripts.gerar_dataset import NOS, RELACIONAMENTOS, gerar, serializar

_LIMITE_BYTES = 5 * 1024 * 1024


# Feature: neo4j-graph-portfolio-project, Property 1: Forma e formato do dataset gerado
# **Validates: Requirements 3.1, 3.2, 3.3**
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(semente=st.integers())
def test_forma_e_formato_do_dataset(semente):
    arquivos = serializar(gerar(semente))

    assert sum(len(c) for c in arquivos.values()) <= _LIMITE_BYTES

    contagens = {}
    for nome, conteudo in arquivos.items():
        texto = conteudo.decode("utf-8")  # UTF-8 válido
        assert "\r" not in texto
        assert texto.endswith("\n")

        linhas = list(csv.reader(io.StringIO(texto, newline=""), delimiter=","))
        cabecalho, dados = linhas[0], linhas[1:]
        assert cabecalho and all(cabecalho)
        assert all(len(l) == len(cabecalho) for l in dados)
        # O cabeçalho é a primeira linha física, separada por vírgula.
        assert texto.split("\n", 1)[0] == ",".join(cabecalho)
        contagens[nome[:-4]] = len(dados)

    tipos_no = [n for n in NOS if contagens.get(n, 0) >= 1]
    tipos_rel = [r for r in RELACIONAMENTOS if contagens.get(r, 0) >= 1]
    assert len(tipos_no) >= 4
    assert len(tipos_rel) >= 5
    assert contagens["usuarios"] >= 100
    assert sum(contagens[r] for r in RELACIONAMENTOS) >= 500
