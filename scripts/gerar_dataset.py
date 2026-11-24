"""Gerador determinístico do dataset sintético do Social Analyzer.

Todos os dados são sintéticos: apelidos e nomes vêm da combinação de listas
fixas e os textos vêm de modelos de frase. Nenhum e-mail, telefone ou
documento é gerado.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

SEMENTE_PADRAO = 42

QTD_USUARIOS = 200
QTD_POSTAGENS = 400
QTD_COMUNIDADES = 12

QTD_SEGUE = 800
QTD_CURTIU = 500
QTD_COMENTOU = 150
QTD_USA_HASHTAG = 500
QTD_PARTICIPA_EXTRA = 60

PERCENTUAL_VERIFICADOS = 0.10

# Colunas de cada arquivo, na ordem do dicionário de dados do design.
COLUNAS: dict[str, tuple[str, ...]] = {
    "usuarios": ("id", "apelido", "nome", "dataCadastro", "verificado"),
    "postagens": ("id", "texto", "dataPublicacao"),
    "hashtags": ("tag",),
    "comunidades": ("id", "nome", "tema"),
    "segue": ("usuarioId", "seguidoId", "desde"),
    "publicou": ("usuarioId", "postagemId"),
    "curtiu": ("usuarioId", "postagemId", "em"),
    "comentou": ("usuarioId", "postagemId", "texto", "em"),
    "usa_hashtag": ("postagemId", "tag"),
    "participa_de": ("usuarioId", "comunidadeId", "papel"),
}

NOS = ("usuarios", "postagens", "hashtags", "comunidades")
RELACIONAMENTOS = ("segue", "publicou", "curtiu", "comentou", "usa_hashtag", "participa_de")

_ADJETIVOS = (
    "alegre", "bravo", "calmo", "curioso", "veloz", "sereno", "criativo", "audaz",
    "gentil", "esperto", "atento", "livre", "noturno", "solar", "urbano", "nomade",
)
_SUBSTANTIVOS = (
    "falcao", "lobo", "coruja", "tigre", "golfinho", "panda", "raposa", "jaguar",
    "arara", "tucano", "lince", "cervo", "puma", "foca", "garca", "onca",
)
_PRIMEIROS_NOMES = (
    "Ana", "Bruno", "Carla", "Daniel", "Elisa", "Felipe", "Gabriela", "Henrique",
    "Isabela", "João", "Karina", "Lucas", "Marina", "Nelson", "Olívia", "Paulo",
    "Quézia", "Rafael", "Sofia", "Tiago", "Úrsula", "Vitor", "Wanda", "Yara",
)
_SOBRENOMES = (
    "Almeida", "Barros", "Cardoso", "Duarte", "Esteves", "Farias", "Guedes",
    "Holanda", "Ibrahim", "Junqueira", "Lacerda", "Menezes", "Nogueira",
    "Oliveira", "Pacheco", "Queiroz", "Ramos", "Siqueira", "Tavares", "Vasconcelos",
)
_HASHTAGS = (
    "tecnologia", "grafos", "neo4j", "dados", "python", "viagem", "culinaria",
    "musica", "cinema", "livros", "esporte", "futebol", "corrida", "yoga",
    "fotografia", "arte", "games", "ciencia", "saude", "educacao",
    "carreira", "startups", "design", "moda", "pets", "natureza", "cafe",
    "humor", "politica", "economia", "meioambiente", "historia", "teatro",
    "podcast", "diy", "jardinagem", "ciclismo", "series", "quadrinhos", "inovacao",
)
_TEMAS = (
    "Tecnologia", "Esportes", "Culinária", "Música", "Cinema", "Viagens",
    "Ciência", "Arte", "Saúde", "Educação", "Negócios", "Natureza",
)
_PAPEIS_COMUM = ("membro", "membro", "membro", "moderador")
_MODELOS_POSTAGEM = (
    "Acabei de descobrir algo novo sobre {a} e quero compartilhar",
    "Alguém mais acompanha as novidades de {a} e {b}",
    "Começando o dia com {a} e muita disposição",
    "Dica rápida de {a} para quem está começando",
    "Hoje o assunto é {a} e como isso se conecta com {b}",
    "Depois de semanas estudando {a}, finalmente deu certo",
    "Qual a melhor forma de aprender {a}",
    "Recomendo muito juntar {a} com {b} no fim de semana",
)
_MODELOS_COMENTARIO = (
    "Muito bom, obrigado por compartilhar",
    "Concordo totalmente com esse ponto",
    "Ótima dica, vou testar hoje mesmo",
    "Interessante, não tinha pensado nisso",
    "Boa! Acompanho o assunto há tempos",
    "Faz sentido, valeu pela explicação",
    "Gostei bastante dessa ideia",
    "Excelente contribuição para a conversa",
)

_DATA_BASE_CADASTRO = datetime(2022, 1, 1)
_DATA_BASE_POSTAGEM = datetime(2024, 1, 1)


@dataclass(frozen=True)
class Dataset:
    nos: dict[str, list[dict]]
    relacionamentos: dict[str, list[dict]]


def _data(base: datetime, dias: int) -> str:
    return (base + timedelta(days=dias)).strftime("%Y-%m-%d")


def _data_hora(base: datetime, segundos: int) -> str:
    return (base + timedelta(seconds=segundos)).strftime("%Y-%m-%dT%H:%M:%S")


def _pares_unicos(
    rng: random.Random,
    quantidade: int,
    sorteio,
    iniciais: list[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    """Sorteia `quantidade` pares distintos; `sorteio(rng)` devolve um par."""
    pares: set[tuple[int, int]] = set(iniciais or [])
    while len(pares) < quantidade:
        pares.add(sorteio(rng))
    return sorted(pares)


def gerar(semente: int = SEMENTE_PADRAO) -> Dataset:
    """Gera o dataset de forma determinística a partir da semente."""
    rng = random.Random(semente)
    ids_usuarios = list(range(1, QTD_USUARIOS + 1))
    ids_postagens = list(range(1, QTD_POSTAGENS + 1))
    ids_comunidades = list(range(1, QTD_COMUNIDADES + 1))

    # Comunidades
    comunidades = [
        {
            "id": cid,
            "nome": f"Comunidade {_TEMAS[(cid - 1) % len(_TEMAS)]}",
            "tema": _TEMAS[(cid - 1) % len(_TEMAS)],
        }
        for cid in ids_comunidades
    ]

    # Usuários: os primeiros usuários de cada comunidade são verificados, o que
    # garante ao menos um verificado por comunidade.
    usuarios = []
    for uid in ids_usuarios:
        adjetivo = rng.choice(_ADJETIVOS)
        substantivo = rng.choice(_SUBSTANTIVOS)
        nome = f"{rng.choice(_PRIMEIROS_NOMES)} {rng.choice(_SOBRENOMES)}"
        verificado = uid <= QTD_COMUNIDADES or rng.random() < PERCENTUAL_VERIFICADOS
        usuarios.append(
            {
                "id": uid,
                "apelido": f"{adjetivo}_{substantivo}_{uid}",
                "nome": nome,
                "dataCadastro": _data(_DATA_BASE_CADASTRO, rng.randrange(0, 730)),
                "verificado": "true" if verificado else "false",
            }
        )

    # Hashtags
    hashtags = [{"tag": tag} for tag in sorted(_HASHTAGS)]
    tags = [h["tag"] for h in hashtags]

    # Postagens, cada uma com um único autor
    postagens = []
    publicou = []
    segundos_postagem: dict[int, int] = {}
    for pid in ids_postagens:
        segundos = rng.randrange(0, 365 * 24 * 3600)
        segundos_postagem[pid] = segundos
        tema_a, tema_b = rng.sample(tags, 2)
        texto = rng.choice(_MODELOS_POSTAGEM).format(a=tema_a, b=tema_b)
        postagens.append(
            {
                "id": pid,
                "texto": texto,
                "dataPublicacao": _data_hora(_DATA_BASE_POSTAGEM, segundos),
            }
        )
        publicou.append({"usuarioId": rng.choice(ids_usuarios), "postagemId": pid})

    # SEGUE: alvos populares seguem uma distribuição enviesada. O usuário 1
    # recebe e faz seguidas explícitas para ter resultados nas consultas.
    pesos_usuarios = [1.0 / (i + 1) ** 0.7 for i in range(QTD_USUARIOS)]
    iniciais = [(1, alvo) for alvo in range(2, 8)] + [(origem, 1) for origem in range(8, 14)]

    def sorteio_segue(r: random.Random) -> tuple[int, int]:
        origem = r.choice(ids_usuarios)
        destino = r.choices(ids_usuarios, weights=pesos_usuarios)[0]
        return (origem, destino if destino != origem else origem % QTD_USUARIOS + 1)

    pares_segue = _pares_unicos(rng, QTD_SEGUE, sorteio_segue, iniciais)
    segue = [
        {
            "usuarioId": a,
            "seguidoId": b,
            "desde": _data(_DATA_BASE_CADASTRO, rng.randrange(730, 1100)),
        }
        for a, b in pares_segue
    ]

    # CURTIU: postagens populares recebem mais curtidas
    pesos_postagens = [1.0 / (i + 1) ** 0.5 for i in range(QTD_POSTAGENS)]

    def sorteio_post(r: random.Random) -> tuple[int, int]:
        return (r.choice(ids_usuarios), r.choices(ids_postagens, weights=pesos_postagens)[0])

    pares_curtiu = _pares_unicos(rng, QTD_CURTIU, sorteio_post)
    curtiu = [
        {
            "usuarioId": u,
            "postagemId": p,
            "em": _data_hora(_DATA_BASE_POSTAGEM, segundos_postagem[p] + rng.randrange(60, 7 * 86400)),
        }
        for u, p in pares_curtiu
    ]

    # COMENTOU
    pares_comentou = _pares_unicos(
        rng, QTD_COMENTOU, lambda r: (r.choice(ids_usuarios), r.choice(ids_postagens))
    )
    comentou = [
        {
            "usuarioId": u,
            "postagemId": p,
            "texto": rng.choice(_MODELOS_COMENTARIO),
            "em": _data_hora(_DATA_BASE_POSTAGEM, segundos_postagem[p] + rng.randrange(60, 7 * 86400)),
        }
        for u, p in pares_comentou
    ]

    # USA_HASHTAG: toda postagem tem ao menos uma hashtag
    pares_hashtag: set[tuple[int, str]] = {(pid, rng.choice(tags)) for pid in ids_postagens}
    while len(pares_hashtag) < QTD_USA_HASHTAG:
        pares_hashtag.add((rng.choice(ids_postagens), rng.choice(tags)))
    usa_hashtag = [{"postagemId": p, "tag": t} for p, t in sorted(pares_hashtag)]

    # PARTICIPA_DE: cada usuário tem uma comunidade principal; há participações extras
    pares_participa: dict[tuple[int, int], str] = {}
    for uid in ids_usuarios:
        cid = (uid - 1) % QTD_COMUNIDADES + 1
        papel = "administrador" if uid <= QTD_COMUNIDADES else rng.choice(_PAPEIS_COMUM)
        pares_participa[(uid, cid)] = papel
    while len(pares_participa) < QTD_USUARIOS + QTD_PARTICIPA_EXTRA:
        chave = (rng.choice(ids_usuarios), rng.choice(ids_comunidades))
        if chave not in pares_participa:
            pares_participa[chave] = rng.choice(_PAPEIS_COMUM)
    participa_de = [
        {"usuarioId": u, "comunidadeId": c, "papel": papel}
        for (u, c), papel in sorted(pares_participa.items())
    ]

    publicou.sort(key=lambda r: (r["usuarioId"], r["postagemId"]))

    return Dataset(
        nos={
            "usuarios": usuarios,
            "postagens": postagens,
            "hashtags": hashtags,
            "comunidades": comunidades,
        },
        relacionamentos={
            "segue": segue,
            "publicou": publicou,
            "curtiu": curtiu,
            "comentou": comentou,
            "usa_hashtag": usa_hashtag,
            "participa_de": participa_de,
        },
    )


def serializar(ds: Dataset) -> dict[str, bytes]:
    """Serializa o dataset: nome do arquivo -> bytes UTF-8, vírgula e `\\n`."""
    arquivos: dict[str, bytes] = {}
    for nome, linhas in {**ds.nos, **ds.relacionamentos}.items():
        colunas = COLUNAS[nome]
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=",", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        escritor.writerow(colunas)
        for linha in linhas:
            escritor.writerow([linha[c] for c in colunas])
        arquivos[f"{nome}.csv"] = saida.getvalue().encode("utf-8")
    return arquivos


# Chave de identificação de cada tipo de nó.
_CHAVE_NO = {
    "usuarios": "id",
    "postagens": "id",
    "hashtags": "tag",
    "comunidades": "id",
}

# Para cada relacionamento: (coluna, nó referenciado).
_REFERENCIAS: dict[str, tuple[tuple[str, str], ...]] = {
    "segue": (("usuarioId", "usuarios"), ("seguidoId", "usuarios")),
    "publicou": (("usuarioId", "usuarios"), ("postagemId", "postagens")),
    "curtiu": (("usuarioId", "usuarios"), ("postagemId", "postagens")),
    "comentou": (("usuarioId", "usuarios"), ("postagemId", "postagens")),
    "usa_hashtag": (("postagemId", "postagens"), ("tag", "hashtags")),
    "participa_de": (("usuarioId", "usuarios"), ("comunidadeId", "comunidades")),
}


@dataclass(frozen=True)
class ErroIntegridade:
    arquivo: str
    identificador: str
    motivo: str = ""

    def __str__(self) -> str:
        texto = f"{self.arquivo}: identificador '{self.identificador}'"
        return f"{texto} ({self.motivo})" if self.motivo else texto


class ErroValidacao(Exception):
    """Dataset com problemas de integridade; `erros` lista cada ocorrência."""

    def __init__(self, erros: list[ErroIntegridade]):
        self.erros = erros
        super().__init__("; ".join(str(e) for e in erros))


def validar(ds: Dataset) -> list[ErroIntegridade]:
    """Retorna os erros de integridade: ids duplicados e referências inexistentes."""
    erros: list[ErroIntegridade] = []
    conhecidos: dict[str, set[str]] = {}

    for no, chave in _CHAVE_NO.items():
        vistos: set[str] = set()
        for linha in ds.nos.get(no, []):
            ident = str(linha[chave])
            if ident in vistos:
                erros.append(ErroIntegridade(f"{no}.csv", ident, "identificador duplicado"))
            vistos.add(ident)
        conhecidos[no] = vistos

    for rel, referencias in _REFERENCIAS.items():
        for linha in ds.relacionamentos.get(rel, []):
            for coluna, no in referencias:
                ident = str(linha[coluna])
                if ident not in conhecidos[no]:
                    erros.append(
                        ErroIntegridade(
                            f"{rel}.csv", ident, f"{coluna} referencia {no} inexistente"
                        )
                    )
    return erros


def gravar(ds: Dataset, destino: str | os.PathLike) -> list[Path]:
    """Valida e grava os CSVs em `destino` de forma atômica.

    Os arquivos são escritos primeiro em um diretório temporário no mesmo pai
    do destino e só então movidos para ele. Em qualquer falha, o destino volta
    ao estado anterior (sem CSV parcial). Outros arquivos do destino (como
    `.gitkeep`) são preservados.
    """
    erros = validar(ds)
    if erros:
        raise ErroValidacao(erros)

    arquivos = serializar(ds)
    destino = Path(destino).resolve()
    pai = destino.parent
    pai.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix=f".{destino.name}.tmp-", dir=pai))
    try:
        novos = tmp / "novos"
        backup = tmp / "backup"
        novos.mkdir()
        backup.mkdir()
        for nome, conteudo in arquivos.items():
            with open(novos / nome, "wb") as f:
                f.write(conteudo)
                f.flush()
                os.fsync(f.fileno())

        destino.mkdir(exist_ok=True)
        movidos: list[str] = []
        substituidos: list[str] = []
        try:
            for nome in arquivos:
                alvo = destino / nome
                if alvo.exists():
                    os.replace(alvo, backup / nome)
                    substituidos.append(nome)
                os.replace(novos / nome, alvo)
                movidos.append(nome)
        except BaseException:
            for nome in movidos:
                try:
                    (destino / nome).unlink()
                except FileNotFoundError:
                    pass
            for nome in substituidos:
                if (backup / nome).exists():
                    os.replace(backup / nome, destino / nome)
            raise
        return [destino / nome for nome in arquivos]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _caminho_padrao_saida() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o dataset sintético em CSV.")
    parser.add_argument("--semente", type=int, default=SEMENTE_PADRAO, help="semente (padrão: 42)")
    parser.add_argument(
        "--saida",
        default=None,
        help="diretório de saída (padrão: data/ na raiz do projeto)",
    )
    args = parser.parse_args(argv)
    saida = Path(args.saida) if args.saida else _caminho_padrao_saida()

    try:
        gravar(gerar(args.semente), saida)
    except ErroValidacao as exc:
        for erro in exc.erros:
            print(f"Erro de integridade em {erro}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Erro ao gravar em {saida}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
