from typing import Optional, List

from elasticsearch_dsl import Index, Document, Text, Keyword, analyzer
from elasticsearch_dsl.connections import connections

_content_analyzer = analyzer(
    'folding_analyzer',
    tokenizer="standard",
    filter=["lowercase", "asciifolding"]
)

class ElasticArticle(Document):
    article_id: int = Keyword()
    title: str = Text()
    content: str = Text(analyzer=_content_analyzer)
    categories: str = Text()

class ElasticRepository:

    def __init__(self, ip: str = 'localhost', port: str = '9200', user: Optional[str] = None, password: Optional[str] = None, index: str = 'wikipedia') -> None:
        if user and password:
            connections.create_connection(hosts=[f'{ip}:{port}'], http_auth=f'{user}:{password}')
        else:
            connections.create_connection(hosts=[f'{ip}:{port}'])

        self.index: Index = Index(index)
        self.index.document(ElasticArticle)

        # Si el indice ya existe, lo borramos
        self.index.delete(ignore=[400, 404])

        # Creamos el indice
        self.index.create()

    def create_article(self, id: int, title: str, content: str, categories: List[str]) -> ElasticArticle:
        article: ElasticArticle = ElasticArticle(article_id=id, title=title, content=content, categories=categories)
        article.save()
        return article




