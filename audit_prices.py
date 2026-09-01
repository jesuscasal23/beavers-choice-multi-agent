"""Audit every recorded sale against the deterministic quote it should have carried.

A sale in the ledger must equal catalog unit price x quantity x (1 - bulk
discount). Any divergence means a customer was charged a price they were never
quoted.
"""
import pandas as pd
from sqlalchemy import create_engine

import project_starter as ps

engine = create_engine("sqlite:///munder_difflin.db")
transactions = pd.read_sql("SELECT rowid, * FROM transactions", engine)
sales = transactions[
    (transactions.transaction_type == "sales")
    & (~transactions.transaction_date.str.startswith("2025-01-01"))
]

mismatches = []
for sale in sales.itertuples():
    quantity = int(sale.units)
    expected = round(
        ps._unit_price(sale.item_name) * quantity * (1 - ps._discount_rate_for(quantity)), 2
    )
    if abs(expected - sale.price) > 0.02:
        mismatches.append((sale.rowid, sale.item_name, quantity, sale.price, expected))

print(f"sales lines audited : {len(sales)}")
print(f"price mismatches    : {len(mismatches)}")
for rowid, name, qty, charged, expected in mismatches:
    print(f"  row {rowid}: {name} x{qty} charged ${charged:.2f}, expected ${expected:.2f}")
if not mismatches:
    print("\nEvery recorded sale matches the price the customer was quoted.")
