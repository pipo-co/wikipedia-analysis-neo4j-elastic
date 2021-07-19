from abc import ABCMeta, abstractmethod
from dataclasses import field
import itertools

from neo4j.work import result
from neo4j.work.transaction import Transaction
from models import ArticleNode, CategoriesFilter, DistanceFilterStrategy, GeneralFilter, IdsFilter, NeoDistanceFilter, NeoLinksFilter, QueryReturnTypes, QuerySort, SortByEnum, TitlesFilter
from typing import Any, List, Optional, Tuple, final

import neo4j
from neo4j import GraphDatabase, Session, Result, ResultSummary
from neo4j.data import Record
from neo4j.exceptions import ClientError

_INDEX_ALREADY_EXISTS_CODE: str = 'Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists'

class Neo4jRepository:

    @staticmethod
    def _create_id_constraint(tx) -> None:
        id_result: Result = tx.run('CREATE CONSTRAINT article_unique_id ON (a:Article) ASSERT a.article_id IS UNIQUE')
        id_result.consume()

    @staticmethod
    def _create_name_constraint(tx) -> None:
        name_result: Result = tx.run('CREATE CONSTRAINT article_unique_title ON (a:Article) ASSERT a.title IS UNIQUE')
        name_result.consume()

    def __init__(self, ip: str, port: int, user: Optional[str], password: Optional[str], database: Optional[str] = None) -> None:
        auth: Optional[Tuple[str, str]] = (user, password) if user and password else None

        self.driver = GraphDatabase.driver(f"neo4j://{ip}:{port}", auth=auth)
        self.db = database if database else neo4j.DEFAULT_DATABASE

        with self.session() as session:
            # Recien en Neo4j 4.3.1 introdujeron IF NOT EXISTS. Por ahora atrapamos la excepcion cuando la constraint ya existe

            # id constraint
            try:
                session.write_transaction(self._create_id_constraint)
            except ClientError as e:
                if e.code != _INDEX_ALREADY_EXISTS_CODE:
                    raise e

            # name constraint
            try:
                session.write_transaction(self._create_name_constraint)
            except ClientError as e:
                if e.code != _INDEX_ALREADY_EXISTS_CODE:
                    raise e

    def session(self) -> Session:
        return self.driver.session(database=self.db)

    def close(self):
        self.driver.close()

    def truncate_db(self, session: Optional[Session] = None):
        if session:
            return session.write_transaction(self._truncate_db)
        else:
            with self.session() as session:
                return session.write_transaction(self._truncate_db)

    @staticmethod
    def _truncate_db(tx) -> None:
        name_result: Result = tx.run('MATCH (n)-[r]-() DELETE n, r')
        name_result.consume()

    def create_article(self, id: int, title: str, categories: List[str], session: Optional[Session] = None) -> bool:
        """
        Parameters:
        id - Wikipedia's article id.
        title - Wikipedia's article title.
        categories - List of the categories the article is in
        """
        if session:
            return session.write_transaction(self._create_article_node, id, title, categories)
        else:
            with self.session() as session:
                return session.write_transaction(self._create_article_node, id, title, categories)

    @staticmethod
    def _create_article_node(tx, id: int, title: str, categories: List[str]) -> bool:
        result: Result = tx.run(
            "MERGE (a:Article {article_id: $id, title: $title, categories: $categories})",
            id=id, title=title, categories=categories
        )

        return result.consume().counters.nodes_created == 1

    def create_and_link_article(self, source_id: int, dest_id: int, dest_title: str, dest_categories: List[str], session: Optional[Session] = None) -> bool:
        """
        Parameters:
        id - Wikipedia's article id.
        title - Wikipedia's article title.
        categories - List of the categories the article is in
        """
        if session:
            return session.write_transaction(self._create_and_link_article, source_id, dest_id, dest_title, dest_categories)
        else:
            with self.session() as session:
                return session.write_transaction(self._create_and_link_article, source_id, dest_id, dest_title, dest_categories)

    @staticmethod
    def _create_and_link_article(tx, source_id: int, dest_id: int, dest_title: str, dest_categories: List[str]) -> bool:
        result: Result = tx.run(
            'MATCH (n:Article {article_id: $source_id}) '
            'MERGE (v:Article {article_id: $dest_id, title: $dest_title, categories: $dest_categories}) '
            'MERGE (n)-[r:Link]->(v)',
            source_id=source_id, dest_id=dest_id, dest_title=dest_title, dest_categories=dest_categories
        )
        summary: ResultSummary = result.consume()

        if summary.counters.relationships_created == 0:
            print(f'Relationship from node {source_id} to node {dest_id} wasn\'t created. Summary counters: {repr(summary.counters)}')

        return summary.counters.nodes_created == 1

    def link_article(self, source_id: int, dest_title: str, session: Session) -> None:
        """
        Parameters:
        id - Wikipedia's article id.
        title - Wikipedia's article title.
        categories - List of the categories the article is in
        """
        if session:
            return session.write_transaction(self._link_article, source_id, dest_title)
        else:
            with self.session() as session:
                return session.write_transaction(self._link_article, source_id, dest_title)

    @staticmethod
    def _link_article(tx, source_id: int, dest_title: str) -> None:
        result: Result = tx.run(
            'MATCH (n:Article {article_id: $source_id}) '
            'MATCH (v:Article {title: $dest_title}) '
            'MERGE (n)-[r:Link]->(v)',
            source_id=source_id, dest_title=dest_title
        )

        if result.consume().counters.relationships_created == 0:
            raise Neo4jWriteException(f'Tried to create duplicated relationship from node {source_id} to node `{dest_title}`')

    def radius_search(self, center: str, string: str, leaps: int) -> Record:
        with self.session() as session:
            return session.write_transaction(self._radius_search, center, string, leaps)
    
    @staticmethod
    def _radius_search(tx: Transaction, center: str, string: str, leaps: int) -> Record:
        result = tx.run(
            "MATCH (center:Article {title: $center_title}), (exterior:Article {title: $ext_title}), "
            "p = shortestPath((center)-[*1.."+str(leaps)+"]-(exterior)) "
            "MATCH (exterior)-[]->(m) "
            "RETURN {article_id: exterior.article_id, title: exterior.title, categories: exterior.categories, " 
            "links: collect({article_id: m.article_id, title: m.title})}",
            center_title=center, ext_title=string
        )
        return result.single()

    def buildQuery(self) -> 'Neo4jFilterBuilder':
        return Neo4jFilterBuilder()

    def executeQuery(self, query: 'Neo4jFinalBuilder') -> Result:
        with self.session() as session:
            return session.write_transaction(query.execute)

    def get_connections(self, node_title: str) -> Record:
        with self.session() as session:
            return session.write_transaction(self._get_connections, node_title)
    
    @staticmethod
    def _get_connections(tx: Transaction, node_title: str) -> Record:
        result = tx.run(
            'MATCH (n:Article {title: $title})-[r]-(m) RETURN {article_id: n.article_id, title: n.title, categories: n.categories, links: collect({article_id: m.article_id, title: m.title})}',
            title=node_title
        )
        return result.single()

