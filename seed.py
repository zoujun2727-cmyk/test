"""Create and populate analytics.db with a sample e-commerce dataset.

Generates a small but realistic relational dataset so the dashboard has
something to query out of the box:

    customers   - who is buying
    products    - what is for sale (with categories)
    orders      - one row per order, tied to a customer and a date
    order_items - line items, tied to an order and a product

Data is randomized but seeded, so re-running produces the same database.
Run:  python3 seed.py
"""

from __future__ import annotations

import datetime as dt
import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("analytics.db")
RNG = random.Random(42)

CATEGORIES = {
    "Electronics": ["Headphones", "USB-C Cable", "Webcam", "Mechanical Keyboard", "Monitor"],
    "Home": ["Desk Lamp", "Coffee Mug", "Throw Blanket", "Wall Clock", "Plant Pot"],
    "Office": ["Notebook", "Gel Pens (12pk)", "Stapler", "Desk Organizer", "Whiteboard"],
    "Fitness": ["Yoga Mat", "Resistance Bands", "Water Bottle", "Jump Rope", "Dumbbell Set"],
}

COUNTRIES = ["US", "US", "US", "UK", "Germany", "Canada", "Australia", "India"]
CHANNELS = ["organic", "paid_search", "social", "email", "referral"]


def build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            id           INTEGER PRIMARY KEY,
            name         TEXT    NOT NULL,
            country      TEXT    NOT NULL,
            signup_date  TEXT    NOT NULL,
            channel      TEXT    NOT NULL
        );

        CREATE TABLE products (
            id        INTEGER PRIMARY KEY,
            name      TEXT    NOT NULL,
            category  TEXT    NOT NULL,
            price     REAL    NOT NULL
        );

        CREATE TABLE orders (
            id           INTEGER PRIMARY KEY,
            customer_id  INTEGER NOT NULL REFERENCES customers(id),
            order_date   TEXT    NOT NULL,
            status       TEXT    NOT NULL
        );

        CREATE TABLE order_items (
            id          INTEGER PRIMARY KEY,
            order_id    INTEGER NOT NULL REFERENCES orders(id),
            product_id  INTEGER NOT NULL REFERENCES products(id),
            quantity    INTEGER NOT NULL,
            unit_price  REAL    NOT NULL
        );
        """
    )


def seed(conn: sqlite3.Connection) -> None:
    # Products
    products = []
    pid = 1
    for category, names in CATEGORIES.items():
        for name in names:
            price = round(RNG.uniform(8, 220), 2)
            products.append((pid, name, category, price))
            pid += 1
    conn.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    # Customers, signing up across the last ~12 months.
    today = dt.date(2026, 6, 1)
    customers = []
    first_names = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley",
                   "Jamie", "Avery", "Quinn", "Drew", "Robin", "Skyler", "Cameron"]
    last_names = ["Lee", "Patel", "Garcia", "Smith", "Kim", "Müller", "Singh",
                  "Brown", "Nguyen", "Rossi", "Khan", "Costa"]
    for cid in range(1, 301):
        signup_offset = RNG.randint(0, 365)
        signup = today - dt.timedelta(days=signup_offset)
        name = f"{RNG.choice(first_names)} {RNG.choice(last_names)}"
        customers.append(
            (cid, name, RNG.choice(COUNTRIES), signup.isoformat(), RNG.choice(CHANNELS))
        )
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # Orders + line items. Customers order after they sign up.
    orders = []
    items = []
    oid = 1
    iid = 1
    for cid, _name, _country, signup_iso, _channel in customers:
        signup = dt.date.fromisoformat(signup_iso)
        n_orders = RNG.choices([0, 1, 2, 3, 4, 5], weights=[2, 5, 5, 3, 2, 1])[0]
        for _ in range(n_orders):
            max_gap = (today - signup).days
            if max_gap <= 0:
                continue
            order_date = signup + dt.timedelta(days=RNG.randint(0, max_gap))
            status = RNG.choices(
                ["completed", "completed", "completed", "refunded", "cancelled"],
                weights=[6, 6, 6, 1, 1],
            )[0]
            orders.append((oid, cid, order_date.isoformat(), status))

            for _ in range(RNG.randint(1, 4)):
                product = RNG.choice(products)
                qty = RNG.randint(1, 3)
                items.append((iid, oid, product[0], qty, product[3]))
                iid += 1
            oid += 1

    conn.executemany("INSERT INTO orders VALUES (?,?,?,?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        build_schema(conn)
        seed(conn)
        conn.commit()
        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("customers", "products", "orders", "order_items")
        }
    finally:
        conn.close()
    print(f"Created {DB_PATH.name}:")
    for table, n in counts.items():
        print(f"  {table:<12} {n:>6} rows")


if __name__ == "__main__":
    main()
