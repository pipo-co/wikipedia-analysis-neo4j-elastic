# Analisis de Wikipedia utilizando Neo4j y ElasticSearch

## Idea Principal
La idea principal es crear una herramienta ETL que a partir de un articulo de wikipedia (articulo `centro`) y una distancia maxima (`radio`) se consigan todos los articulos que se puedan llegar a partir del articulo centro siguiendo los links a otros articulos de wikipedia dentro del contenido del mismo en menos de `radio` saltos. Estos articulos, junto con sus relaciones y categorias seran cargadas en bases Neo4j (relaciones) y ElasticSearch (contenido del articulo) especificadas.
Una vez cargada la informacion, la herramienta proveera facilidades para realizar queries que involucren ambas bases de datos. Un ejemplo del tipo de query pensadas en soportar es: "quiero todos los titulos de los articulos de categoria 'lenguaje de programacion' que esten a menos de 3 saltos de la pagina de wikipedia de 'Java' (centro del grafo) y que su contenido contenga la palabra 'inmutable'".

### Neo4j
En neo4j los nodos seran los articulos, con el id del articulo y la propiedad 'categorias' con las categorias del articulo, y las relaciones seran si un articulo referencia a otro (es posible que dos articulos se referencien entre si) con la propiedad de cantidad de veces que se referencia. Notese que en neo no se guardara nada con respecto al contenido del articulo. Esto facilita consultas acerca de relaciones entre articulos.

### ElasticSearch
En elastic el id tambien sera el id del articulo (de esta manera los contenidos de ambas bases estaran relacionados) y tendra las propiedades 'titulo' con el titulo del articulo, 'contenido' con el contenido del articulo completo en texto plano y 'categorias' con todas las categorias del articulo. Esto facilita consultas full text de articulos.

### Aplicacion
La logica de aplicacion sera desarrollada en python, pues cuenta con sencillos clientes para Neo4j y ElasticSearch. Se espera que la conexion con Wikipedia utilizando este lenguaje tambien sea sencilla.
Para facilidad de uso, en principio se propone que la herramienta sea un servidor que exponga sus funcionalidades mediante una API HTTP, donde uno de los endpoints sera la funcionalidad ETL, y el resto seran funcionalidades de busqueda. Para inicializar el servidor deberan ser provistos los parametros de conexion a las bases Neo4j y ElasticSearch donde se quieran cargar o analizar los datos.
Las respuestas seran en formato JSON todavia a definir (probablemente parecido al de la interfaz HTTP de Neo).
En principio no hay expectativa de desarrollo de un entorno grafico o de visualizacion de los datos, pero no descartamos la posibilidad de desarrollar una simple interfaz web para interactuar con el servidor, o encontrar alguna herramienta para visualizar el grafo de los articulos

#### Parametros ETL
  - URL de articulo de wikipedia valido o, lenguaje y id de revision del articulo
  - Cantidad maxima de saltos a traer de la base de datos de wikipedia (para evitar tener que traerla entera)
  - `Opcional`. Lista de categorias de articulos a traer. De no especificarse se traeran los articulos de cualquier categoria.

#### Busquedas propuestas



