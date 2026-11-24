// Constraint de unicidade para Usuario.id
CREATE CONSTRAINT usuario_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE;

// Constraint de unicidade para Postagem.id
CREATE CONSTRAINT postagem_id IF NOT EXISTS FOR (p:Postagem) REQUIRE p.id IS UNIQUE;

// Constraint de unicidade para Hashtag.tag
CREATE CONSTRAINT hashtag_tag IF NOT EXISTS FOR (h:Hashtag) REQUIRE h.tag IS UNIQUE;

// Constraint de unicidade para Comunidade.id
CREATE CONSTRAINT comunidade_id IF NOT EXISTS FOR (c:Comunidade) REQUIRE c.id IS UNIQUE;

// Importação dos nós Usuario com conversão explícita de inteiro, data e booleano
LOAD CSV WITH HEADERS FROM 'file:///usuarios.csv' AS linha
MERGE (u:Usuario {id: toInteger(linha.id)})
SET u.apelido = linha.apelido,
    u.nome = linha.nome,
    u.dataCadastro = date(linha.dataCadastro),
    u.verificado = toBoolean(linha.verificado);

// Importação dos nós Postagem com conversão explícita de inteiro e data e hora
LOAD CSV WITH HEADERS FROM 'file:///postagens.csv' AS linha
MERGE (p:Postagem {id: toInteger(linha.id)})
SET p.texto = linha.texto,
    p.dataPublicacao = datetime(linha.dataPublicacao);

// Importação dos nós Hashtag pela tag, que é a chave de negócio
LOAD CSV WITH HEADERS FROM 'file:///hashtags.csv' AS linha
MERGE (h:Hashtag {tag: linha.tag});

// Importação dos nós Comunidade com conversão explícita do identificador inteiro
LOAD CSV WITH HEADERS FROM 'file:///comunidades.csv' AS linha
MERGE (c:Comunidade {id: toInteger(linha.id)})
SET c.nome = linha.nome,
    c.tema = linha.tema;

// Importação do relacionamento SEGUE, com a data em que o usuário passou a seguir
LOAD CSV WITH HEADERS FROM 'file:///segue.csv' AS linha
MATCH (a:Usuario {id: toInteger(linha.usuarioId)})
MATCH (b:Usuario {id: toInteger(linha.seguidoId)})
MERGE (a)-[r:SEGUE]->(b)
SET r.desde = date(linha.desde);

// Importação do relacionamento PUBLICOU entre usuário e postagem
LOAD CSV WITH HEADERS FROM 'file:///publicou.csv' AS linha
MATCH (u:Usuario {id: toInteger(linha.usuarioId)})
MATCH (p:Postagem {id: toInteger(linha.postagemId)})
MERGE (u)-[:PUBLICOU]->(p);

// Importação do relacionamento CURTIU, com chave de idempotência por par usuário e postagem
LOAD CSV WITH HEADERS FROM 'file:///curtiu.csv' AS linha
MATCH (u:Usuario {id: toInteger(linha.usuarioId)})
MATCH (p:Postagem {id: toInteger(linha.postagemId)})
MERGE (u)-[r:CURTIU]->(p)
SET r.em = datetime(linha.em);

// Importação do relacionamento COMENTOU, com chave de idempotência por usuário, postagem e instante do comentário
LOAD CSV WITH HEADERS FROM 'file:///comentou.csv' AS linha
MATCH (u:Usuario {id: toInteger(linha.usuarioId)})
MATCH (p:Postagem {id: toInteger(linha.postagemId)})
MERGE (u)-[r:COMENTOU {em: datetime(linha.em)}]->(p)
SET r.texto = linha.texto;

// Importação do relacionamento USA_HASHTAG entre postagem e hashtag
LOAD CSV WITH HEADERS FROM 'file:///usa_hashtag.csv' AS linha
MATCH (p:Postagem {id: toInteger(linha.postagemId)})
MATCH (h:Hashtag {tag: linha.tag})
MERGE (p)-[:USA_HASHTAG]->(h);

// Importação do relacionamento PARTICIPA_DE, com o papel do usuário na comunidade
LOAD CSV WITH HEADERS FROM 'file:///participa_de.csv' AS linha
MATCH (u:Usuario {id: toInteger(linha.usuarioId)})
MATCH (c:Comunidade {id: toInteger(linha.comunidadeId)})
MERGE (u)-[r:PARTICIPA_DE]->(c)
SET r.papel = linha.papel;
