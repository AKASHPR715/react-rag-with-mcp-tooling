# neo4j_tool.py
import os
from neo4j import GraphDatabase
from langchain.tools import tool

# -------------------------------
# Neo4j Configuration
# -------------------------------
NEO4J_URI="neo4j+s://d91363b7.databases.neo4j.io"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="BmxHeHKMtMtTbJkDMaKi8ccYIXME20Mmz_ie07nc7fw"

# Initialize Neo4j driver (singleton)
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_cypher_query(query: str, parameters: dict = None) -> list:
    """Run a Cypher query and return results as list of dictionaries."""
    with neo4j_driver.session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]


@tool
def query_tax_graph(natural_language_query: str) -> str:
    """
    Use this to answer questions that benefit from structured relationships,
    such as: 
      - "Which deductions can be claimed together?"
      - "What sections are linked to NPS?"
      - "Show hierarchy of Chapter VI-A sections."
    
    Input: A specific question that implies relationships or dependencies.
    """
    query_map = {
        "nps related sections": """
        MATCH (s:Section)-[:RELATED_TO]->(:Topic {name: 'NPS'})
        RETURN s.section_id AS Section, s.title AS Title
        """,
        "deductions that can be claimed with 80c": """
        MATCH (s1:Section {section_id: '80C'})-[:CAN_BE_CLAIMED_WITH]->(s2:Section)
        RETURN s2.section_id AS Section, s2.title AS Title
        """,
        "chapter via sections": """
        MATCH (c:Chapter)<-[:PART_OF]-(s:Section)
        RETURN c.name AS Chapter, collect(s.section_id) AS Sections
        LIMIT 5
        """
    }

    q_lower = natural_language_query.strip().lower()

    for key, cypher in query_map.items():
        if key in q_lower:
            try:
                results = run_cypher_query(cypher)
                if not results:
                    return "No relevant relationships found in the tax graph."
                return "\n".join(str(r) for r in results)
            except Exception as e:
                return f"Graph query failed: {str(e)}"

    return "I cannot answer this using the tax knowledge graph. Try rephrasing or use another tool."

# MCP Tool Definition removed as app/mcp_app.py is missing.
