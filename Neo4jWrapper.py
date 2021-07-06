from typing import List
from neo4j import GraphDatabase

class Neo4jWrapper:

    def __init__(self, ip, port, user, password):
        uri = "bolt://" + ip + ":" + str(port)
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_article(self, id: int, title: str, categories: List[str]):
        """
        Parameters:
        id - Wikipedia's article id.
        title - Wikipedia's article title.
        categories - List of the categories the article is in
        """
        with self.driver.session() as session:
            session.write_transaction(self._create_article_node, id, title, categories)

    def create_relationships(self, id: int, related_articles: List[int]):
        """
        Parameters:
        id - Wikipedia's article id.
        related_articles - List of article ids that are linked to the main article
        """
        with self.driver.session() as session:
            session.write_transaction(self._create_article_relationships, id, related_articles)

    @staticmethod
    def _create_article_node(tx, id: int, title: str, categories: List[str]):
        tx.run("CREATE (a:Article {article_id: $id, title: $title, categories:$categories})",
                        id=id, title=title, categories=categories)
    
    @staticmethod
    def _create_article_relationships(tx, id: int, related_articles: List[int]):
        for i in range(len(related_articles)):
            tx.run("MATCH (a:Article), (b:Article) WHERE a.article_id = $a_id AND b.article_id = $b_id "+
                "CREATE (a)-[r:LINKS]->(b)", a_id=id, b_id=related_articles[i])

# if __name__ == "__main__":
#     neo = Neo4jWrapper("localhost", 7687, "neo4j", "password")
#     neo.create_article(5, "byebye world", ["byebye", "world"])
#     neo.create_article(22, "chao mundo", ["chao", "mundo", "world"])
#     neo.create_relationships(22, [12, 5])
#     neo.close()