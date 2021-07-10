from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    # General config
    wiki_open_dbs_on_startup: bool = False

    # Neo4j connection config
    wiki_neo_ip: str = 'localhost'
    wiki_neo_port: int = 7687
    wiki_neo_db: Optional[str] = None
    wiki_neo_user: Optional[str] = None
    wiki_neo_pass: Optional[str] = None

    # ElasticSearch connection config
    wiki_es_ip: str = 'localhost'
    wiki_es_port: int = 9200
    wiki_es_db: str = 'wikipedia'
    wiki_es_user: Optional[str] = None
    wiki_es_pass: Optional[str] = None

    class Config:
        env_file = ".env"


settings: Settings = Settings()
