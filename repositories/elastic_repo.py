from typing import Optional, List, Dict, Any, Iterator, Union, Tuple, overload, Literal

from elasticsearch_dsl import Index, Document, Text, Keyword, Search, Q, response, analyzer
from elasticsearch_dsl.connections import connections

from models import ElasticFilter, BoolOp, TextSearchField

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

    @overload
    def search(self, filters: List[ElasticFilter], with_content: Literal[True] = True) -> Iterator[Tuple[int, str]]:
        pass

    @overload
    def search(self, filters: List[ElasticFilter], with_content: Literal[False] = False) -> Iterator[int]:
        pass

    def search(self, filters: List[ElasticFilter], with_content: bool = False) -> Iterator[Union[int, Tuple[int, str]]]:
        must: List[Q] = []
        should: List[Q] = []

        for filter in filters:
            op: List[Q] = must if filter.bool_op == BoolOp.AND else should
            field: str = 'title' if filter.field == TextSearchField.TITLE else 'content'  # todo mejorar

            for match in filter.matches:
                is_phrase: bool = True if ' ' in match else False

                query_type: str = 'match_phrase' if is_phrase else 'match'
                query_params: Dict[str, Any] = {field: {'query': match}}
                if not is_phrase and filter.fuzzy:
                    query_params[field]['fuzziness'] = 2  # Solo se puede aplicar fuzzy si no es una frase

                op.append(Q(query_type, **query_params))

        # Projection
        include: List[str] = ['article_id']
        if with_content:
            include.append('content')

        # Prepare search
        s = Search(using=connections.get_connection(self.repo_id), index=self.index._name)
        if filters:
            s = s.query('bool', must=must, should=should)
        s = s.source(include=include)

        return map(self._id_content_mapper if with_content else self._id_mapper, s.scan())

    @staticmethod
    def _id_mapper(hit):
        return hit.article_id

    @staticmethod
    def _id_content_mapper(hit):
        return hit.article_id, hit.content

    def strict_search_query(self, string: str) -> response:
        s = Search(using=self.repo_id)
        s = s.query('query_string', **{'query': string, 'default_field': 'content'})
        # s = s.query("query_string", query=string, fields=['content'])
        return s.execute()
