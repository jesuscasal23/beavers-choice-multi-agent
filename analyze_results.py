"""Check the evaluation run against the project rubric thresholds.

Financial figures come from test_results.csv. Fulfilment counts come from the
agent trace in run_full.log, which records the actual SALE COMPLETED and
UNAVAILABLE verdicts -- counting those is exact, whereas pattern-matching the
customer-facing prose is a guess.
"""
import os
import re

import pandas as pd

STARTING_CASH = 45_059.70
STARTING_INVENTORY = 4_940.30
LOG_PATH = "run_full.log"

results = pd.read_csv("test_results.csv")
results["cash_delta"] = results["cash_balance"].diff()
results.loc[results.index[0], "cash_delta"] = (
    results.loc[results.index[0], "cash_balance"] - STARTING_CASH
)

# --- fulfilment counts, taken from the agent trace ---------------------------
sold_ids, declined_ids = set(), set()
if os.path.exists(LOG_PATH):
    blocks = re.split(r"^=== Request (\d+) ===", open(LOG_PATH, errors="replace").read(), flags=re.M)
    for i in range(1, len(blocks), 2):
        request_id, body = int(blocks[i]), blocks[i + 1]
        if re.search(r"SALE COMPLETED: \d", body):
            sold_ids.add(request_id)
        if re.search(r"UNAVAILABLE: (?:'|[A-Z0-9])", body):
            declined_ids.add(request_id)

cash_changes = int((results["cash_delta"].abs() > 0.005).sum())
final_cash = results["cash_balance"].iloc[-1]
final_inventory = results["inventory_value"].iloc[-1]

print(f"{'requests processed':<38}{len(results)}")
print(f"{'requests changing cash balance':<38}{cash_changes:<5}(rubric needs >= 3)")
if sold_ids or declined_ids:
    unfulfilled = sorted(set(results.request_id) - sold_ids)
    print(f"{'requests with a recorded sale':<38}{len(sold_ids):<5}(rubric needs >= 3)")
    print(f"{'requests with a declined line':<38}{len(declined_ids)}")
    print(f"{'requests left entirely unfulfilled':<38}{len(unfulfilled):<5}(rubric needs >= 1) {unfulfilled}")
else:
    print(f"  ({LOG_PATH} not found — fulfilment counts unavailable)")

print()
print(f"{'cash balance':<38}${STARTING_CASH:,.2f} -> ${final_cash:,.2f}  ({final_cash - STARTING_CASH:+,.2f})")
print(f"{'inventory value':<38}${STARTING_INVENTORY:,.2f} -> ${final_inventory:,.2f}")
print(f"{'total assets':<38}${STARTING_CASH + STARTING_INVENTORY:,.2f} -> ${final_cash + final_inventory:,.2f}")
print()
print("per-request:")
print(f"  {'id':>3}  {'date':<12}{'cash delta':>12}{'cash':>13}   outcome")
for row in results.itertuples():
    if row.request_id in sold_ids:
        outcome = "sold + declined lines" if row.request_id in declined_ids else "fulfilled"
    elif sold_ids:
        outcome = "declined"
    else:
        outcome = ""
    print(f"  {row.request_id:>3}  {row.request_date:<12}{row.cash_delta:>+12.2f}{row.cash_balance:>13.2f}   {outcome}")