def mapper(record: Record) -> ArticleNode:
    return ArticleNode(id=record['article_id'], title=record['title'], categories=record['categories'], links=record['links'])

# Custom Exceptions
class Neo4jWriteException(Exception):
    pass

Neo4jQuerySegment = Tuple[str, Optional[dict[str, Any]]]

class Neo4jQueryBuilder():
    _baseBuilder: Optional['Neo4jQueryBuilder']
    __ident = 0

    def __init__(self, base: 'Neo4jQueryBuilder' = None) -> None:
        self._baseBuilder = base

    @staticmethod
    def ident():
        x = Neo4jQueryBuilder.__ident
        Neo4jQueryBuilder.__ident += 1
        return x

    @abstractmethod
    def stringify(self) -> Neo4jQuerySegment:
        pass

    @final
    def _build(self) -> List[Neo4jQuerySegment]:
        list = self._baseBuilder._build() if self._baseBuilder is not None else []
        list.append(self.stringify())
        return list

    @final
    def build(self) -> Neo4jQuerySegment:
        query, args = map(list, zip(*self._build()))
        dic = dict(itertools.chain.from_iterable(d.items() for d in args if d is not None))
        return ('\n'.join(query), dic)

class Neo4jFilterBuilder(Neo4jQueryBuilder):
    def generalFilter(self, filter: GeneralFilter):
        return Neo4jGeneralFilterBuilder(self, filter)

    def distanceFilter(self, filter: NeoDistanceFilter):
        return Neo4jDistanceFilterBuilder(self, filter)

    def linksFilter(self, filter: NeoLinksFilter):
        return Neo4jLinksFilterBuilder(self, filter)

    def returnType(self, type: QueryReturnTypes):
        return Neo4jReturnBuilder.byType(self, type)

    def sortBy(self, sort: QuerySort):
        return Neo4jSortBuilder(self, sort)

    def stringify(self) -> Neo4jQuerySegment:
        return ('MATCH (n:Article)', None)

