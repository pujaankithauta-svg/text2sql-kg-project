-- GOLD LAYER
-- Business-ready star schema: 1 fact table + dimension tables

CREATE TABLE gold.dim_customer (
    customer_key         SERIAL PRIMARY KEY,
    customer_id           TEXT UNIQUE NOT NULL,
    full_name              TEXT,
    email                    TEXT,
    signup_date               DATE,
    region                     TEXT,
    segment                     TEXT,
    churn_status                 TEXT
);

CREATE TABLE gold.dim_product (
    product_key           SERIAL PRIMARY KEY,
    product_id             TEXT UNIQUE NOT NULL,
    product_name             TEXT,
    category                   TEXT,
    subcategory                  TEXT,
    brand                          TEXT,
    unit_cost                        NUMERIC(10,2),
    unit_price                         NUMERIC(10,2),
    margin_pct                           NUMERIC(5,2)
);

CREATE TABLE gold.dim_supplier (
    supplier_key           SERIAL PRIMARY KEY,
    supplier_id              TEXT UNIQUE NOT NULL,
    supplier_name              TEXT,
    country                      TEXT
);

CREATE TABLE gold.dim_store (
    store_key               SERIAL PRIMARY KEY,
    store_id                  TEXT UNIQUE NOT NULL,
    store_name                  TEXT,
    channel                       TEXT,
    region                          TEXT
);

CREATE TABLE gold.dim_date (
    date_key                 INTEGER PRIMARY KEY,   -- format YYYYMMDD
    full_date                  DATE UNIQUE NOT NULL,
    year                          INTEGER,
    quarter                         INTEGER,
    month                             INTEGER,
    month_name                         TEXT,
    day_of_week                          TEXT,
    is_weekend                             BOOLEAN
);

CREATE TABLE gold.fact_orders (
    order_item_key           SERIAL PRIMARY KEY,
    order_id                   TEXT NOT NULL,
    order_item_id                TEXT NOT NULL,
    customer_key                   INTEGER REFERENCES gold.dim_customer(customer_key),
    product_key                      INTEGER REFERENCES gold.dim_product(product_key),
    store_key                          INTEGER REFERENCES gold.dim_store(store_key),
    date_key                             INTEGER REFERENCES gold.dim_date(date_key),
    order_status                           TEXT,
    payment_method                           TEXT,
    quantity                                   INTEGER,
    unit_price_at_sale                           NUMERIC(10,2),
    discount_pct                                   NUMERIC(5,2),
    line_revenue                                     NUMERIC(12,2)
);