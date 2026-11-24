// Quem são os 10 usuários mais seguidos da rede?
MATCH (seguidor:Usuario)-[:SEGUE]->(u:Usuario)
RETURN u.id AS id, u.apelido AS apelido, count(seguidor) AS seguidores
ORDER BY seguidores DESC, id ASC
LIMIT 10;

// Quais usuários seguidos pelas pessoas que o usuário 10 segue ele ainda não segue?
MATCH (eu:Usuario {id: 10})-[:SEGUE]->(:Usuario)-[:SEGUE]->(sugestao:Usuario)
WHERE sugestao <> eu
  AND NOT (eu)-[:SEGUE]->(sugestao)
RETURN sugestao.id AS id, sugestao.apelido AS apelido, count(*) AS caminhosEmComum
ORDER BY caminhosEmComum DESC, id ASC
LIMIT 10;

// Qual é o menor caminho de seguidores entre o usuário 10 e o usuário 150?
MATCH (origem:Usuario {id: 10}), (destino:Usuario {id: 150})
MATCH caminho = shortestPath((origem)-[:SEGUE*..8]-(destino))
RETURN [n IN nodes(caminho) | n.apelido] AS apelidosNoCaminho, length(caminho) AS saltos;

// Quais hashtags aparecem mais nas 10 postagens mais curtidas?
MATCH (p:Postagem)<-[c:CURTIU]-(:Usuario)
WITH p, count(c) AS curtidas
ORDER BY curtidas DESC, p.id ASC
LIMIT 10
MATCH (p)-[:USA_HASHTAG]->(h:Hashtag)
RETURN h.tag AS hashtag, count(DISTINCT p) AS postagens, sum(curtidas) AS curtidasAcumuladas
ORDER BY postagens DESC, curtidasAcumuladas DESC, hashtag ASC
LIMIT 10;

// Quais comunidades concentram mais usuários verificados?
MATCH (u:Usuario {verificado: true})-[:PARTICIPA_DE]->(c:Comunidade)
RETURN c.id AS id, c.nome AS comunidade, count(DISTINCT u) AS verificados
ORDER BY verificados DESC, id ASC
LIMIT 10;

// Quais usuários influenciam, em até 2 saltos, pessoas de comunidades diferentes da sua?
MATCH (a:Usuario)-[:PARTICIPA_DE]->(ca:Comunidade)
MATCH (a)-[:SEGUE*1..2]->(b:Usuario)-[:PARTICIPA_DE]->(cb:Comunidade)
WHERE a <> b
  AND ca <> cb
  AND NOT (a)-[:PARTICIPA_DE]->(cb)
RETURN a.id AS id, a.apelido AS apelido,
       count(DISTINCT b) AS influenciados,
       count(DISTINCT cb) AS comunidadesAlcancadas
ORDER BY comunidadesAlcancadas DESC, influenciados DESC, id ASC
LIMIT 10;
