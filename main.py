from typing import Optional, List
from fastapi import FastAPI, Request, Form
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import starlette.status as status
import uvicorn
import os, json

from models import ArticleQuery
from querys import strict_search_query, process_query

from dependencies import databases
from dependencies.settings import settings
from wikipedia_import import import_wiki

app = FastAPI()
templates = Jinja2Templates(directory="templates/")
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent.absolute() / "static"),
    name="static",
)

@app.on_event("startup")
def startup_event():
    if settings.wiki_open_dbs_on_startup:
        databases.neo_open(settings.wiki_neo_ip, settings.wiki_neo_port, settings.wiki_neo_user, settings.wiki_neo_pass, settings.wiki_neo_db)
        databases.es_open(settings.wiki_es_ip, settings.wiki_es_port, settings.wiki_es_user, settings.wiki_es_pass, settings.wiki_es_db)

@app.on_event("shutdown")
def shutdown_event():
    databases.close_all()

class WikipediaImportRequest(BaseModel):
    center_page: str = Field(..., title="Pagina Centro", description="Titulo de pagina de wikipedia (exactamete como aparece) desde donde se empieza a importar. Requerido.")
    radius: int = Field(..., gt=0, title='Centro', description='Distancia maxima a la cual un nodo puede estar de la pagina centro durante la importacion. Requerido.')
    categories: List[str] = Field(..., title='Categorias', description='Solo importar articulos dentro de estas categorias. Requerido.')
    lang: str = Field('en', title='Idioma de Wikipedia', description='El idioma de la wikipedia a usar. Es opcional, defaultea a Ingles.')


@app.post("/api/import")
def wikipedia_import(import_request: WikipediaImportRequest):
    return import_wiki(import_request.center_page, import_request.radius, import_request.categories, import_request.lang)

@app.get("/api/strict_search")
def strict_search(source: str, string: str, leaps: int):
    file = strict_search_query(source, string, leaps)

    data ={
        "nodes" : [],
        "edges" : []
    }

    for node in file:
        data["nodes"].append(node.__dict__)
        data["edges"].extend([{"from": node.id, "to":link["article_id"]} for link in node.links])

    for node in data["nodes"]:
        del node['links']

    file_name = os.getcwd()+"/static/json/data.json"
    with open(file_name,'w') as f:
        f.write(json.dumps(data, indent = 4))
    
    return file

@app.get("/api/search")
def search(query: ArticleQuery):
    return process_query(query)

@app.get("/")
def search(request: Request):
    return templates.TemplateResponse('search.html', context={'request': request})

@app.post("/")
async def search(request: Request, source: str = Form(...), radius: int = Form(...), string: Optional[str] = Form(None)):
    strict_search(source, string, radius)
    return RedirectResponse('/graph', status_code=status.HTTP_302_FOUND)

# grafica la ultima query realizada, utiliza el archivo /static/json/data.json
@app.get("/graph")
def search(request: Request):
    return templates.TemplateResponse('graph.html', context={'request': request})

# @app.get("/setup")
# def setup(request: Request):
#     return templates.TemplateResponse('setupForm.html', context={'request': request})

@app.get("/reset")
async def search(request: Request):
    databases.truncate_dbs()
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

@app.get("/import-parameters")
def import_parameters(request: Request):
    return templates.TemplateResponse('importForm.html', context={'request': request})

@app.post("/import-parameters")
async def import_parameters(request: Request, center_param: str = Form(...), lang_param: str = Form(...), radius_param: str = Form(...), categories_param: Optional[str] = Form(None)):
    params = WikipediaImportRequest(center_page=center_param, radius=radius_param, lang=lang_param, categories=list(categories_param))
    wikipedia_import(import_request=params)
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

# DEBUG
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# @app.post("/setup")
# async def setup(request: Request, elastic_ip: str = Form(...), elastic_port: int = Form(...),
#             neo_ip: str = Form(...), neo_port: int = Form(...)):
#     global elastic_parameters, neo_parameters, es, neo
#
#     elastic_parameters["ip"] = elastic_ip
#     elastic_parameters["port"] = elastic_port
#     neo_parameters["ip"] = neo_ip
#     neo_parameters["port"] = neo_port
#
#     # db auth not implemented yet
#     es = Elasticsearch(HOST=elastic_parameters["ip"],PORT=elastic_parameters["port"])
#     neo = Neo4jRepository(neo_parameters["ip"], neo_parameters["port"], "neo4j", "password")
#
#     return RedirectResponse('/import-parameters', status_code=status.HTTP_302_FOUND)

# @app.get("/test-elastic-post")
# def elastic_test_post(request: Request):
#     document = {
#         "description": "this is a test",
#         "timestamp": datetime.now()
#     }
#     index = "testing"
#     doc_id = 1
#     es.index(index=index, doc_type="test", id=doc_id, body=document)
#     return document
#
# @app.get("/test-elastic-get")
# def elastic_test_get(request: Request):
#     result = es.get(index="testing", doc_type="test", id=1)
#     retrieved_document = result['_source']
#     return "Retrieved document: {Id: " + result['_id'] + ", Description: " + retrieved_document['description'] + ", Timestamp: " +retrieved_document['timestamp'] + "}"