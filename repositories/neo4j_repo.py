from typing import List, Optional, Tuple

import neo4j
from neo4j import GraphDatabase, Session, Result, ResultSummary
from neo4j.exceptions import ClientError

_INDEX_ALREADY_EXISTS_CODE: str = 'Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists'

class Neo4jRepository:

    @staticmethod
    def _create_id_constraint(tx) -> None:
        id_result: Result = tx.run('CREATE CONSTRAINT article_unique_id ON (a:Article) ASSERT a.article_id IS UNIQUE')
        id_result.consume()

    @staticmethod
    def _create_name_constraint(tx) -> None:
        name_result: Result = tx.run('CREATE CONSTRAINT article_unique_name ON (a:Article) ASSERT a.article_name IS UNIQUE')
        name_result.consume()

    @staticmethod
    def _truncate_db(tx) -> None:
        name_result: Result = tx.run('MATCH (n)-[r]-(m) DELETE n, r')
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

            # Trunco la db seleccionada
            session.write_transaction(self._truncate_db)

    def session(self) -> Session:
        return self.driver.session(database=self.db)

    def close(self):
        self.driver.close()

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
            "MERGE (a:Article {article_id: $id, title: $title, categories:$categories})",
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

# Custom Exceptions
class Neo4jWriteException(Exception):
    pass

