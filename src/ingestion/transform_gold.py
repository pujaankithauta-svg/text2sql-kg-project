"""
Transforms silver -> gold: builds the star schema.
Computes derived business metrics (margin_pct, line_revenue)
and generates a proper date dimension.
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


def truncate_gold():
    with engine.begin() as conn:
        for table in ["fact_orders", "dim_date", "dim_store", "dim_supplier",
                      "dim_product", "dim_customer"]:
            conn.execute(text(f"TRUNCATE TABLE gold.{table} CASCADE"))
    print("Truncated all gold tables.")


def build_dim_customer():
    df = pd.read_sql("SELECT * FROM silver.customers", engine)
    df["full_name"] = df["first_name"] + " " + df["last_name"]
    out = df[["customer_id", "full_name", "email", "signup_date", "region",
              "segment", "churn_status"]]
    out.to_sql("dim_customer", engine, schema="gold", if_exists="append", index=False)
    print(f"gold.dim_customer: {len(out)} rows")


def build_dim_supplier():
    df = pd.read_sql("SELECT * FROM silver.suppliers", engine)
    out = df[["supplier_id", "supplier_name", "country"]]
    out.to_sql("dim_supplier", engine, schema="gold", if_exists="append", index=False)
    print(f"gold.dim_supplier: {len(out)} rows")


def build_dim_product():
    df = pd.read_sql("SELECT * FROM silver.products", engine)
    df["margin_pct"] = ((df["unit_price"] - df["unit_cost"]) / df["unit_price"] * 100).round(2)
    out = df[["product_id", "product_name", "category", "subcategory", "brand",
              "unit_cost", "unit_price", "margin_pct"]]
    out.to_sql("dim_product", engine, schema="gold", if_exists="append", index=False)
    print(f"gold.dim_product: {len(out)} rows")


def build_dim_store():
    df = pd.read_sql("SELECT * FROM silver.stores", engine)
    out = df[["store_id", "store_name", "channel", "region"]]
    out.to_sql("dim_store", engine, schema="gold", if_exists="append", index=False)
    print(f"gold.dim_store: {len(out)} rows")


def build_dim_date():
    orders_dates = pd.read_sql("SELECT DISTINCT order_date FROM silver.orders WHERE order_date IS NOT NULL", engine)
    dates = pd.to_datetime(orders_dates["order_date"])

    df = pd.DataFrame({"full_date": dates.sort_values().unique()})
    df["full_date"] = pd.to_datetime(df["full_date"])
    df["date_key"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"] = df["full_date"].dt.year
    df["quarter"] = df["full_date"].dt.quarter
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.strftime("%B")
    df["day_of_week"] = df["full_date"].dt.strftime("%A")
    df["is_weekend"] = df["full_date"].dt.dayofweek.isin([5, 6])

    out = df[["date_key", "full_date", "year", "quarter", "month",
              "month_name", "day_of_week", "is_weekend"]]
    out.to_sql("dim_date", engine, schema="gold", if_exists="append", index=False)
    print(f"gold.dim_date: {len(out)} rows")


def build_fact_orders():
    orders = pd.read_sql("SELECT * FROM silver.orders", engine)
    items = pd.read_sql("SELECT * FROM silver.order_items", engine)

    dim_customer = pd.read_sql("SELECT customer_key, customer_id FROM gold.dim_customer", engine)
    dim_product = pd.read_sql("SELECT product_key, product_id FROM gold.dim_product", engine)
    dim_store = pd.read_sql("SELECT store_key, store_id FROM gold.dim_store", engine)
    dim_date = pd.read_sql("SELECT date_key, full_date FROM gold.dim_date", engine)
    dim_date["full_date"] = pd.to_datetime(dim_date["full_date"])

    fact = items.merge(orders, on="order_id", how="inner")
    fact["order_date"] = pd.to_datetime(fact["order_date"])

    fact = fact.merge(dim_customer, on="customer_id", how="inner")
    fact = fact.merge(dim_product, on="product_id", how="inner")
    fact = fact.merge(dim_store, on="store_id", how="inner")
    fact = fact.merge(dim_date, left_on="order_date", right_on="full_date", how="inner")

    fact["line_revenue"] = (fact["quantity"] * fact["unit_price_at_sale"] *
                             (1 - fact["discount_pct"] / 100)).round(2)

    out = fact[["order_id", "order_item_id", "customer_key", "product_key",
                "store_key", "date_key", "order_status", "payment_method",
                "quantity", "unit_price_at_sale", "discount_pct", "line_revenue"]]
    out.to_sql("fact_orders", engine, schema="gold", if_exists="append", index=False)
    print(f"gold.fact_orders: {len(out)} rows")


def main():
    truncate_gold()
    build_dim_customer()
    build_dim_supplier()
    build_dim_product()
    build_dim_store()
    build_dim_date()
    build_fact_orders()
    print("\nGold transform complete.")


if __name__ == "__main__":
    main()