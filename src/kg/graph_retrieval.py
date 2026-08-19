"""
GraphRAG retrieval layer: queries the Neo4j knowledge graph for relevant
business context (class definitions, relationships, taxonomy) to enrich
the Text-to-SQL prompt beyond raw schema dumps.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(override=True)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def run_query(query, params=None):
    with driver.session() as session:
        result = session.run(query, params or {})
        return [dict(record) for record in result]


def get_class_definitions():
    """
    Pulls every ontology class and its business definition (rdfs:comment),
    e.g. Customer -> 'An individual or organization that has placed...'
    """
    query = """
        MATCH (c:n4sch__Class)
        WHERE c.n4sch__name IS NOT NULL
        OPTIONAL MATCH (c)-[:n4sch__comment]-()
        RETURN c.n4sch__name AS name, c.n4sch__comment AS definition
        ORDER BY name
    """
    return run_query(query)


def get_taxonomy_hierarchy():
    """
    Pulls the class subclass hierarchy (Product -> Electronics -> Laptops, etc.)
    """
    query = """
        MATCH (child:n4sch__Class)-[:n4sch__SCO]->(parent:n4sch__Class)
        RETURN child.n4sch__name AS child, parent.n4sch__name AS parent
        ORDER BY parent, child
    """
    return run_query(query)


def get_object_properties():
    """
    Pulls the relationships (object properties) with their domain/range,
    e.g. placesOrder: Customer -> Order. This tells the agent correct join logic.
    """
    query = """
        MATCH (r:n4sch__Relationship)
        OPTIONAL MATCH (r)-[:n4sch__DOMAIN]->(d:n4sch__Class)
        OPTIONAL MATCH (r)-[:n4sch__RANGE]->(ra:n4sch__Class)
        RETURN r.n4sch__name AS relationship, d.n4sch__name AS domain, ra.n4sch__name AS range
        ORDER BY relationship
    """
    return run_query(query)


def get_active_customer_business_rules():
    """
    Hardcoded surfacing of the key logical restriction we defined in Protege
    (EnterpriseCustomer = Customer + hasChurnStatus 'Active').
    In a larger system this would come from parsing OWL restrictions directly,
    but explicitly surfacing it here demonstrates the exact business logic
    the baseline agent has no access to.

    Each rule carries "triggers": substrings that must appear in the user's
    question (case-insensitive) for the rule to be injected into the prompt.
    Without this, dumping every rule into every prompt regardless of relevance
    causes the LLM to over-apply rules to questions that never invoked them
    (e.g. silently adding a churn_status='Active' filter to a question that
    never mentioned "active").
    """
    return [
        {
            "rule": "Product-to-Supplier joins must go through silver.products (which has supplier_id) — gold.dim_product has NO supplier_key or supplier_id column",
            "triggers": ["supplier"],
        },
        {
            "rule": "EnterpriseCustomer means: Customer with segment='Enterprise' AND churn_status='Active'",
            "triggers": ["enterprise"],
        },
        {
            "rule": "SMBCustomer means: Customer with segment='SMB' AND churn_status='Active'",
            "triggers": ["smb"],
        },
        {
            "rule": "ConsumerCustomer means: Customer with segment='Consumer' AND churn_status='Active'",
            "triggers": ["consumer"],
        },
        {
            "rule": "'Active customer' in general means churn_status = 'Active' (not 'Churned' or 'At Risk')",
            "triggers": ["active"],
        },
        {
            "rule": "'At-risk customer' means churn_status = 'At Risk'",
            "triggers": ["at-risk", "at risk"],
        },
        {
            "rule": "Profit margin / margin percentage refers to the margin_pct column on gold.dim_product",
            "triggers": ["margin", "profit"],
        },
        {
            "rule": "Revenue always refers to line_revenue in gold.fact_orders, which already accounts for discounts",
            "triggers": ["revenue"],
        },
        {
            "rule": "'Region' by default refers to the customer's home region (gold.dim_customer.region). Only use the store/sales region (gold.dim_store.region) if the question explicitly asks about stores, channels, or sales locations.",
            "triggers": ["region"],
        },
    ]


def build_graph_context(question=None):
    """
    Assembles all retrieved graph knowledge into a single formatted
    context block to inject into the LLM prompt. When `question` is given,
    business rules are filtered to those whose trigger terms appear in the
    question, instead of injecting the entire rule set unconditionally.
    """
    classes = get_class_definitions()
    taxonomy = get_taxonomy_hierarchy()
    relationships = get_object_properties()
    business_rules = get_active_customer_business_rules()

    if question is not None:
        q_lower = question.lower()
        business_rules = [
            b for b in business_rules
            if any(trigger in q_lower for trigger in b["triggers"])
        ]

    context = "=== BUSINESS GLOSSARY (from Knowledge Graph Ontology) ===\n"
    for c in classes:
        if c["definition"]:
            context += f"- {c['name']}: {c['definition']}\n"

    context += "\n=== CATEGORY TAXONOMY ===\n"
    for t in taxonomy:
        context += f"- {t['child']} is a type of {t['parent']}\n"

    context += "\n=== ENTITY RELATIONSHIPS (correct join logic) ===\n"
    for r in relationships:
        if r["domain"] and r["range"]:
            context += f"- {r['relationship']}: {r['domain']} -> {r['range']}\n"

    context += "\n=== BUSINESS RULES / DEFINITIONS ===\n"
    for b in business_rules:
        context += f"- {b['rule']}\n"

    return context


if __name__ == "__main__":
    # Quick manual test
    print(build_graph_context("How many active enterprise customers do we have?"))