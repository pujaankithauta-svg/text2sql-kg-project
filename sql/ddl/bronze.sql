-- BRONZE LAYER
-- Raw landing tables — loose typing, lineage columns, minimal validation

CREATE TABLE bronze.customers (
    customer_id         TEXT,
    first_name           TEXT,
    last_name            TEXT,
    email                TEXT,
    signup_date          TEXT,
    region               TEXT,
    segment              TEXT,
    churn_status         TEXT,
    _source_file         TEXT,
    _loaded_at           TIMESTAMP DEFAULT now()
);

CREATE TABLE bronze.products (
    product_id           TEXT,
    product_name         TEXT,
    category             TEXT,
    subcategory          TEXT,
    brand                TEXT,
    unit_cost            TEXT,
    unit_price           TEXT,
    supplier_id          TEXT,
    _source_file         TEXT,
    _loaded_at           TIMESTAMP DEFAULT now()
);

CREATE TABLE bronze.suppliers (
    supplier_id          TEXT,
    supplier_name        TEXT,
    country               TEXT,
    contact_email        TEXT,
    _source_file          TEXT,
    _loaded_at            TIMESTAMP DEFAULT now()
);

CREATE TABLE bronze.stores (
    store_id              TEXT,
    store_name            TEXT,
    channel                TEXT,
    region                 TEXT,
    _source_file           TEXT,
    _loaded_at             TIMESTAMP DEFAULT now()
);

CREATE TABLE bronze.orders (
    order_id               TEXT,
    customer_id            TEXT,
    store_id                TEXT,
    order_date               TEXT,
    order_status             TEXT,
    payment_method            TEXT,
    _source_file              TEXT,
    _loaded_at                TIMESTAMP DEFAULT now()
);

CREATE TABLE bronze.order_items (
    order_item_id             TEXT,
    order_id                   TEXT,
    product_id                  TEXT,
    quantity                     TEXT,
    unit_price_at_sale            TEXT,
    discount_pct                   TEXT,
    _source_file                    TEXT,
    _loaded_at                       TIMESTAMP DEFAULT now()
);