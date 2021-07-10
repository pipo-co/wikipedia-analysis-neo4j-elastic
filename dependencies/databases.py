from typing import Optional

from repositories.elastic_repo import ElasticRepository
from repositories.neo4j_repo import Neo4jRepository

es: ElasticRepository
_es_open: bool = False

def es_instance() -> ElasticRepository:
    if not _neo_open:
        raise Exception('ElasticSearch instance not available')
    return es

def es_open(ip: str, port: int, user: Optional[str], password: Optional[str], index: str) -> None:
    global es, _es_open
    es = ElasticRepository(ip, port, user, password, index)
    _es_open = True

def es_close() -> None:
    global _es_open
    if _es_open:
        es.close()
        _es_open = False


neo: Neo4jRepository
_neo_open: bool = False

def neo_instance() -> Neo4jRepository:
    if not _neo_open:
        raise Exception('Neo instance not available')
    return neo

def neo_open(ip: str, port: int, user: Optional[str], password: Optional[str], index: str) -> None:
    global neo, _neo_open
    neo = Neo4jRepository(ip, port, user, password, index)
    _neo_open = True

def neo_close() -> None:
    global _neo_open
    if _neo_open:
        neo.close()
        _neo_open = False

def close_all() -> None:
    es_close()
    neo_close()
