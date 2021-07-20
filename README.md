# Analisis de Wikipedia utilizando Neo4j y ElasticSearch

## Dependencias

- Python 3.8 o superior
- Neo4j Server 4.3.1 o superior. Debe tener el plugin oficial Apoc correspondiente de la version instalado
- Elasticsearch 7.13.3 o superior
- El resto de las dependencias pueden instalarse ejecutando `pip install -r requirements.txt`

## Correr el servidor

Para ejecutar el servidor basta ejecutar `uvicorn main:app`. 
El mismo se levantara automaticamente en `localhost:8000`.
La documentacion OpenApi 3.0 generada automaticamente de los endpoints del servidor se puede encontrar en `localhost:8000/docs`.

Para la configuracion inicial de las bases de datos se puede utilizar un archivo .env especificando variables de entorno.

Una configuracion de ejemplo:
```dotenv
# General Config
WIKI_OPEN_DBS_ON_STARTUP = true

# Neo4j connection config
WIKI_NEO_IP = localhost
WIKI_NEO_PORT = 7687
# WIKI_NEO_DB = default
WIKI_NEO_USER = neo4j
WIKI_NEO_PASS = tobias

# ElasticSearch connection config
WIKI_ES_IP = localhost
WIKI_ES_PORT = 9200
WIKI_ES_DB = wikipedia
# WIKI_ES_USER = default
# WIKI_ES_PASS = default
```
De todas maneras, las conexiones podran ser configuradas una vez inicializado el servidor en la pagina ...(TODO PECHI)

## Endpoints principales

- Para importar se debera ejecutar un pedido POST a `/api/import` con los parametros en el payload del request en formato json
- Para realizar busquedas se debera ejecutar un pedido GET a `/api/search` con la query en formato json en el peyload del request

## Idea Principal
La idea principal es crear una herramienta ETL que a partir de un articulo de wikipedia (articulo `centro`) y una distancia maxima (`radio`) se consigan todos los articulos que se puedan llegar a partir del articulo centro siguiendo los links a otros articulos de wikipedia dentro del contenido del mismo en menos de `radio` saltos. 

Estos articulos, junto con sus relaciones y categorias seran cargadas en bases Neo4j (relaciones) y ElasticSearch (contenido del articulo) especificadas.
Una vez cargada la informacion, la herramienta proveera facilidades para realizar queries que involucren ambas bases de datos. 

Un ejemplo del tipo de query pensadas en soportar es: "quiero todos los titulos de los articulos de categoria 'lenguaje de programacion' que esten a menos de 3 saltos de la pagina de wikipedia de 'Java' (centro del grafo) y que su contenido contenga la palabra 'inmutable'".

### Neo4j
En neo4j los nodos seran los articulos, con el id del articulo y la propiedad 'categorias' con las categorias del articulo, y las relaciones seran si un articulo referencia a otro (es posible que dos articulos se referencien entre si) con la propiedad de cantidad de veces que se referencia. Notese que en neo no se guardara nada con respecto al contenido del articulo. Esto facilita consultas acerca de relaciones entre articulos.

### ElasticSearch
En elastic el id tambien sera el id del articulo (de esta manera los contenidos de ambas bases estaran relacionados) y tendra las propiedades 'titulo' con el titulo del articulo, 'contenido' con el contenido del articulo completo en texto plano y 'categorias' con todas las categorias del articulo. Esto facilita consultas full text de articulos.

### Aplicacion
La logica de aplicacion sera desarrollada en Python, pues cuenta con sencillos clientes para Neo4j y ElasticSearch. Se espera que la conexion con Wikipedia utilizando este lenguaje tambien sea sencilla.

Para facilidad de uso, en principio se propone que la herramienta sea un servidor que exponga sus funcionalidades mediante una API HTTP, donde uno de los endpoints sera la funcionalidad ETL, y el resto seran funcionalidades de busqueda. Para inicializar el servidor deberan ser provistos los parametros de conexion a las bases Neo4j y ElasticSearch donde se quieran cargar o analizar los datos.

Las respuestas seran en formato JSON todavia a definir (probablemente parecido al de la interfaz HTTP de Neo).
En principio no hay expectativa de desarrollo de un entorno grafico o de visualizacion de los datos, pero no descartamos la posibilidad de desarrollar una simple interfaz web para interactuar con el servidor, o encontrar alguna herramienta para visualizar el grafo de los articulos

#### Parametros ETL
  - URL de articulo de wikipedia valido o, lenguaje y id de revision del articulo
  - Cantidad maxima de saltos a traer de la base de datos de wikipedia (para evitar tener que traerla entera)
  - `Opcional`. Lista de categorias de articulos a traer. De no especificarse se traeran los articulos de cualquier categoria.

### Busquedas
Elastic nos permite hacer busquedas exact y fuzzy del contenido y del titulo de los articulos.

Neo nos permite consultar las relaciones entre articulos, como articulos cercanos, la distancia entre dos articulos, si existe camino entre 2 articulos, etc.

Nos parece que tiene mucho valor poder realizar estos dos tipos de consultas simultaneamente para analizar rapidamente la estructura y el contenido de Wikipedia con facilidad y sencillez.

En general vamos a buscar realizar consultas donde el punto de partida sea el articulo centro, pues garantizamos que obtuvimos todas las relaciones de este articulo, por lo que el resultado de la consulta refleja perfectamnete el de Wikipedia. Realizar consultas entre 2 o mas articulos cercanos al borde de nuestro grafico no tiene mucho sentido, pues muchas relaciones entre articulos estaran faltando. Para este tipo de consultas convendra ejecutar el ETL nuevamente, configurando un nuevo centro.

Ideas particulares:
  - "Quiero todos los titulos de los articulos de la categoria 'Plantas' que esten a menos de 5 saltos de la pagina de wikipedia de 'Jazmin' y que se sean de la misma familia biologica"
  - "Quiero todos los titulos de los articulos de la categoria 'Perfumes' que esten a menos de 5 saltos de la pagina de wikipedia de 'Jazmin' y que contengan la palabra 'Aroma' ordenado por su cantidad de apariciones"
