"""
Imports the OWL ontology (enterprise_ontology.owl) into Neo4j using
the neosemantics (n10s) plugin, turning classes/properties into
actual graph nodes and relationships.
"""

import os
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OWL_FILE_PATH = PROJECT_ROOT / "ontology" / "owl" / "enterprise_ontology.owl"


def run_query(driver, query, params=None):
    with driver.session() as session:
        result = session.run(query, params or {})
        return list(result)


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print(f"Connecting to Neo4j at {NEO4J_URI}...")

    # Confirm graph config already initialized (from earlier manual step)
    print("Checking n10s graph config...")
    config_check = run_query(driver, "CALL n10s.graphconfig.show();")
    if not config_check:
        print("No graph config found — initializing now...")
        run_query(driver, "CALL n10s.graphconfig.init();")
    else:
        print("Graph config already present.")

    # Read the OWL file content
    if not OWL_FILE_PATH.exists():
        raise FileNotFoundError(f"OWL file not found at {OWL_FILE_PATH}")

    file_uri = OWL_FILE_PATH.as_uri()  # converts to file:///C:/... format
    print(f"Importing ontology from: {file_uri}")

    import_query = """
    CALL n10s.onto.import.fetch($file_uri, "RDF/XML")
    YIELD terminationStatus, triplesLoaded, triplesParsed, namespaces, extraInfo
    RETURN terminationStatus, triplesLoaded, triplesParsed, namespaces, extraInfo
    """

    result = run_query(driver, import_query, {"file_uri": file_uri})

    for record in result:
        print("\n--- Import Result ---")
        print(f"Status: {record['terminationStatus']}")
        print(f"Triples loaded: {record['triplesLoaded']}")
        print(f"Triples parsed: {record['triplesParsed']}")
        print(f"Namespaces: {record['namespaces']}")
        if record["extraInfo"]:
            print(f"Extra info: {record['extraInfo']}")

    # Quick sanity check: count imported nodes by label
    print("\n--- Node counts after import ---")
    counts = run_query(driver, """
        MATCH (n)
        RETURN labels(n) AS labels, count(*) AS count
        ORDER BY count DESC
        LIMIT 15
    """)
    for row in counts:
        print(f"{row['labels']}: {row['count']}")

    driver.close()
    print("\nOntology import complete.")


if __name__ == "__main__":
    main()