from typing import List

import dependencies
from dependencies.settings import settings
from models import ArticleNode, ArticleQuery, ElasticTextSearchFilter
from dependencies.databases import neo_instance, es_instance
from repositories.neo4j_repo import mapper


def process_query(query: ArticleQuery):
    es = es_instance()

    return list(es.search(query.elastic_filter))

def strict_search_query(center: str, string: str, leaps: int) -> List[ArticleNode]:
    es = es_instance()
    neo = neo_instance()
    
    articles = es.strict_search_query(string)
    results: List[ArticleNode] = []
    for h in articles:
        if h.title != center:
            record = neo.radius_search(center, h.title, leaps)
            if record is not None:
                results.append(mapper(record[0]))
    
    return results