from dataclasses import dataclass, field
from typing import Any, Dict, List

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