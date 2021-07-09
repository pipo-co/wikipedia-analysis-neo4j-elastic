from collections import deque
from typing import Optional, Dict, Deque, List

from elasticsearch import Elasticsearch
from wikipedia import wikipedia, WikipediaPage

from models import ImportArticleNode
from neo4j_repo import Neo4jRepository


def main():
    import_wiki("Python (programming language)", 1)


def import_wiki(center_title: str, radius: int, lang: Optional[str] = None, categories: Optional[List[str]] = None):
    if lang:
        wikipedia.set_lang(lang)

    # es = Elasticsearch(HOST=elastic_parameters["ip"], PORT=elastic_parameters["port"])
    neo = Neo4jRepository('localhost', '7687', "neo4j", "tobias")

    # Utilizamos cola pues BFS
    node_q: Deque[ImportArticleNode] = deque()
    # La distancia al centro de cada nodo. -1 significa que es un nodo invalido.
    title_dist_dict: Dict[str, int] = {}

    center_page: WikipediaPage = wikipedia.page(center_title, auto_suggest=False)
    center_node: ImportArticleNode = ImportArticleNode(int(center_page.pageid), center_page.title, center_page.links)
    neo.create_article(center_node.id, center_node.title, center_page.categories)

    title_dist_dict[center_page.title] = 0
    node_q.append(center_node)

    test_count: int = 0

    # Recorrido BFS para poder saber la distancia al centro de cada nodo
    while node_q:
        current_node: ImportArticleNode = node_q.popleft()
        current_dist: int = title_dist_dict[current_node.title]
        for link in current_node.links:
            dist: Optional[int] = title_dist_dict.get(link, None)

            # Si todavia no lo vi, lo creo
            if dist is None:
                # Cargo el link de wikipedia
                page: WikipediaPage = wikipedia.page(link, auto_suggest=False)

                # Para crearlo se debe cumplir que:
                # 1. current_dist < radius porque sino estariamos creando un nodo en radio + 1
                # 2. De haberse especificado categorias, alguna de ellas debe estar en page
                if (
                    current_dist < radius and
                    (categories is None or any(cat in page.categories for cat in categories))
                ):
                    # Creo nodo y relacion en neo
                    if not neo.create_and_link_article(current_node.id, page.pageid, page.title, page.categories):
                        raise Exception('Un nodo que pense que tenia que crear, ya esta creado')

                    # Pongo el nuevo nodo en las estructuras
                    title_dist_dict[page.title] = current_dist + 1
                    node_q.append(ImportArticleNode(int(page.pageid), page.title, page.links))

                # Si no cumple, lo agrego con dist -1 para no volver a calcularlo
                else:
                    title_dist_dict[link] = -1

            # El nodo ya existia -> solo creo la relacion y listo
            else:
                if dist != -1:
                    neo.link_article(current_node.id, link)

            test_count += 1
            print(f'({current_node.title})---({link}). Total: {test_count}')

if __name__ == '__main__':
    main()
