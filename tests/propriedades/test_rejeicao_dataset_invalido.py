"""Teste de propriedade da rejeição de dataset inválido sem gravação parcial."""
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import given, settings, strategies as st

from scripts import gerar_dataset
from scripts.gerar_dataset import Dataset, ErroValidacao, gerar, gravar, main

_ID_INEXISTENTE = 999999


def _corromper(ds: Dataset, tipo: str, indice: int) -> tuple[Dataset, str, str]:
    """Devolve (novo dataset, arquivo esperado, identificador inválido).

    O Dataset é frozen: constrói-se um novo com cópias das listas.
    """
    nos = {k: [dict(l) for l in v] for k, v in ds.nos.items()}
    rels = {k: [dict(l) for l in v] for k, v in ds.relacionamentos.items()}
    if tipo == "duplicar_id":
        original = nos["usuarios"][indice % len(nos["usuarios"])]
        nos["usuarios"].append(dict(original))
        return Dataset(nos, rels), "usuarios.csv", str(original["id"])
    rels["curtiu"].append(
        {"usuarioId": _ID_INEXISTENTE, "postagemId": 1, "em": "2024-01-01T00:00:00"}
    )
    return Dataset(nos, rels), "curtiu.csv", str(_ID_INEXISTENTE)


def _instantaneo(raiz: Path) -> dict[str, bytes | None]:
    """Mapa caminho relativo -> conteúdo (None para diretórios), incluindo temporários."""
    return {
        str(p.relative_to(raiz)): (p.read_bytes() if p.is_file() else None)
        for p in sorted(raiz.rglob("*"))
    }


# Feature: neo4j-graph-portfolio-project, Property 4: Dataset inválido é rejeitado sem gravação parcial
# **Validates: Requirements 3.9**
@settings(max_examples=100, deadline=None)
@given(
    semente=st.integers(min_value=0, max_value=20),
    tipo=st.sampled_from(["duplicar_id", "referencia_inexistente"]),
    indice=st.integers(min_value=0, max_value=199),
)
def test_dataset_invalido_e_rejeitado_sem_gravacao_parcial(semente, tipo, indice):
    corrompido, arquivo, ident = _corromper(gerar(semente), tipo, indice)

    with tempfile.TemporaryDirectory() as raiz_str:
        raiz = Path(raiz_str)
        destino = raiz / "data"
        destino.mkdir()
        (destino / ".gitkeep").write_bytes(b"")
        (destino / "usuarios.csv").write_bytes(b"conteudo previo\n")
        antes = _instantaneo(raiz)

        # gravar: erro com nome do arquivo e identificador inválido.
        with pytest.raises(ErroValidacao) as info:
            gravar(corrompido, destino)
        mensagem = str(info.value)
        assert arquivo in mensagem
        assert ident in mensagem
        assert _instantaneo(raiz) == antes

        # CLI: código de saída diferente de zero e destino intacto.
        with mock.patch.object(gerar_dataset, "gerar", return_value=corrompido):
            codigo = main(["--semente", str(semente), "--saida", str(destino)])
        assert codigo != 0
        assert _instantaneo(raiz) == antes
