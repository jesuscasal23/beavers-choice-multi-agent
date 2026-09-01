"""Audit customer-facing replies for leaked internal vocabulary.

The system's internal status codes (AVAILABLE, RESTOCKED, UNAVAILABLE,
SALE COMPLETED, SALE REJECTED) and its internal figures (cash balance, supplier
cost, margin) must never reach a customer. _sanitize_customer_reply enforces
this in code; this script verifies the enforcement held over a whole run.
"""
import re

import pandas as pd

STATUS_CODES = re.compile(
    r"\b(?:UNAVAILABLE|AVAILABLE|RESTOCKED|RESTOCK PLACED|RESTOCK DECLINED|"
    r"SALE COMPLETED|SALE REJECTED|NOT_IN_CATALOG)\b"
)
INTERNAL_TERMS = re.compile(
    r"cash balance|cash reserve|supplier cost|cost of goods|profit margin|"
    r"gross margin|inventory_agent|quoting_agent|sales_agent|orchestrator|"
    r"price correction|Traceback|create_transaction|get_stock_level|"
    r"ensure_stock_available|record_sale",
    re.IGNORECASE,
)

results = pd.read_csv("test_results.csv")
status_hits, term_hits = [], []
for row in results.itertuples():
    reply = str(row.response)
    for match in STATUS_CODES.findall(reply):
        status_hits.append((row.request_id, match))
    for match in INTERNAL_TERMS.findall(reply):
        term_hits.append((row.request_id, match))

print(f"replies audited          : {len(results)}")
print(f"leaked status codes      : {len(status_hits)}")
for request_id, match in status_hits:
    print(f"  request {request_id}: {match}")
print(f"leaked internal terms    : {len(term_hits)}")
for request_id, match in term_hits:
    print(f"  request {request_id}: {match}")

if not status_hits and not term_hits:
    print("\nNo internal status codes or internal figures reached a customer.")
