from typing import List, Optional, Dict

from elasticsearch_dsl.query import Q

import dependencies
from dependencies.settings import settings
from models import ArticleNode, ArticleQuery, ElasticTextSearchFilter, IdsFilter, NeoDistanceFilter, NeoLinksFilter, \
    QueryReturnTypes, SearchResponse
from dependencies.databases import neo_instance, es_instance
from repositories.neo4j_repo import Neo4jDistanceFilterBuilder, mapper


async def process_query(query: ArticleQuery) -> SearchResponse:
    es = es_instance()
    neo = neo_instance()

    neoBuilder = neo.buildQuery()

    id_content_map: Optional[Dict[int, str]] = None

    if query.elastic_filter is not None or query.return_type == QueryReturnTypes.NODE_WITH_CONTENT:
        ids: List[int]

        if query.elastic_filter is None:
            query.elastic_filter = []

        # With or without content from elastic
        if query.return_type == QueryReturnTypes.NODE_WITH_CONTENT:
            id_content_map = {}
            for (id, content) in es.search(query.elastic_filter, True):
                id_content_map[id] = content
            ids = list(id_content_map.keys())
        else:
            ids = list(es.search(query.elastic_filter, False))

        neoBuilder = neoBuilder.generalFilter(IdsFilter(ids=ids))

    if query.neo_filter is not None:
        for filter in query.neo_filter:
            if type(filter) is NeoDistanceFilter:
                neoBuilder = neoBuilder.distanceFilter(filter)
            elif type(filter) is NeoLinksFilter:
                neoBuilder = neoBuilder.linksFilter(filter)

    if query.general_filters is not None:
        for filter in query.general_filters:
            neoBuilder = neoBuilder.generalFilter(filter)

    if query.sort is not None:
        neoBuilder = neoBuilder.sortBy(query.sort)

    if query.return_type == QueryReturnTypes.NODE_WITH_CONTENT:
        neoBuilder = neoBuilder.returnType(QueryReturnTypes.NODE)
    else:
        neoBuilder = neoBuilder.returnType(query.return_type)

    if query.offset is not None:
        neoBuilder = neoBuilder.skip(query.offset)

    if query.limit is not None:
        neoBuilder = neoBuilder.limit(query.limit)
    
    results = neo.executeQuery(neoBuilder)

    # Agrego el content si aplica
    if query.return_type == QueryReturnTypes.NODE_WITH_CONTENT:
        if id_content_map is None:
            raise AssertionError('id_content_map must not be None')

        for node in results:
            node.content = id_content_map[node.id]

    return SearchResponse(result=results)

    
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