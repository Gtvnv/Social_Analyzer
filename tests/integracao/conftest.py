"""Fixtures de integração: sobem o Neo4j via Docker Compose em porta alternativa.

Se o Docker (CLI ou daemon) não estiver disponível, ou se o Neo4j não ficar
pronto no prazo, os testes marcados são pulados.
"""
import csv
import io
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CYPHER = RAIZ / "cypher"
DATA = RAIZ / "data"

HTTP_PORT = "17474"
BOLT_PORT = "17687"
SENHA = "senha-de-teste-integracao"
PRAZO_PRONTO_S = 180


def pytest_collection_modifyitems(items):
    """Garante o marker `integracao` em todo teste deste diretório."""
    for item in items:
        if Path(str(item.fspath)).parent == Path(__file__).parent:
            item.add_marker(pytest.mark.integracao)


def _docker_disponivel() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=20, check=False
        )
        if r.returncode != 0:
            return False
        r = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            timeout=20,
            check=False,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class Neo4jCompose:
    """Executa comandos do compose e do cypher-shell no ambiente temporário."""

    def __init__(self, env_file: Path, projeto: str):
        self.base = [
            "docker", "compose",
            "--project-directory", str(RAIZ),
            "-f", str(RAIZ / "docker-compose.yml"),
            "--env-file", str(env_file),
            "-p", projeto,
        ]
        self.env = {
            **os.environ,
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": SENHA,
            "NEO4J_HTTP_PORT": HTTP_PORT,
            "NEO4J_BOLT_PORT": BOLT_PORT,
        }

    def executar(self, args, entrada: str | None = None, timeout=120):
        return subprocess.run(
            self.base + args,
            input=entrada,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=self.env,
            check=False,
        )

    def cypher(self, texto: str, timeout=120) -> subprocess.CompletedProcess:
        """Roda cypher-shell lendo o texto da entrada padrão (`< arquivo`)."""
        return self.executar(
            ["exec", "-T", "neo4j", "cypher-shell",
             "-u", "neo4j", "-p", SENHA, "--format", "plain"],
            entrada=texto,
            timeout=timeout,
        )

    def cypher_arquivo(self, caminho: Path, timeout=300):
        return self.cypher(caminho.read_text(encoding="utf-8"), timeout=timeout)


@pytest.fixture(scope="session")
def neo4j(tmp_path_factory):
    if not _docker_disponivel():
        pytest.skip("Docker/daemon indisponível: testes de integração ignorados")

    env_file = tmp_path_factory.mktemp("env") / ".env"
    env_file.write_text(
        f"NEO4J_USER=neo4j\nNEO4J_PASSWORD={SENHA}\n"
        f"NEO4J_HTTP_PORT={HTTP_PORT}\nNEO4J_BOLT_PORT={BOLT_PORT}\n",
        encoding="utf-8",
    )
    ambiente = Neo4jCompose(env_file, f"sa-integ-{uuid.uuid4().hex[:8]}")

    try:
        subir = ambiente.executar(["up", "-d"], timeout=600)
        if subir.returncode != 0:
            pytest.skip(f"Não foi possível subir o Neo4j: {subir.stderr.strip()[:300]}")

        limite = time.monotonic() + PRAZO_PRONTO_S
        pronto = False
        while time.monotonic() < limite:
            try:
                r = ambiente.cypher("RETURN 1;", timeout=30)
            except subprocess.TimeoutExpired:
                r = None
            if r is not None and r.returncode == 0:
                pronto = True
                break
            time.sleep(3)
        if not pronto:
            pytest.skip("Neo4j não ficou disponível no prazo: testes ignorados")

        yield ambiente
    finally:
        try:
            ambiente.executar(["down", "-v"], timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            pass


def ler_csv(nome: str) -> list[dict]:
    with (DATA / nome).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def contagens_esperadas() -> dict[str, int]:
    """Deriva as contagens esperadas (após MERGE) dos CSVs em data/."""
    def distintos(nome, *chaves):
        return len({tuple(l[c] for c in chaves) for l in ler_csv(nome)})

    return {
        "Usuario": distintos("usuarios.csv", "id"),
        "Postagem": distintos("postagens.csv", "id"),
        "Hashtag": distintos("hashtags.csv", "tag"),
        "Comunidade": distintos("comunidades.csv", "id"),
        "SEGUE": distintos("segue.csv", "usuarioId", "seguidoId"),
        "PUBLICOU": distintos("publicou.csv", "usuarioId", "postagemId"),
        "CURTIU": distintos("curtiu.csv", "usuarioId", "postagemId"),
        "COMENTOU": distintos("comentou.csv", "usuarioId", "postagemId", "em"),
        "USA_HASHTAG": distintos("usa_hashtag.csv", "postagemId", "tag"),
        "PARTICIPA_DE": distintos("participa_de.csv", "usuarioId", "comunidadeId"),
    }


def linhas_plain(saida: str) -> list[list[str]]:
    """Converte a saída `--format plain` em linhas de dados (sem o cabeçalho)."""
    linhas = [l for l in saida.splitlines() if l.strip()]
    if not linhas:
        return []
    leitor = csv.reader(io.StringIO("\n".join(linhas)), skipinitialspace=True)
    return list(leitor)[1:]


def dividir_consultas(texto: str) -> list[str]:
    """Separa um arquivo .cypher em instruções, descartando comentários."""
    sem_comentarios = "\n".join(
        l for l in texto.splitlines() if not l.lstrip().startswith("//")
    )
    return [p.strip() for p in re.split(r";\s*(?:\n|$)", sem_comentarios) if p.strip()]
