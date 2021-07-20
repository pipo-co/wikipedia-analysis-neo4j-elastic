import json
import os
from pathlib import Path
from typing import Dict, Optional, List
from types import SimpleNamespace

import starlette.status as status
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse
from starlette.requests import Request
from starlette.responses import Response

from dependencies import databases
from dependencies.settings import settings
from models import ArticleNode, ArticleQuery, ImportSummary, SearchResponse
from querys import strict_search_query, process_query
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
    center_page: str = Field(..., title="Pagina Centro", description="Titulo de pagina de wikipedia (exactamente como aparece) desde donde se empieza a importar. Requerido.")
    radius: int = Field(..., gt=0, title='Centro', description='Distancia maxima a la cual un nodo puede estar de la pagina centro durante la importacion. Requerido.')
    categories: List[str] = Field(..., title='Categorias', description='Solo importar articulos dentro de estas categorias. Requerido.')
    lang: str = Field('en', title='Idioma de Wikipedia', description='El idioma de la wikipedia a usar. Es opcional, defaultea a Ingles.')


@app.post("/api/import", response_model=ImportSummary)
def wikipedia_import(import_request: WikipediaImportRequest):
    return import_wiki(import_request.center_page, import_request.radius, import_request.categories, import_request.lang)

@app.get("/api/simple_search")
def strict_search(source: str, string: str, leaps: int):
    return strict_search_query(source, string, leaps)

@app.get("/api/search")
async def search(query: ArticleQuery):
    return await process_query(query)

@app.get("/")
def searchForm(request: Request):
    return templates.TemplateResponse('search.html', context={'request': request})

# grafica la ultima query realizada, utiliza el archivo /static/json/data.json
@app.post("/graph")
async def graph(request: Request):
    data = await request.form()
    data = json.loads(data['query'])
    query = ArticleQuery(**data)
    searchResponse = await search(query)

    if data['return_type'] == "NODE":
        result = article_node_to_graph(searchResponse.result)
        return templates.TemplateResponse('graph.html', context={'request': request, 'result': result})
    else:
        return templates.TemplateResponse('normalResponse.html', context={'request': request, 'result': searchResponse.result})

@app.get("/reset")
async def reset(request: Request):
    databases.truncate_dbs()
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

def article_node_to_graph(nodes: List[ArticleNode]) -> Dict[str, List]:
    
    data ={
        "nodes" : [],
        "edges" : []
    }

    for node in nodes:
        data["nodes"].append(node.__dict__)
        data["edges"].extend([{"from": node.id, "to":link.article_id} for link in node.links])

    for node in data["nodes"]:
        del node['links']

    return data

# DEBUG
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)