class Neo4jDistanceFilterBuilder(Neo4jFilterBuilder):
    filter: NeoDistanceFilter

    def __init__(self, base: Neo4jQueryBuilder, filter: NeoDistanceFilter) -> None:
        super().__init__(base)
        self.filter = filter

    def stringify(self) -> Neo4jQuerySegment:
        ident = Neo4jQueryBuilder.ident()
        if self.filter.strategy == DistanceFilterStrategy.AT_DIST:
            strategy = 'athop'
        elif self.filter.strategy == DistanceFilterStrategy.UP_TO_DIST:
            strategy = 'tohop'
        str =   f"MATCH (source: Article {{title: $title{ident}}})\n" \
                f"CALL apoc.neighbors.{strategy}(source, 'Link>', {self.filter.dist})\n" \
                "YIELD node\n" \
                "WITH collect(n.article_id) as ids, node\n" \
                "WHERE node.article_id in ids\n" \
                "WITH node as n"
        dic = {f"title{ident}": self.filter.source_node}
        return (str, dic)

class Neo4jLinksFilterBuilder(Neo4jFilterBuilder):
    filter: NeoLinksFilter

    def __init__(self, base: 'Neo4jQueryBuilder', filter: NeoLinksFilter) -> None:
        super().__init__(base)
        self.filter = filter

    def stringify(self) -> Neo4jQuerySegment:
        ident = Neo4jQueryBuilder.ident()
        hasCategories = self.filter.categories is not None
        str =   "CALL {\n" \
                "    WITH n\n" \
                "    MATCH (n)-[links:Link]->(m:Article)\n" + \
                (f"    WHERE all(cat in $categories{ident} WHERE cat in m.categories)\n" \
                    if hasCategories else "") + \
                "    RETURN count(links) as links }\n" \
                "WITH links as count, n\n"\
                f"WHERE count > {self.filter.min_count} " +\
                (f"and count < {self.filter.max_count}\n"
                    if self.filter.max_count is not None else "\n") + \
                "WITH n"
        dic = {f'categories{ident}': self.filter.categories} if hasCategories else None
        return (str, dic)

class Neo4jFinalBuilder(Neo4jQueryBuilder):
    @final
    def __execute(self, tx: Transaction) -> Result:
        query, kwargs = self.build()
        print(query)
        return tx.run(query, **kwargs)

    def map(self, result: Result):
        pass

    def execute(self, tx: Transaction) -> Any:
        return self.map(self.__execute(tx))

class Neo4jReturnBuilder(Neo4jFinalBuilder):
    type: QueryReturnTypes

    @staticmethod
    def byType(base: Neo4jQueryBuilder, type: QueryReturnTypes) -> 'Neo4jReturnBuilder':
        if  type == QueryReturnTypes.NODE or \
            type == QueryReturnTypes.TITLE or \
            type == QueryReturnTypes.ID:
            return Neo4jListReturnBuilder(base, type)
        elif type == QueryReturnTypes.COUNT:
            return Neo4jSingleReturnBuilder(base, type)

    def __init__(self, base: Neo4jQueryBuilder, type: QueryReturnTypes) -> None:
        super().__init__(base)
        self.type = type

    def limit(self, n: int):
        return Neo4jLimitBuilder(self, n)

    def skip(self, n: int):
        return Neo4jSkipBuilder(self, n)

