import concurrent.futures
import itertools
from collections import deque
import time
from typing import Optional, Dict, Deque, List, Iterator, Any, Tuple

from mediawiki import MediaWiki, MediaWikiPage, PageError, DisambiguationError

import dependencies.databases
from dependencies.settings import settings
from models import ImportArticleNode
from repositories.elastic_repo import ElasticRepository
from repositories.neo4j_repo import Neo4jRepository

INVALID_LINK: int = -1
MAX_CATEGORIES: int = 49
MAX_LINKS_PER_CATEGORY_FILTER_REQ: int = 49  # Un changui
WIKIPEDIA_USER_AGENT: str = 'neo_elastic_scraper; tbrandy@itba.edu.ar'

# Filtra links invalidos
def _link_filter_request(wikipedia: MediaWiki, links: Iterator[str], categories: List[str], executor: concurrent.futures.ThreadPoolExecutor) -> Tuple[List[str], List[concurrent.futures.Future]]:
    params: Dict[str, Any] = {
        'action': 'query',
        'prop': 'categories',
        'redirects': True,
        'format': 'json',
        'cllimit': 1,                           # Cantidad de categorias maximas. Con una alcanza
        'titles': '|'.join(links),              # Paginas a buscar
        'clcategories': '|'.join(categories)    # Categorias que debe tener la pagina (alguna de ellas)
    }
    response: Dict[str, Any] = wikipedia.wiki_request(params)
    pages: List[Dict[str, Any]] = response['query']['pages'].values()

    invalid_links: List[str] = []
    link_request_futures: List[concurrent.futures.Future] = []

    for page in pages:
        # Si posee alguna de las categorias, es un link valido. Preparamos el pedido de resolucion.
        # Sino, es un link invalido. Preparamos para que se agregue al diccionario
        # Aprovechamos para filtrar paginas invalidas por otras razones (id = 0)
        if 'categories' in page and page['pageid'] != 0:
            link_request_futures.append(executor.submit(wikipedia.page, page['title'], auto_suggest=False, preload=True))
        else:
            invalid_links.append(page['title'])

    return invalid_links, link_request_futures

