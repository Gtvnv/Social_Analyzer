"""Testes de exemplo para scripts/verificar_readme.py.

Usa READMEs mínimos (válidos e inválidos) montados em string e uma consulta
.cypher mínima.

**Validates: Requirements 1.1, 1.3, 7.1, 7.2, 8.2, 8.4, 8.5, 10.8**
"""
import pytest

from scripts import verificar_readme as vr

CYPHER = "// Quem tem mais seguidores?\nMATCH (p:Pessoa)\nRETURN p.nome;\n"

ABERTURA = (
    "# Social Analyzer\n\n"
    "https://github.com/Gtvnv/social-analyzer-neo4j\n\n"
    "Análise de uma rede social sintética com grafos.\n"
)

SUMARIO = (
    "## Sumário\n\n"
    "- [Contexto](#contexto)\n"
    "- [Perguntas de negócio](#perguntas-de-negócio)\n"
    "- [Consultas de negócio](#consultas-de-negócio)\n"
    "- [Estrutura do repositório](#estrutura-do-repositório)\n"
    "- [Tecnologias](#tecnologias)\n"
    "- [Próximos passos](#próximos-passos)\n"
    "- [Troubleshooting](#troubleshooting)\n\n"
)

CONTEXTO = "## Contexto\n\nProjeto de portfólio.\n\n"

PERGUNTAS = (
    "## Perguntas de negócio\n\n"
    + "".join(f"- Pergunta {i}?\n" for i in range(1, 6))
    + "\n"
)

CONSULTAS = (
    "## Consultas de negócio\n\n"
    "### Quem tem mais seguidores?\n\n"
    "```cypher\nMATCH (p:Pessoa)\nRETURN p.nome;\n```\n\n"
    "A consulta lista as pessoas.\n\n"
    "![Resultado](docs/images/consulta-1.png)\n\n"
)

ARVORE = (
    "## Estrutura do repositório\n\n"
    "```text\n"
    "projeto/\n"
    "├── data/             # CSVs do dataset\n"
    "├── cypher/           # carga e consultas\n"
    "├── docs/\n"
    "│   └── images/       # evidências visuais\n"
    "└── scripts/          # verificadores\n"
    "```\n\n"
)

TECNOLOGIAS = "## Tecnologias\n\n- Neo4j 5.x\n- Python 3.12\n\n"

PASSOS = "## Próximos passos\n\n- Passo um\n- Passo dois\n\n"


def _entrada(i: int) -> str:
    return (
        f"### Problema {i}\n\n"
        "- **Sintoma:** algo falha\n"
        "- **Causa:** motivo\n"
        "- **Solução:** corrigir\n\n"
        "```text\nerro exato\n```\n\n"
    )


def _troubleshooting(n: int = 5) -> str:
    return "## Troubleshooting\n\n" + "".join(_entrada(i) for i in range(n))


def montar(**partes: str) -> str:
    base = {
        "abertura": ABERTURA,
        "sumario": SUMARIO,
        "contexto": CONTEXTO,
        "perguntas": PERGUNTAS,
        "consultas": CONSULTAS,
        "arvore": ARVORE,
        "tecnologias": TECNOLOGIAS,
        "passos": PASSOS,
        "troubleshooting": _troubleshooting(),
    }
    base.update(partes)
    return "\n".join(base.values())


def _problemas(readme: str) -> list[str]:
    return vr.verificar_readme(readme, CYPHER)


def test_readme_valido_sem_problemas():
    assert _problemas(montar()) == []


# ------------------------------------------------------------------ abertura


def test_resumo_ausente():
    readme = "# Social Analyzer\n\nhttps://github.com/Gtvnv/x\n"
    assert any("resumo" in p for p in vr.verificar_abertura(readme))


def test_link_github_fora_das_cinco_primeiras_linhas():
    abertura = (
        "# Titulo\n\nResumo curto.\n\nLinha a\n\nLinha b\n\nLinha c\n\n"
        "https://github.com/Gtvnv/x\n"
    )
    assert any("link" in p for p in vr.verificar_abertura(abertura))


# ------------------------------------------------------------------ sumário


def test_sem_sumario():
    sem = montar(sumario="")
    assert any("Sumário" in p for p in vr.verificar_secoes_obrigatorias(sem))


def test_sumario_com_link_faltando():
    sumario = SUMARIO.replace("- [Tecnologias](#tecnologias)\n", "")
    problemas = vr.verificar_sumario(montar(sumario=sumario))
    assert any("Tecnologias" in p for p in problemas)


# ------------------------------------------------------------------ perguntas


