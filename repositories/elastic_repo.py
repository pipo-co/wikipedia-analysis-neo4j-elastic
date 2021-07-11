from typing import Optional, List

from elasticsearch_dsl import Index, Document, Text, Keyword, Search, Q, response, analyzer
from elasticsearch_dsl.connections import connections
from six import string_types

_content_analyzer = analyzer(
    'folding_analyzer',
    tokenizer="standard",
    filter=["lowercase", "asciifolding"]
)

class ElasticArticle(Document):
    article_id: int = Keyword()
    title: str = Text()
    content: str = Text(analyzer=_content_analyzer)
    categories: str = Keyword()

class ElasticRepository:

    __repo_counter: int = 0

    def __init__(self, ip: str, port: int, user: Optional[str], password: Optional[str], index: str) -> None:
        self.__repo_counter += 1
        self.repo_id: str = f'wiki_es_{self.__repo_counter}'

        auth: str = f'{user}:{password}' if user and password else None
        # Crea una conexion global con el nombre 'repo_id'
        connections.create_connection(self.repo_id, hosts=[f'{ip}:{port}'], http_auth=auth)

        # Creamos el indice
        self.index: Index = Index(index, using=self.repo_id)
        self.index.document(ElasticArticle)
        self.index.save()

    def close(self) -> None:
        connections.remove_connection(self.repo_id)

    def truncate_db(self):
        self.index.delete()
        self.index.create()

    def create_article(self, id: int, title: str, content: str, categories: List[str]) -> ElasticArticle:
        article: ElasticArticle = ElasticArticle(article_id=id, title=title, content=content, categories=categories)
        article.save()
        return article

    def strict_search_query(self, string: str) -> response:
        s = Search(using=self.repo_id)
        s = s.query('query_string', **{'query': string, 'default_field': 'content'})
        # s = s.query("query_string", query=string, fields=['content'])
        return s.execute()
