"""
Loads raw CSVs from data/raw/ into the bronze schema in Postgres.
Bronze = raw as-is, minimal transformation, lineage columns added.
"""

import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")
PG_DB = os.getenv("POSTGRES_DB")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

# Maps CSV filename -> target bronze table name
FILE_TABLE_MAP = {
    "suppliers.csv": "suppliers",
    "products.csv": "products",
    "stores.csv": "stores",
    "customers.csv": "customers",
    "orders.csv": "orders",
    "order_items.csv": "order_items",
}


def load_file(csv_filename, table_name):
    filepath = RAW_DIR / csv_filename
    df = pd.read_csv(filepath, dtype=str)  # keep everything as string for bronze
    df["_source_file"] = csv_filename

    df.to_sql(
        table_name,
        engine,
        schema="bronze",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000,
    )
    print(f"Loaded {len(df)} rows into bronze.{table_name}")


def main():
    for csv_filename, table_name in FILE_TABLE_MAP.items():
        load_file(csv_filename, table_name)
    print("\nBronze load complete.")


if __name__ == "__main__":
    main()