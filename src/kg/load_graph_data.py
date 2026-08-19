"""
Loads gold-layer data from Postgres into Neo4j as graph nodes,
connected via relationships matching the ontology's object properties.
"""

import os
from neo4j import GraphDatabase
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# Postgres connection
PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")
PG_DB = os.getenv("POSTGRES_DB")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")

pg_engine = create_engine(
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def run_write(query, params=None):
    with driver.session() as session:
        session.run(query, params or {})


def create_constraints():
    print("Creating uniqueness constraints for data nodes...")
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplier) REQUIRE s.supplier_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (st:Store) REQUIRE st.store_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Order) REQUIRE o.order_id IS UNIQUE",
    ]
    for c in constraints:
        run_write(c)
    print("Constraints created.")


def load_customers():
    print("Loading customers...")
    df = pd.read_sql("SELECT * FROM gold.dim_customer", pg_engine)
    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MERGE (c:Customer {customer_id: row.customer_id})
            SET c.full_name = row.full_name,
                c.email = row.email,
                c.region = row.region,
                c.segment = row.segment,
                c.churn_status = row.churn_status
        """, rows=df.to_dict("records"))
    print(f"Loaded {len(df)} Customer nodes")


def load_suppliers():
    print("Loading suppliers...")
    df = pd.read_sql("SELECT * FROM gold.dim_supplier", pg_engine)
    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MERGE (s:Supplier {supplier_id: row.supplier_id})
            SET s.supplier_name = row.supplier_name,
                s.country = row.country
        """, rows=df.to_dict("records"))
    print(f"Loaded {len(df)} Supplier nodes")


def load_stores():
    print("Loading stores...")
    df = pd.read_sql("SELECT * FROM gold.dim_store", pg_engine)
    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MERGE (st:Store {store_id: row.store_id})
            SET st.store_name = row.store_name,
                st.channel = row.channel,
                st.region = row.region
        """, rows=df.to_dict("records"))
    print(f"Loaded {len(df)} Store nodes")


def load_products():
    print("Loading products (and linking to suppliers)...")
    df = pd.read_sql("SELECT * FROM gold.dim_product", pg_engine)
    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MERGE (p:Product {product_id: row.product_id})
            SET p.product_name = row.product_name,
                p.category = row.category,
                p.subcategory = row.subcategory,
                p.brand = row.brand,
                p.unit_cost = row.unit_cost,
                p.unit_price = row.unit_price,
                p.margin_pct = row.margin_pct
        """, rows=df.to_dict("records"))
    print(f"Loaded {len(df)} Product nodes")

    # Link products to suppliers via suppliedBy relationship
    prod_supplier = pd.read_sql("""
        SELECT dp.product_id, ds.supplier_id
        FROM gold.dim_product dp
        JOIN silver.products sp ON dp.product_id = sp.product_id
        JOIN gold.dim_supplier ds ON sp.supplier_id = ds.supplier_id
    """, pg_engine)
    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MATCH (p:Product {product_id: row.product_id})
            MATCH (s:Supplier {supplier_id: row.supplier_id})
            MERGE (p)-[:suppliedBy]->(s)
        """, rows=prod_supplier.to_dict("records"))
    print(f"Linked {len(prod_supplier)} Product-Supplier relationships")


def load_orders_and_lineitems():
    print("Loading orders (in batches, this is the big one)...")

    orders_query = """
        SELECT DISTINCT f.order_id, dc.customer_id, dst.store_id,
               f.order_status, f.payment_method
        FROM gold.fact_orders f
        JOIN gold.dim_customer dc ON f.customer_key = dc.customer_key
        JOIN gold.dim_store dst ON f.store_key = dst.store_key
    """
    orders_df = pd.read_sql(orders_query, pg_engine)

    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MERGE (o:Order {order_id: row.order_id})
            SET o.order_status = row.order_status,
                o.payment_method = row.payment_method
            WITH o, row
            MATCH (c:Customer {customer_id: row.customer_id})
            MERGE (c)-[:placesOrder]->(o)
            WITH o, row
            MATCH (st:Store {store_id: row.store_id})
            MERGE (o)-[:fulfilledByStore]->(st)
        """, rows=orders_df.to_dict("records"))
    print(f"Loaded {len(orders_df)} Order nodes with relationships")

    print("Loading order line items (this may take 1-2 minutes)...")
    items_query = """
        SELECT f.order_item_key, f.order_id, dp.product_id,
               f.quantity, f.unit_price_at_sale, f.discount_pct, f.line_revenue
        FROM gold.fact_orders f
        JOIN gold.dim_product dp ON f.product_key = dp.product_key
    """
    items_df = pd.read_sql(items_query, pg_engine)

    # Batch in chunks of 5000 to avoid overwhelming a single transaction
    batch_size = 5000
    total = len(items_df)
    for start in range(0, total, batch_size):
        batch = items_df.iloc[start:start + batch_size]
        with driver.session() as session:
            session.run("""
                UNWIND $rows AS row
                MERGE (li:OrderLineItem {order_item_key: row.order_item_key})
                SET li.quantity = row.quantity,
                    li.unit_price_at_sale = row.unit_price_at_sale,
                    li.discount_pct = row.discount_pct,
                    li.line_revenue = row.line_revenue
                WITH li, row
                MATCH (o:Order {order_id: row.order_id})
                MERGE (o)-[:hasLineItem]->(li)
                WITH li, row
                MATCH (p:Product {product_id: row.product_id})
                MERGE (li)-[:forProduct]->(p)
            """, rows=batch.to_dict("records"))
        print(f"  ...loaded {min(start + batch_size, total)}/{total} line items")

    print(f"Loaded {total} OrderLineItem nodes with relationships")


def main():
    create_constraints()
    load_customers()
    load_suppliers()
    load_stores()
    load_products()
    load_orders_and_lineitems()
    driver.close()
    print("\nGraph data load complete.")


if __name__ == "__main__":
    main()