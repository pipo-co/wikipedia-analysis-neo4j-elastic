from typing import Optional
from datetime import datetime
from elasticsearch import Elasticsearch
from fastapi import FastAPI, Request, Form
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import starlette.status as status
import wikipedia

app = FastAPI()
templates = Jinja2Templates(directory="templates/")
elastic_parameters = {}
neo_parameters = {}
center = ''
lang = ''
radius = None
category = None
es = None

@app.get("/")
def setup(request: Request):
    if elastic_parameters == {}:
        return RedirectResponse('/setup', status_code=status.HTTP_302_FOUND)
    if center == '':
        return RedirectResponse('/import-parameters', status_code=status.HTTP_302_FOUND)

    return 'ok'

@app.get("/setup")
def setup(request: Request):
    return templates.TemplateResponse('setupForm.html', context={'request': request})

@app.post("/setup")
async def setup(request: Request, elastic_ip: str = Form(...), elastic_port: int = Form(...),
            neo_ip: str = Form(...), neo_port: int = Form(...)):
    global elastic_parameters, neo_parameters, es
    
    elastic_parameters["ip"] = elastic_ip
    elastic_parameters["port"] = elastic_port
    neo_parameters["ip"] = neo_ip
    neo_parameters["port"] = neo_port
    
    es = Elasticsearch(HOST=elastic_parameters["ip"],PORT=elastic_parameters["port"])

    return RedirectResponse('/import-parameters', status_code=status.HTTP_302_FOUND)

@app.get("/import-parameters")
def import_parameters(request: Request):
    result = ""
    return templates.TemplateResponse('importForm.html', context={'request': request})

@app.post("/import-parameters")
async def import_parameters(center_param: str = Form(...), lang_param: str = Form(...), radius_param: int = Form(...), category_param: Optional[str] = Form(None)):
    global center, lang, radius, category
    center = center_param
    lang = lang_param
    radius = radius_param
    category = category_param

    return {"center":  center, 
            "lang": lang, 
            "radius": radius, 
            "category": category,
            "elastic": elastic_parameters["ip"]+':'+str(elastic_parameters["port"]),
            "neo4j": neo_parameters["ip"]+':'+str(neo_parameters["port"]),
    }

@app.get("/test-elastic-post")
def elastic_test_post(request: Request):
    document = {
        "description": "this is a test",
        "timestamp": datetime.now()
    }
    index = "testing"
    doc_id = 1
    es.index(index=index, doc_type="test", id=doc_id, body=document)
    return document

@app.get("/test-elastic-get")
def elastic_test_get(request: Request):
    result = es.get(index="testing", doc_type="test", id=1)
    retrieved_document = result['_source']
    return "Retrieved document: {Id: " + result['_id'] + ", Description: " + retrieved_document['description'] + ", Timestamp: " +retrieved_document['timestamp'] + "}"