class Neo4jListReturnBuilder(Neo4jReturnBuilder):
    def stringify(self) -> Neo4jQuerySegment:
        if self.type == QueryReturnTypes.NODE:
            str = "MATCH (n)-[]->(linked)\n" \
            "RETURN {article_id: n.article_id, title: n.title, categories: n.categories, \n" \
            "links: collect({article_id: linked.article_id, title: linked.title})}"
        elif self.type == QueryReturnTypes.TITLE:
            str = "RETURN n.title as title"
        elif self.type == QueryReturnTypes.ID:
            str = "RETURN n.article_id as id"

        return (str, None)

    def map(self, result: Result) -> list:
        if self.type == QueryReturnTypes.NODE:
            return list(map(mapper, result))
        elif self.type == QueryReturnTypes.TITLE:
            return list(map(lambda r: r['title'], result))
        elif self.type == QueryReturnTypes.ID:
            return list(map(lambda r: r['id'], result))

class Neo4jSingleReturnBuilder(Neo4jReturnBuilder):
    def stringify(self) -> Neo4jQuerySegment:
        if self.type == QueryReturnTypes.COUNT:
            str = "RETURN count(n) as count"
        return (str, None)

    def map(self, result: Result) -> Any:
        if self.type == QueryReturnTypes.COUNT:
            return {'count': result.single()[0]}

class Neo4jGeneralFilterBuilder(Neo4jFilterBuilder):
    filter: GeneralFilter

    def __init__(self, base: Neo4jQueryBuilder, filter: GeneralFilter) -> None:
        super().__init__(base)
        self.filter = filter

    def stringify(self) -> Neo4jQuerySegment:
        ident = Neo4jQueryBuilder.ident()

        if type(self.filter) == IdsFilter:
            field = 'article_id'
            arr = self.filter.ids
        elif type(self.filter) == TitlesFilter:
            field = 'title'
            arr = self.filter.titles
        elif type(self.filter) == CategoriesFilter:
            field = 'categories'
            arr = self.filter.categories

        str = (f"WHERE n.{field} in $arr{ident}\n" \
                if field != 'categories' else
            f"WHERE any(x in n.{field} WHERE x in $arr{ident})\n") + \
            "WITH n"
        dic = {f"arr{ident}": arr}
        return (str, dic)

class Neo4jSortBuilder(Neo4jQueryBuilder):
    sort: QuerySort

    def __init__(self, base: Neo4jQueryBuilder, sort: QuerySort) -> None:
        super().__init__(base)
        self.sort = sort

    def stringify(self) -> Neo4jQuerySegment:
        order = self.sort.type
        if self.sort.sort_by == SortByEnum.LINK_COUNT:
            str = "MATCH (n)-[links:Link]->(:Article)\n" \
                "WITH n, count(links) as count\n" \
                f"ORDER BY count(links)\n {order}" \
                "WITH n"
        elif self.sort.sort_by == SortByEnum.ID:
            str = f"ORDER BY n.article_id {order}"
        elif self.sort.sort_by == SortByEnum.TITLE:
            str = f"ORDER BY n.title {order}"
        return (str, None)
    
    def returnType(self, type: QueryReturnTypes):
        return Neo4jReturnBuilder.byType(self, type)

class Neo4jCutBuilder(Neo4jFinalBuilder):
    cut: int

    def __init__(self, base: 'Neo4jQueryBuilder', cut: int) -> None:
        super().__init__(base)
        self.cut = cut

    def map(self, result: Result):
        return self._baseBuilder.map(result)

class Neo4jLimitBuilder(Neo4jCutBuilder):
    def stringify(self) -> Neo4jQuerySegment:
        return (f"LIMIT {self.cut}", None)

class Neo4jSkipBuilder(Neo4jCutBuilder):
    def stringify(self) -> Neo4jQuerySegment:
        return (f"SKIP {self.cut}", None)

    def limit(self, n: int):
        return Neo4jLimitBuilder(self, n)