def import_wiki(center_title: str, radius: int, categories: List[str], lang: str = 'en') -> int:
    if len(categories) > MAX_CATEGORIES or len(categories) == 0:
        raise ValueError(f'Max filtering categories on import is {MAX_CATEGORIES}')

    start_time = time.time()

    # Normalizo las categorias
    categories = ['Category:' + cat for cat in categories]

    wikipedia: MediaWiki = MediaWiki(lang=lang, user_agent=WIKIPEDIA_USER_AGENT)
    es: ElasticRepository = dependencies.databases.es_instance()
    neo: Neo4jRepository = dependencies.databases.neo_instance()

    # Utilizamos cola pues BFS
    node_q: Deque[ImportArticleNode] = deque()
    # La distancia al centro de cada nodo. INVALID_LINK significa que es un nodo invalido.
    title_dist_dict: Dict[str, int] = {}

    # Buscamos y creamos nodo centro
    center_page: MediaWikiPage = wikipedia.page(center_title, auto_suggest=False, preload=True)
    center_node: ImportArticleNode = ImportArticleNode(int(center_page.pageid), center_page.title, center_page.links)

    # Utilizamos una sola sesion de neo para el proceso de importacion
    with neo.session() as neo_session:
        # Truncamos las bases antes del import
        neo.truncate_db(neo_session)
        es.truncate_db()

        # Cargamos centro en las db
        neo.create_article(center_node.id, center_node.title, center_page.categories)
        es.create_article(center_node.id, center_node.title, center_page.content, center_page.categories)

        title_dist_dict[center_page.title] = 0
        node_q.append(center_node)

        # Logging variables
        ring_count: int = 0
        current_ring_count: int = 0
        current_node_count: int
        total_nodes_imported: int = 0

        # Recorrido BFS para poder saber la distancia al centro de cada nodo
        while node_q:
            current_node: ImportArticleNode = node_q.popleft()
            current_dist: int = title_dist_dict[current_node.title]  # Distancia del nodo al centro

            # Logging
            current_node_count = 0
            if ring_count < current_dist:
                ring_count = current_dist
                current_ring_count = 0
            else:
                current_ring_count += 1

            with concurrent.futures.ThreadPoolExecutor() as executor:

                # Calculamos que links ya resolvimos y creamos, y cuales necesitamos resolver/crear
                links_needing_request: List[str] = []
                for link in current_node.links:
                    dist: Optional[int] = title_dist_dict.get(link, None)

                    # Si no esta en el mapa, todavia no calculamos este link. Hay que calcularlo y guardarlo.
                    if dist is None:
                        # Si el nodo anterior estaba al borde del grafo, entonces no hay que crear nada, pues sino nos pasamos del radio
                        if current_dist < radius:
                            links_needing_request.append(link)

                    else:
                        # El nodo ya existia -> solo creo la relacion y listo. No queremos links invalidos ni autoreferencias
                        if dist != INVALID_LINK and current_node.title != link:
                            neo.link_article(current_node.id, link, neo_session)

                # Preparamos los request para filtrar los links por categoria (y invalidos)
                link_filter_request_futures: List[concurrent.futures.Future] = []
                for i in range(0, len(links_needing_request), MAX_LINKS_PER_CATEGORY_FILTER_REQ):
                    # Puedo preguntar como maximo por MAX_LINKS_PER_CATEGORY_FILTER_REQ links en un mismo request
                    link_filter_request_futures.append(
                        executor.submit(_link_filter_request, wikipedia, itertools.islice(links_needing_request, i, i + MAX_LINKS_PER_CATEGORY_FILTER_REQ), categories, executor)
                    )

                # Ejecutamos los request de filtrado y preparamos a partir de ellos los request de resolucion de links validos
                links_resolution_futures: List[concurrent.futures.Future] = []
                for future in concurrent.futures.as_completed(link_filter_request_futures):
                    invalid_links: List[str]
                    partial_links_resolution_futures: List[concurrent.futures.Future]
                    invalid_links, partial_links_resolution_futures = future.result()

                    # Guardamos los links invalidos en el dict
                    for link in invalid_links:
                        title_dist_dict[link] = INVALID_LINK

                    links_resolution_futures.extend(partial_links_resolution_futures)

                # Ejecutamos los request de resolcuion de links validos (al fin!)
                for future in concurrent.futures.as_completed(links_resolution_futures):
                    try:
                        page: MediaWikiPage = future.result()
                    except (PageError, DisambiguationError) as e:
                        # Link no encontrado -> Informamos y se current_node_count: int = 0guimos adelante
                        print(f'Couldn\'t find link {e.title} - Ignoring page from now on')
                        title_dist_dict[e.title] = INVALID_LINK
                        continue

                    # pageid viene como str!
                    pageid: int = int(page.pageid)

                    if page.title in title_dist_dict:
                        # Si esta en el dict, entonces ya lo habiamos calculado, no deberiamos estar aca. No deberia pasar, pero pasa (???
                        continue

                    # Creo nodo y relacion en neo
                    if not neo.create_and_link_article(current_node.id, pageid, page.title, page.categories, neo_session):
                        raise Exception('Un nodo que pense que tenia que crear, ya esta creado')

                    # Creo articulo en elastic
                    es.create_article(pageid, page.title, page.content, page.categories)

                    # Pongo el nuevo nodo en las estructuras
                    title_dist_dict[page.title] = current_dist + 1
                    node_q.append(ImportArticleNode(pageid, page.title, page.links))

                    total_nodes_imported += 1
                    current_node_count += 1
                    print(f'({current_node.title})-->({page.title}). Current Ring: {ring_count}. Current Node in Ring: {current_ring_count}. Current relationship: {current_node_count}. Total: {total_nodes_imported}')

    print(f'Total time elapsed: {time.time() - start_time}')
    return total_nodes_imported

# Para testear
if __name__ == '__main__':
    dependencies.databases.neo_open(settings.wiki_neo_ip, settings.wiki_neo_port, settings.wiki_neo_user, settings.wiki_neo_pass, settings.wiki_neo_db)
    dependencies.databases.es_open(settings.wiki_es_ip, settings.wiki_es_port, settings.wiki_es_user, settings.wiki_es_pass, settings.wiki_es_db)

    import_wiki("Titanic (1997 film)", 3, ['English-language films'])

    dependencies.databases.close_all()
