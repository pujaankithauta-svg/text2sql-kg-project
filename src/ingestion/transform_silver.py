"""
Transforms bronze -> silver: dedupe, standardize dates, cast types,
enforce referential integrity by dropping orphaned rows.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")
PG_DB = os.getenv("POSTGRES_DB")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)


def parse_messy_date(series):
    """Try multiple date formats, return standardized datetime."""
    return pd.to_datetime(series, format="mixed", dayfirst=False, errors="coerce")


def truncate_silver():
    with engine.begin() as conn:
        for table in ["order_items", "orders", "products", "stores", "customers", "suppliers"]:
            conn.execute(text(f"TRUNCATE TABLE silver.{table} CASCADE"))
    print("Truncated all silver tables.")


def transform_suppliers():
    df = pd.read_sql("SELECT * FROM bronze.suppliers", engine)
    df = df.drop_duplicates(subset=["supplier_id"])
    out = df[["supplier_id", "supplier_name", "country", "contact_email"]]
    out.to_sql("suppliers", engine, schema="silver", if_exists="append", index=False)
    print(f"Silver suppliers: {len(out)} rows")


def transform_products():
    df = pd.read_sql("SELECT * FROM bronze.products", engine)
    df = df.drop_duplicates(subset=["product_id"])
    df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    # Drop rows referencing suppliers that don't exist in silver
    valid_suppliers = pd.read_sql("SELECT supplier_id FROM silver.suppliers", engine)["supplier_id"]
    df = df[df["supplier_id"].isin(valid_suppliers)]
    out = df[["product_id", "product_name", "category", "subcategory", "brand",
              "unit_cost", "unit_price", "supplier_id"]]
    out.to_sql("products", engine, schema="silver", if_exists="append", index=False)
    print(f"Silver products: {len(out)} rows")


def transform_stores():
    df = pd.read_sql("SELECT * FROM bronze.stores", engine)
    df = df.drop_duplicates(subset=["store_id"])
    out = df[["store_id", "store_name", "channel", "region"]]
    out.to_sql("stores", engine, schema="silver", if_exists="append", index=False)
    print(f"Silver stores: {len(out)} rows")


def transform_customers():
    df = pd.read_sql("SELECT * FROM bronze.customers", engine)
    # Dedupe on customer_id, keeping first occurrence
    before = len(df)
    df = df.drop_duplicates(subset=["customer_id"])
    after = len(df)
    print(f"Deduped customers: removed {before - after} duplicate rows")

    df["is_email_missing"] = df["email"].isna() | (df["email"].str.strip() == "")
    df["signup_date"] = parse_messy_date(df["signup_date"])

    out = df[["customer_id", "first_name", "last_name", "email", "signup_date",
              "region", "segment", "churn_status", "is_email_missing"]]
    out.to_sql("customers", engine, schema="silver", if_exists="append", index=False)
    print(f"Silver customers: {len(out)} rows")


def transform_orders():
    df = pd.read_sql("SELECT * FROM bronze.orders", engine)
    df = df.drop_duplicates(subset=["order_id"])
    df["order_date"] = parse_messy_date(df["order_date"])

    valid_customers = pd.read_sql("SELECT customer_id FROM silver.customers", engine)["customer_id"]
    valid_stores = pd.read_sql("SELECT store_id FROM silver.stores", engine)["store_id"]
    before = len(df)
    df = df[df["customer_id"].isin(valid_customers) & df["store_id"].isin(valid_stores)]
    print(f"Dropped {before - len(df)} orders with orphaned customer/store references")

    out = df[["order_id", "customer_id", "store_id", "order_date", "order_status", "payment_method"]]
    out.to_sql("orders", engine, schema="silver", if_exists="append", index=False)
    print(f"Silver orders: {len(out)} rows")


def transform_order_items():
    df = pd.read_sql("SELECT * FROM bronze.order_items", engine)
    df = df.drop_duplicates(subset=["order_item_id"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price_at_sale"] = pd.to_numeric(df["unit_price_at_sale"], errors="coerce")
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce")

    valid_orders = pd.read_sql("SELECT order_id FROM silver.orders", engine)["order_id"]
    valid_products = pd.read_sql("SELECT product_id FROM silver.products", engine)["product_id"]
    before = len(df)
    df = df[df["order_id"].isin(valid_orders) & df["product_id"].isin(valid_products)]
    print(f"Dropped {before - len(df)} order_items with orphaned order/product references")

    out = df[["order_item_id", "order_id", "product_id", "quantity",
              "unit_price_at_sale", "discount_pct"]]
    out.to_sql("order_items", engine, schema="silver", if_exists="append", index=False)
    print(f"Silver order_items: {len(out)} rows")


def main():
    truncate_silver()
    transform_suppliers()
    transform_products()
    transform_stores()
    transform_customers()
    transform_orders()
    transform_order_items()
    print("\nSilver transform complete.")


if __name__ == "__main__":
    main()