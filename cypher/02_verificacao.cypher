// Consulta de verificação pós-carga (somente leitura).
// Retorna uma linha por label de nó (Usuario, Postagem, Hashtag, Comunidade)
// e uma linha por tipo de relacionamento (SEGUE, PUBLICOU, CURTIU, COMENTOU,
// USA_HASHTAG, PARTICIPA_DE), com a respectiva contagem. Os valores devem ser
// iguais após reexecutar a carga, o que confirma a idempotência.
MATCH (n:Usuario) RETURN 'Usuario' AS elemento, 'nó' AS natureza, count(n) AS total
UNION ALL
MATCH (n:Postagem) RETURN 'Postagem' AS elemento, 'nó' AS natureza, count(n) AS total
UNION ALL
MATCH (n:Hashtag) RETURN 'Hashtag' AS elemento, 'nó' AS natureza, count(n) AS total
UNION ALL
MATCH (n:Comunidade) RETURN 'Comunidade' AS elemento, 'nó' AS natureza, count(n) AS total
UNION ALL
MATCH ()-[r:SEGUE]->() RETURN 'SEGUE' AS elemento, 'relacionamento' AS natureza, count(r) AS total
UNION ALL
MATCH ()-[r:PUBLICOU]->() RETURN 'PUBLICOU' AS elemento, 'relacionamento' AS natureza, count(r) AS total
UNION ALL
MATCH ()-[r:CURTIU]->() RETURN 'CURTIU' AS elemento, 'relacionamento' AS natureza, count(r) AS total
UNION ALL
MATCH ()-[r:COMENTOU]->() RETURN 'COMENTOU' AS elemento, 'relacionamento' AS natureza, count(r) AS total
UNION ALL
MATCH ()-[r:USA_HASHTAG]->() RETURN 'USA_HASHTAG' AS elemento, 'relacionamento' AS natureza, count(r) AS total
UNION ALL
MATCH ()-[r:PARTICIPA_DE]->() RETURN 'PARTICIPA_DE' AS elemento, 'relacionamento' AS natureza, count(r) AS total;
