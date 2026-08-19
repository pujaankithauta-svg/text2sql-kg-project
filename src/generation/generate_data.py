"""
Synthetic enterprise data generator.
Generates customers, products, suppliers, stores, orders, and order_items
with realistic messiness (duplicates, nulls, inconsistent formats) —
mimicking real raw lakehouse landing data.
"""

import random
import csv
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REGIONS = ["North America", "Europe", "APAC", "LATAM", "MEA"]
SEGMENTS = ["Enterprise", "SMB", "Consumer"]
CHURN_STATUSES = ["Active", "Churned", "At Risk"]
CATEGORIES = {
    "Electronics": ["Laptops", "Phones", "Accessories"],
    "Apparel": ["Menswear", "Womenswear", "Footwear"],
    "Home": ["Furniture", "Kitchen", "Decor"],
    "Grocery": ["Beverages", "Snacks", "Fresh Produce"],
}
CHANNELS = ["Online", "Physical Store"]
ORDER_STATUSES = ["Completed", "Cancelled", "Returned", "Pending"]
PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Bank Transfer"]

N_CUSTOMERS = 5000
N_PRODUCTS = 500
N_SUPPLIERS = 60
N_STORES = 25
N_ORDERS = 50000


def random_date_messy(start_year=2023, end_year=2026):
    """Generate dates in inconsistent formats — realistic raw data mess."""
    d = fake.date_between(start_date=f"-{(2026 - start_year) * 365}d", end_date="today")
    fmt_choice = random.random()
    if fmt_choice < 0.7:
        return d.strftime("%Y-%m-%d")
    elif fmt_choice < 0.9:
        return d.strftime("%m/%d/%Y")
    else:
        return d.strftime("%d-%b-%Y")


def generate_customers():
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        email = fake.email() if random.random() > 0.01 else ""  # 1% missing emails
        rows.append({
            "customer_id": f"CUST{i:06d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": email,
            "signup_date": random_date_messy(),
            "region": random.choice(REGIONS),
            "segment": random.choice(SEGMENTS),
            "churn_status": random.choice(CHURN_STATUSES),
        })
    # Inject ~2% duplicate customer records (common in raw enterprise data)
    n_dupes = int(N_CUSTOMERS * 0.02)
    dupes = random.sample(rows, n_dupes)
    rows.extend(dupes)
    random.shuffle(rows)
    return rows


def generate_suppliers():
    rows = []
    for i in range(1, N_SUPPLIERS + 1):
        rows.append({
            "supplier_id": f"SUP{i:04d}",
            "supplier_name": fake.company(),
            "country": fake.country(),
            "contact_email": fake.company_email(),
        })
    return rows


def generate_products(supplier_ids):
    rows = []
    for i in range(1, N_PRODUCTS + 1):
        category = random.choice(list(CATEGORIES.keys()))
        subcategory = random.choice(CATEGORIES[category])
        cost = round(random.uniform(5, 500), 2)
        price = round(cost * random.uniform(1.3, 2.5), 2)
        rows.append({
            "product_id": f"PROD{i:05d}",
            "product_name": f"{fake.word().capitalize()} {subcategory[:-1] if subcategory.endswith('s') else subcategory}",
            "category": category,
            "subcategory": subcategory,
            "brand": fake.company(),
            "unit_cost": str(cost),
            "unit_price": str(price),
            "supplier_id": random.choice(supplier_ids),
        })
    return rows


def generate_stores():
    rows = []
    for i in range(1, N_STORES + 1):
        rows.append({
            "store_id": f"STORE{i:03d}",
            "store_name": f"{fake.city()} {random.choice(['Outlet', 'Flagship', 'Branch'])}",
            "channel": random.choice(CHANNELS),
            "region": random.choice(REGIONS),
        })
    return rows


def generate_orders_and_items(customer_ids, product_ids, store_ids):
    order_rows = []
    item_rows = []
    item_counter = 1

    for i in range(1, N_ORDERS + 1):
        order_id = f"ORD{i:07d}"
        order_rows.append({
            "order_id": order_id,
            "customer_id": random.choice(customer_ids),
            "store_id": random.choice(store_ids),
            "order_date": random_date_messy(),
            "order_status": random.choices(ORDER_STATUSES, weights=[0.75, 0.1, 0.1, 0.05])[0],
            "payment_method": random.choice(PAYMENT_METHODS),
        })

        n_items = random.randint(1, 5)
        for _ in range(n_items):
            item_rows.append({
                "order_item_id": f"ITEM{item_counter:08d}",
                "order_id": order_id,
                "product_id": random.choice(product_ids),
                "quantity": str(random.randint(1, 4)),
                "unit_price_at_sale": str(round(random.uniform(5, 900), 2)),
                "discount_pct": str(random.choice([0, 0, 0, 5, 10, 15, 20])),
            })
            item_counter += 1

    return order_rows, item_rows


def write_csv(rows, filename):
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {filepath}")


def main():
    print("Generating suppliers...")
    suppliers = generate_suppliers()
    write_csv(suppliers, "suppliers.csv")

    print("Generating products...")
    supplier_ids = [s["supplier_id"] for s in suppliers]
    products = generate_products(supplier_ids)
    write_csv(products, "products.csv")

    print("Generating stores...")
    stores = generate_stores()
    write_csv(stores, "stores.csv")

    print("Generating customers...")
    customers = generate_customers()
    write_csv(customers, "customers.csv")

    print("Generating orders and order items...")
    customer_ids = [c["customer_id"] for c in customers]
    product_ids = [p["product_id"] for p in products]
    store_ids = [s["store_id"] for s in stores]
    orders, order_items = generate_orders_and_items(customer_ids, product_ids, store_ids)
    write_csv(orders, "orders.csv")
    write_csv(order_items, "order_items.csv")

    print("\nDone. All CSVs written to data/raw/")


if __name__ == "__main__":
    main()