from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Union, Optional

from pydantic.main import BaseModel

@dataclass
class ImportArticleNode:
    id: int
    title: str
    links: List[str] = field(default_factory=list)

class ArticleNode(BaseModel):
    id: int
    title: str
    categories: List[str]
    links: List[Dict[str, Any]]

# Return Types
class QueryReturnTypes(Enum):
    COUNT = auto()
    TITLE = auto()
    ID = auto()
    NODE = auto()
    NODE_WITH_CONTENT = auto()

# Elastic Filters
class TextSearchFields(Enum):
    TITLE = 'title'
    CONTENT = 'content'

class TextSearchStrategy(Enum):
    EXACT = auto()
    FUZZY = auto()

class ElasticTextSearchFilter(BaseModel):
    field: TextSearchFields
    strategy: TextSearchStrategy
    match: str

# Node Filters
class DistanceFilterStrategy(Enum):
    AT_DIST = auto()
    UP_TO_DIST = auto()

class NeoDistanceFilter(BaseModel):
    source_node: str
    dist: int
    strategy: DistanceFilterStrategy = DistanceFilterStrategy.UP_TO_DIST

class NeoLinksFilter(BaseModel):
    min_count: int = 0
    max_count: Optional[int] = None
    categories: Optional[List[str]] = None

# General Filters
class IdsFilter(BaseModel):
    ids: List[int]

class TitlesFilter(BaseModel):
    titles: List[str]

class CategoriesFilter(BaseModel):
    categories: List[str]

# Sort Fields
class SortByEnum(Enum):
    ID = auto()
    TITLE = auto()
    LINK_COUNT = auto()

class SortType(Enum):
    ASC = auto()
    DESC = auto()

class QuerySort(BaseModel):
    sort_by: SortByEnum
    type: SortType = SortType.ASC


GeneralFilter = Union[IdsFilter, TitlesFilter, CategoriesFilter]
ElasticFilter = Union[ElasticTextSearchFilter]
NeoFilter = Union[NeoDistanceFilter, NeoLinksFilter]

# Primero se ejecuta elastic siempre - No hay ors
class ArticleQuery(BaseModel):
    return_type: QueryReturnTypes
    elastic_filter: List[ElasticFilter]  # Hay diferencia entre == y contains?
    neo_filter: List[NeoFilter]
    general_filters: List[GeneralFilter]
    sort: Optional[QuerySort] = None
    limit: int  # Tambien se podria offset ??
    offset: int
