from typing import List
from models import ArticleNode
from dependencies.databases import neo_instance, es_instance
from repositories.neo4j_repo import mapper

def strict_search_query(center: str, string: str, leaps: int) -> List[ArticleNode]:
    es = es_instance()
    neo = neo_instance()
    
    articles = es.strict_search_query(string, leaps)
    results: List[ArticleNode] = []
    for h in articles:
        if h.title != center:
            record = neo.radius_search(center, h.title, leaps)
            if record != None:
                results.append(mapper(record[0]))
    
    return results