@pytest.mark.parametrize("n", [4, 11])
def test_perguntas_fora_do_intervalo(n):
    perguntas = "## Perguntas de negócio\n\n" + "".join(
        f"- Pergunta {i}?\n" for i in range(n)
    )
    problemas = vr.verificar_perguntas(montar(perguntas=perguntas))
    assert any(f"{n} itens" in p for p in problemas)


def test_pergunta_sem_interrogacao():
    perguntas = PERGUNTAS.replace("Pergunta 3?", "Pergunta 3")
    problemas = vr.verificar_perguntas(montar(perguntas=perguntas))
    assert len(problemas) == 1 and "'?'" in problemas[0]


# ------------------------------------------------------------------ estrutura


def test_arvore_sem_diretorio_obrigatorio():
    arvore = ARVORE.replace("└── scripts/          # verificadores\n", "")
    problemas = vr.verificar_estrutura(montar(arvore=arvore))
    assert any("scripts/" in p and "ausente" in p for p in problemas)


def test_arvore_descricao_longa():
    arvore = ARVORE.replace("# CSVs do dataset", "# " + "x" * 121)
    problemas = vr.verificar_estrutura(montar(arvore=arvore))
    assert any("data/" in p and "121" in p for p in problemas)


# ------------------------------------------------------------------ tecnologias


def test_tecnologia_sem_versao():
    tec = "## Tecnologias\n\n- Neo4j\n- Python 3.12\n\n"
    problemas = vr.verificar_tecnologias(montar(tecnologias=tec))
    assert len(problemas) == 1 and "Neo4j" in problemas[0]


# ------------------------------------------------------------------ próximos passos


@pytest.mark.parametrize("n", [1, 11])
def test_proximos_passos_fora_do_intervalo(n):
    passos = "## Próximos passos\n\n" + "".join(f"- Passo {i}\n" for i in range(n))
    problemas = vr.verificar_proximos_passos(montar(passos=passos))
    assert any(f"{n} itens" in p for p in problemas)


# ------------------------------------------------------------------ troubleshooting


def test_troubleshooting_com_menos_de_cinco_entradas():
    problemas = vr.verificar_troubleshooting(montar(troubleshooting=_troubleshooting(4)))
    assert any("4 entradas" in p for p in problemas)


def test_troubleshooting_campo_faltando():
    ts = _troubleshooting().replace("- **Causa:** motivo\n", "", 1)
    problemas = vr.verificar_troubleshooting(montar(troubleshooting=ts))
    assert len(problemas) == 1 and "campo Causa ausente" in problemas[0]


def test_troubleshooting_sem_bloco_de_codigo():
    ts = _troubleshooting().replace("```text\nerro exato\n```\n", "", 1)
    problemas = vr.verificar_troubleshooting(montar(troubleshooting=ts))
    assert len(problemas) == 1 and "bloco de código" in problemas[0]


# ------------------------------------------------------------------ consultas


def test_consulta_sem_imagem():
    consultas = CONSULTAS.replace("![Resultado](docs/images/consulta-1.png)\n", "")
    problemas = vr.verificar_consultas(
        montar(consultas=consultas), vr.extrair_consultas(CYPHER)
    )
    assert len(problemas) == 1 and "imagem" in problemas[0]


def test_consulta_sem_explicacao():
    consultas = CONSULTAS.replace("A consulta lista as pessoas.\n", "")
    problemas = vr.verificar_consultas(
        montar(consultas=consultas), vr.extrair_consultas(CYPHER)
    )
    assert any("0 frases" in p for p in problemas)


# ------------------------------------------------------------------ CLI


def _arquivos(tmp_path, readme: str):
    r = tmp_path / "README.md"
    c = tmp_path / "consultas.cypher"
    r.write_text(readme, encoding="utf-8")
    c.write_text(CYPHER, encoding="utf-8")
    return ["--readme", str(r), "--consultas", str(c)]


def test_cli_codigo_0(tmp_path, capsys):
    assert vr.main(_arquivos(tmp_path, montar())) == 0
    assert "conforme" in capsys.readouterr().out


def test_cli_codigo_1(tmp_path, capsys):
    ts = _troubleshooting(4)
    assert vr.main(_arquivos(tmp_path, montar(troubleshooting=ts))) == 1
    assert "Troubleshooting" in capsys.readouterr().out


def test_cli_codigo_2_arquivo_inexistente(tmp_path):
    args = ["--readme", str(tmp_path / "nao_existe.md"), "--consultas", str(tmp_path / "x")]
    assert vr.main(args) == 2
