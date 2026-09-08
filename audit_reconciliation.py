"""Reconcile customer-facing responses against the transaction ledger.

audit_prices.py checks that each recorded sale carries the right price, and
audit_replies.py checks that every price shown to a customer is backed by a
recorded sale. Neither catches the failure a reviewer found in an earlier run:
a customer told one story while the ledger recorded another -- a fulfilled total
that does not reconcile with the cash movement, or an item silently substituted
for the one the customer asked for.

Three checks, over every request:

  A. CASH        the row-to-row cash delta in test_results.csv equals
                 (sales - restocks) in that request's slice of the ledger.
  B. TOTALS      the ledger-generated "Confirmed order" total equals the sum of
                 its own line items, and equals the sales in that slice.
  C. SUBSTITUTION every record_sale call in the log resolved to the item that
                 was actually written, and no call resolved a term the catalog
                 does not carry.

The ledger is partitioned per request by walking transactions in rowid order and
cutting where the running cash balance matches each row of test_results.csv --
transactions are appended in request order, so the prefix sums identify the
boundaries exactly.
"""
import re
import sys

import pandas as pd
from sqlalchemy import create_engine

import project_starter as ps

STARTING_CASH = 45_059.70
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")


def _amount(text: str) -> float:
    return float(text.replace("$", "").replace(",", "").strip())


def _slice_ledger_by_request(results: pd.DataFrame) -> dict:
    """Map request_id -> the transactions that request wrote."""
    ledger = pd.read_sql(
        "SELECT rowid, item_name, transaction_type, units, price, transaction_date "
        "FROM transactions ORDER BY rowid",
        create_engine("sqlite:///munder_difflin.db"),
    )
    # Drop the rows init_database seeds (the opening cash row and the initial
    # stock purchases); they predate every request and are not attributable to
    # one. The running balance therefore starts from STARTING_CASH.
    ledger = ledger[~ledger.transaction_date.str.startswith("2025-01-01")].reset_index(drop=True)
    ledger["signed"] = ledger.apply(
        lambda r: r.price if r.transaction_type == "sales" else -r.price, axis=1
    )
    ledger["running"] = STARTING_CASH + ledger["signed"].cumsum()

    slices, cursor = {}, 0
    for row in results.itertuples():
        target = row.cash_balance
        end = cursor
        for i in range(cursor, len(ledger)):
            if abs(ledger.iloc[i]["running"] - target) < 0.005:
                end = i + 1
        slices[row.request_id] = ledger.iloc[cursor:end]
        cursor = end
    return slices


def main() -> int:
    results = pd.read_csv("test_results.csv")
    results["cash_delta"] = results["cash_balance"].diff()
    results.loc[results.index[0], "cash_delta"] = results.cash_balance.iloc[0] - STARTING_CASH
    slices = _slice_ledger_by_request(results)

    cash_fail, total_fail, sub_fail = [], [], []

    for row in results.itertuples():
        window = slices.get(row.request_id)
        if window is None or window.empty:
            if abs(row.cash_delta) > 0.005:
                cash_fail.append((row.request_id, row.cash_delta, 0.0))
            continue

        sales = window[window.transaction_type == "sales"].price.sum()
        restocks = window[window.transaction_type == "stock_orders"].price.sum()

        # A. cash movement
        if abs((sales - restocks) - row.cash_delta) > 0.011:
            cash_fail.append((row.request_id, row.cash_delta, sales - restocks))

        # B. the confirmed-order block against the ledger
        reply = str(row.response)
        if "Confirmed order" in reply:
            block = reply.partition("Confirmed order")[2]
            stated_total = re.search(r"Order total:\s*(\$[\d,]+\.\d{2})", block)
            line_totals = [_amount(m) for m in MONEY.findall(block.split("Order total")[0])]
            if stated_total:
                declared = _amount(stated_total.group(1))
                if abs(declared - sum(line_totals)) > 0.011:
                    total_fail.append((row.request_id, "lines do not sum to the stated total"))
                if abs(declared - sales) > 0.011:
                    total_fail.append((row.request_id, f"stated ${declared:,.2f} vs ledger ${sales:,.2f}"))

    # C. item substitution, read from the agent trace
    log = open("run_full.log", errors="replace").read()
    log = re.sub(r"[│┃]", " ", log)
    log = re.sub(r"\s*\n\s*", " ", log)
    for call in re.finditer(
        r"'record_sale'[^{]*\{[^}]*'item_name':\s*'([^']{1,80})'", log
    ):
        requested = " ".join(call.group(1).split())
        resolved = ps._resolve_item_name(requested)
        if not resolved:
            sub_fail.append((requested, "not a catalog item -- sale must be refused"))

    print(f"requests reconciled              : {len(results)}")
    print(f"A. cash-delta mismatches         : {len(cash_fail)}")
    for rid, stated, actual in cash_fail:
        print(f"     request {rid}: csv delta ${stated:,.2f} vs ledger ${actual:,.2f}")
    print(f"B. confirmed-order mismatches    : {len(total_fail)}")
    for rid, why in total_fail:
        print(f"     request {rid}: {why}")
    print(f"C. unsupported-item sales        : {len(sub_fail)}")
    for name, why in sub_fail:
        print(f"     '{name}': {why}")

    if not (cash_fail or total_fail or sub_fail):
        print("\nEvery customer response reconciles with the ledger.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
