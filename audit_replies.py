"""Audit customer-facing replies for leaked internal vocabulary and unbacked prices.

The system's internal status codes (AVAILABLE, RESTOCKED, UNAVAILABLE,
SALE COMPLETED, SALE REJECTED) and its internal figures (cash balance, supplier
cost, margin) must never reach a customer. _sanitize_customer_reply enforces
this in code; this script verifies the enforcement held over a whole run.

It also verifies that every money figure in a reply is backed by that reply's
own ledger-generated "Confirmed order" block. The model was observed corrupting
a $47.50 line into $237.50 between agents, so a price appearing in the prose
that the ledger does not support is a defect.
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


# --- every money figure must be backed by the ledger-generated summary --------
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")


def _normalize(amount: str) -> str:
    """Compare amounts by value, not spelling: $1365.00 and $1,365.00 are equal."""
    return amount.replace(" ", "").replace(",", "")

unbacked = []
for row in results.itertuples():
    reply = str(row.response)
    if "Confirmed order" not in reply:
        # Nothing was sold; no price should be quoted at all.
        for match in MONEY.findall(reply):
            unbacked.append((row.request_id, match, "no sale recorded"))
        continue
    prose, _, summary = reply.partition("Confirmed order")
    backed = {_normalize(m) for m in MONEY.findall(summary)}
    for match in MONEY.findall(prose):
        if _normalize(match) not in backed:
            unbacked.append((row.request_id, match, "not in the confirmed order"))

print(f"prices not backed by the ledger : {len(unbacked)}")
for request_id, amount, why in unbacked:
    print(f"  request {request_id}: {amount} ({why})")
if not unbacked:
    print("\nEvery price shown to a customer is backed by a recorded sale.")
