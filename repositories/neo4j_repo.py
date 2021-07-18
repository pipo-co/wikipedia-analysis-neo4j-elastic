from abc import ABCMeta, abstractmethod
import itertools

from neo4j.work import result
from neo4j.work.transaction import Transaction
from models import ArticleNode, DistanceFilterStrategy, GeneralFilter, QueryReturnTypes
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
            'match (n:Article {article_id: $source_id}) '
            'merge (v:Article {article_id: $dest_id, title: $dest_title, categories: $dest_categories}) '
            'merge (n)-[r:Link]->(v)',
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
            'match (n:Article {article_id: $source_id}) '
            'match (v:Article {title: $dest_title}) '
            'merge (n)-[r:Link]->(v)',
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
            "match (exterior)-[]->(m) "
            "return {article_id: exterior.article_id, title: exterior.title, categories: exterior.categories, " 
            "links: collect({article_id: m.article_id, title: m.title})}",
            center_title=center, ext_title=string
        )
        return result.single()

    def buildQuery(self) -> 'Neo4jFilterQuery':
        return Neo4jFilterQuery()

    def executeQuery(self, query: 'Neo4jQuery') -> Result:
        with self.session() as session:
            return session.write_transaction(query.execute)

    def get_connections(self, node_title: str) -> Record:
        with self.session() as session:
            return session.write_transaction(self._get_connections, node_title)
    
    @staticmethod
    def _get_connections(tx: Transaction, node_title: str) -> Record:
        result = tx.run(
            'match (n:Article {title: $title})-[r]-(m) return {article_id: n.article_id, title: n.title, categories: n.categories, links: collect({article_id: m.article_id, title: m.title})}',
            title=node_title
        )
        return result.single()

def mapper(record: Record) -> ArticleNode:
    return ArticleNode(id=record['article_id'], title=record['title'], categories=record['categories'], links=record['links'])

# Custom Exceptions
class Neo4jWriteException(Exception):
    pass

Neo4jQuerySegment = Tuple[str, dict[str, Any]]

class Neo4jQuery:
    query: str
    kwargs: dict[str, Any]

    def __init__(self, query: str, args: dict[str, Any]):
        self.kwargs = args
        self.query = query

    def execute(self, tx: Transaction) -> Result:
        return tx.run(self.query, **self.kwargs)

class Neo4jQueryBuilder():
    _baseBuilder: Optional['Neo4jQueryBuilder']
    ident = 0

    def __init__(self, base: 'Neo4jQueryBuilder' = None) -> None:
        self._baseBuilder = base

    @abstractmethod
    def stringify(self) -> Neo4jQuerySegment:
        pass

    @final
    def _build(self) -> List[Neo4jQuerySegment]:
        list = self._baseBuilder._build() if self._baseBuilder is not None else []
        list.append(self.stringify())
        return list

    @final
    def build(self) -> Neo4jQuery:
        query, args = map(list, zip(*self._build()))
        dic = dict(itertools.chain.from_iterable(d.items() for d in args))
        return Neo4jQuery('\n'.join(query), dic)

class Neo4jFilterQuery(Neo4jQueryBuilder):
    def generalFilter(self, filter: GeneralFilter):
        return Neo4jGeneralFilter(self._baseBuilder, filter)

    def distanceFilter(self, source: str, distance: int, strategy: DistanceFilterStrategy):
        return Neo4jDistanceFilter(self._baseBuilder, source, distance, strategy)

    def returnType(self, type: QueryReturnTypes):
        # if  type == QueryReturnTypes.COUNT or \
        #     type == QueryReturnTypes.TITLE or \
        #     type == QueryReturnTypes.ID:
        return Neo4jSimpleReturn(self._baseBuilder, type)

class Neo4jDistanceFilter(Neo4jFilterQuery):
    source_node: str
    dist: int
    strategy: DistanceFilterStrategy

    def __init__(self, base: Neo4jQueryBuilder, source_node: str, dist: int, strategy: DistanceFilterStrategy) -> None:
        super().__init__(base)
        self.source_node = source_node
        self.dist = dist
        self.strategy = strategy

    def stringify(self) -> Neo4jQuerySegment:
        return ('', dict())

class Neo4jSimpleReturn(Neo4jQueryBuilder):
    type : QueryReturnTypes

    def __init__(self, base: Neo4jQueryBuilder, type: QueryReturnTypes) -> None:
        super().__init__(base)
        self.type = type

    def stringify(self) -> Neo4jQuerySegment:
        return ('', dict())

class Neo4jGeneralFilter(Neo4jFilterQuery):
    filter: GeneralFilter

    def __init__(self, base: Neo4jQueryBuilder, filter: GeneralFilter) -> None:
        super().__init__(base)
        self.filter = filter

    def stringify(self) -> Neo4jQuerySegment:
        return ('', dict())
