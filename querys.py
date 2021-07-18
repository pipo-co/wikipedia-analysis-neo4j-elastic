from typing import List

import dependencies
from dependencies.settings import settings
from models import ArticleNode, ArticleQuery, ElasticTextSearchFilter, IdsFilter, NeoLinksFilter
from dependencies.databases import neo_instance, es_instance
from repositories.neo4j_repo import Neo4jDistanceFilter, mapper


def process_query(query: ArticleQuery):
    es = es_instance()
    neo = neo_instance()

    neoBuilder = neo.buildQuery()

    if query.elastic_filter is not None:
        ids = list(es.search(query.elastic_filter))
        neoBuilder = neoBuilder.generalFilter(IdsFilter(ids=ids))

    if query.neo_filter is not None:
        for filter in query.neo_filter:
            if type(filter) is Neo4jDistanceFilter:
                neoBuilder = neoBuilder.distanceFilter(filter)
            elif type(filter) is NeoLinksFilter:
                pass

    if query.general_filters is not None:
        for filter in query.general_filters:
            neoBuilder = neoBuilder.generalFilter(filter)

    neoBuilder = neoBuilder.returnType(query.return_type)
    neoQuery = neoBuilder.build()
    return neo.executeQuery(neoQuery)

    
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
    
    results.append(mapper(neo.get_connections(center)[0]))
    
    return results