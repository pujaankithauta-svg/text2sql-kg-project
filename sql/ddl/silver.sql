-- SILVER LAYER
-- Cleaned, deduplicated, properly typed tables

CREATE TABLE silver.customers (
    customer_id         TEXT PRIMARY KEY,
    first_name           TEXT,
    last_name            TEXT,
    email                TEXT,
    signup_date          DATE,
    region               TEXT,
    segment              TEXT,
    churn_status         TEXT,
    is_email_missing     BOOLEAN,
    _loaded_at           TIMESTAMP DEFAULT now()
);

CREATE TABLE silver.suppliers (
    supplier_id          TEXT PRIMARY KEY,
    supplier_name        TEXT,
    country               TEXT,
    contact_email        TEXT,
    _loaded_at            TIMESTAMP DEFAULT now()
);

CREATE TABLE silver.products (
    product_id           TEXT PRIMARY KEY,
    product_name         TEXT,
    category             TEXT,
    subcategory          TEXT,
    brand                TEXT,
    unit_cost            NUMERIC(10,2),
    unit_price           NUMERIC(10,2),
    supplier_id          TEXT REFERENCES silver.suppliers(supplier_id),
    _loaded_at            TIMESTAMP DEFAULT now()
);

CREATE TABLE silver.stores (
    store_id              TEXT PRIMARY KEY,
    store_name            TEXT,
    channel                TEXT,
    region                 TEXT,
    _loaded_at              TIMESTAMP DEFAULT now()
);

CREATE TABLE silver.orders (
    order_id               TEXT PRIMARY KEY,
    customer_id            TEXT REFERENCES silver.customers(customer_id),
    store_id                TEXT REFERENCES silver.stores(store_id),
    order_date               DATE,
    order_status              TEXT,
    payment_method              TEXT,
    _loaded_at                   TIMESTAMP DEFAULT now()
);

CREATE TABLE silver.order_items (
    order_item_id             TEXT PRIMARY KEY,
    order_id                   TEXT REFERENCES silver.orders(order_id),
    product_id                  TEXT REFERENCES silver.products(product_id),
    quantity                     INTEGER,
    unit_price_at_sale             NUMERIC(10,2),
    discount_pct                    NUMERIC(5,2),
    _loaded_at                       TIMESTAMP DEFAULT now()
);