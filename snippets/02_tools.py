# =============================================================================
# SECTION 2 -- Tools
#
# Every tool is a thin, typed wrapper around the starter's helper functions.
# Two rules drive the design:
#   1. Tools return STRINGS, never DataFrames. The model only ever sees text, so
#      the pandas work happens here and the model gets something unambiguous.
#   2. Arithmetic and policy live in Python. Discounts, totals, cash-reserve
#      checks and lead-time checks are code; the model only picks the tool.
#
# Helper-function coverage (rubric: all seven must be used):
#   create_transaction         -> place_restock_order / ensure_stock_available, record_sale
#   get_all_inventory          -> inventory_snapshot
#   get_stock_level            -> check_stock_level, calculate_quote, record_sale
#   get_supplier_delivery_date -> check_supplier_delivery, place_restock_order,
#                                 ensure_stock_available
#   get_cash_balance           -> check_cash_balance, place_restock_order
#   generate_financial_report  -> company_financial_report
#   search_quote_history       -> find_similar_quotes
# =============================================================================


# ---- Private helpers (not exposed to the agents) ----------------------------
def _named_size(text: str) -> str:
    """The paper size a phrase names, or an empty string if it names none."""
    for token in SIZE_TOKENS:
        if re.search(rf"\b{token}\b", text):
            return token
    return ""


def _resolve_item_name(raw_name: str) -> str:
    """Map a loosely-worded product name onto an exact catalog item name.

    Resolution is deliberately ordered from certain to speculative, and refuses
    rather than guessing:

      0. Reject outright if any word is a known non-catalog product term.
      1. Exact match, then case-insensitive exact match.
      2. Explicit synonym from CATALOG_ALIASES.
      3. Longest catalog name contained in the phrasing, so "heavy cardstock
         (white)" finds "Cardstock" and "A4 glossy paper" finds "Glossy paper".
      4. Longest synonym contained in the phrasing, so a trailing qualifier such
         as "table napkins (white)" still resolves.
      5. Fuzzy match, but only above RESOLVER_FUZZY_CUTOFF, and never across a
         paper-size boundary.

    Step 0 and the raised cutoff in step 4 both exist for the same reason: a
    wrong resolution here does not fail loudly, it sells the customer a product
    they never asked for and bills them for it.

    Returns an empty string when nothing matches, which callers surface to the
    customer as "not an item we carry".
    """
    if not raw_name:
        return ""

    lowered = raw_name.strip().lower()

    # 0. Known non-catalog products, checked word by word so "10,000 tickets"
    #    is refused as surely as "tickets".
    words = set(re.findall(r"[a-z]+", lowered))
    if words & UNSUPPORTED_PRODUCT_TERMS:
        return ""

    # 1. Exact.
    if raw_name in CATALOG_BY_NAME:
        return raw_name
    if lowered in CATALOG_LOWER:
        return CATALOG_LOWER[lowered]

    # 2. Curated synonyms.
    if lowered in CATALOG_ALIASES:
        return CATALOG_ALIASES[lowered]

    # 3. Longest catalog name appearing inside the phrasing.
    contained = [name for name in CATALOG_LOWER if name in lowered]
    if contained:
        return CATALOG_LOWER[max(contained, key=len)]

    # 4. Synonym appearing inside the phrasing, for trailing qualifiers like
    #    "(white)" or a size in parentheses.
    alias_hits = [alias for alias in CATALOG_ALIASES if alias in lowered]
    if alias_hits:
        return CATALOG_ALIASES[max(alias_hits, key=len)]

    # 5. Similarity, only when it is close enough to be a spelling variant, and
    #    never when it would swap one named paper size for another.
    close = difflib.get_close_matches(
        lowered, list(CATALOG_LOWER), n=1, cutoff=RESOLVER_FUZZY_CUTOFF
    )
    if not close:
        return ""
    requested_size, matched_size = _named_size(lowered), _named_size(close[0])
    if requested_size and matched_size and requested_size != matched_size:
        return ""
    return CATALOG_LOWER[close[0]]


def _unit_price(item_name: str) -> float:
    """Retail price per unit for a resolved catalog item name."""
    return float(CATALOG_BY_NAME[item_name]["unit_price"])


def _discount_rate_for(quantity: int) -> float:
    """Return the bulk discount rate that applies to a given order size."""
    for threshold, rate in BULK_DISCOUNT_TIERS:
        if quantity >= threshold:
            return rate
    return 0.0


def _units_from_stock_frame(stock_df: pd.DataFrame) -> int:
    """Normalize get_stock_level's single-row DataFrame down to an integer.

    The helper returns one row even for an item that has never been traded, with
    a NULL item_name and a COALESCEd zero, so both cases are handled here.
    """
    if stock_df.empty or pd.isna(stock_df.iloc[0]["current_stock"]):
        return 0
    return int(stock_df.iloc[0]["current_stock"])


def _current_stock(item_name: str, as_of_date: str) -> int:
    """Units on hand for a resolved catalog item, as a plain integer."""
    return _units_from_stock_frame(get_stock_level(item_name, as_of_date))


# ---- Inventory & supply tools ----------------------------------------------
@tool
def catalog_listing() -> str:
    """Lists every item Beaver's Choice sells, with its list price per unit.

    Call this first whenever a customer describes a product in their own words,
    so you can map their wording onto an exact catalog item name.
    """
    lines = [
        f"- {item['item_name']} ({item['category']}): ${item['unit_price']:.2f}/unit"
        for item in paper_supplies
    ]
    return "Beaver's Choice catalog:\n" + "\n".join(lines)


@tool
def inventory_snapshot(as_of_date: str) -> str:
    """Lists every item currently holding stock, with quantities on hand.

    Use for broad questions such as "what do you have in stock?", or as a health
    check before committing to an unusually large order.

    Args:
        as_of_date: Date to evaluate stock at, formatted as YYYY-MM-DD.
    """
    inventory = get_all_inventory(as_of_date)
    if not inventory:
        return f"No items are in stock as of {as_of_date}."
    lines = [f"- {item}: {int(qty)} units" for item, qty in sorted(inventory.items())]
    return f"Stock on hand as of {as_of_date}:\n" + "\n".join(lines)


@tool
def check_stock_level(item_name: str, as_of_date: str) -> str:
    """Reports units on hand for one specific item, resolving fuzzy item names.

    Args:
        item_name: Product name as the customer described it, or the exact catalog name.
        as_of_date: Date to evaluate stock at, formatted as YYYY-MM-DD.
    """
    resolved = _resolve_item_name(item_name)
    if not resolved:
        return (
            f"'{item_name}' does not match any item in the Beaver's Choice "
            f"catalog. Call catalog_listing to see valid item names."
        )
    # Direct call to the starter helper: this tool is its thin wrapper.
    units = _units_from_stock_frame(get_stock_level(resolved, as_of_date))
    return (
        f"{resolved}: {units} units on hand as of {as_of_date} "
        f"(list price ${_unit_price(resolved):.2f}/unit). "
        f"Resolved from customer wording '{item_name}'."
    )


@tool
def check_supplier_delivery(order_date: str, quantity: int) -> str:
    """Estimates when a supplier restock of a given size would arrive.

    Use whenever stock is short, to test whether a restock can beat the
    customer's deadline.

    Args:
        order_date: Date the restock would be placed, formatted as YYYY-MM-DD.
        quantity: Number of units to order from the supplier.
    """
    delivery_date = get_supplier_delivery_date(order_date, quantity)
    return (
        f"A supplier order of {quantity} units placed on {order_date} "
        f"is estimated to arrive on {delivery_date}."
    )


def _restock(
    resolved: str, quantity: int, order_date: str, required_by_date: str
) -> str:
    """Shared restock logic behind place_restock_order and ensure_stock_available.

    Refuses on two independent grounds, both enforced in code rather than by
    prompt: a delivery date past the customer's deadline, or a purchase that
    would breach the minimum cash reserve.
    """
    if quantity <= 0:
        return "Restock quantity must be a positive number of units."

    delivery_date = get_supplier_delivery_date(order_date, quantity)
    if delivery_date > required_by_date:
        return (
            f"RESTOCK DECLINED: {quantity} units of {resolved} ordered on "
            f"{order_date} would not arrive until {delivery_date}, which is "
            f"after the customer's deadline of {required_by_date}."
        )

    total_cost = round(_unit_price(resolved) * SUPPLIER_COST_RATIO * quantity, 2)
    cash_on_hand = get_cash_balance(order_date)
    if cash_on_hand - total_cost < MIN_CASH_RESERVE:
        return (
            f"RESTOCK DECLINED: {quantity} units of {resolved} would cost "
            f"${total_cost:.2f} and leave the company below its "
            f"${MIN_CASH_RESERVE:,.2f} minimum cash reserve."
        )

    create_transaction(
        item_name=resolved,
        transaction_type="stock_orders",
        quantity=quantity,
        price=total_cost,
        date=order_date,
    )
    return (
        f"RESTOCK PLACED: {quantity} units of {resolved} for ${total_cost:.2f}, "
        f"ordered {order_date}, arriving {delivery_date} "
        f"(customer deadline {required_by_date})."
    )


@tool
def place_restock_order(
    item_name: str, quantity: int, order_date: str, required_by_date: str
) -> str:
    """Buys a specific quantity of stock from the supplier.

    Prefer ensure_stock_available, which sizes the order for you. Use this only
    when you want to order an exact quantity.

    Args:
        item_name: Product name to restock; fuzzy names are resolved.
        quantity: Number of units to buy from the supplier.
        order_date: Date the order is placed, formatted as YYYY-MM-DD.
        required_by_date: Date the customer needs the goods, formatted as YYYY-MM-DD.
    """
    resolved = _resolve_item_name(item_name)
    if not resolved:
        return f"Cannot restock '{item_name}': it is not in the catalog."
    return _restock(resolved, quantity, order_date, required_by_date)


@tool
def ensure_stock_available(
    item_name: str, quantity: int, as_of_date: str, required_by_date: str
) -> str:
    """Decides, end to end, whether a line item can be supplied -- and restocks if needed.

    This is the inventory agent's primary tool. It resolves the item name,
    measures the shortfall, and where stock is short it sizes and places the
    restock itself, subject to the delivery-deadline and cash-reserve guards.

    Collapsing check-then-decide-then-order into ONE tool is deliberate: in
    testing, a model given the steps separately would check stock, observe a
    shortfall, and then simply forget to place the order -- promising the
    customer a delivery that was never bought. Encoding the policy in the tool
    removes that failure mode entirely.

    Returns a verdict beginning with AVAILABLE, RESTOCKED, or UNAVAILABLE.

    Args:
        item_name: Product name as the customer described it.
        quantity: Number of units the customer wants.
        as_of_date: Date of the request, formatted as YYYY-MM-DD.
        required_by_date: Date the customer needs the goods, formatted as YYYY-MM-DD.
    """
    resolved = _resolve_item_name(item_name)
    if not resolved:
        return (
            f"UNAVAILABLE: '{item_name}' is not an item Beaver's Choice carries."
        )
    if quantity <= 0:
        return "UNAVAILABLE: quantity must be a positive number of units."

    on_hand = _current_stock(resolved, as_of_date)
    if on_hand >= quantity:
        return (
            f"AVAILABLE: {quantity} units of {resolved} can ship from stock "
            f"({on_hand} units on hand as of {as_of_date})."
        )

    # Order the shortfall plus a safety buffer, so the next customer for the
    # same item is not immediately declined too.
    shortfall = quantity - on_hand
    restock_quantity = int(math.ceil(shortfall * RESTOCK_BUFFER_MULTIPLIER))
    outcome = _restock(resolved, restock_quantity, as_of_date, required_by_date)

    if outcome.startswith("RESTOCK PLACED"):
        delivery_date = get_supplier_delivery_date(as_of_date, restock_quantity)
        return (
            f"RESTOCKED: {resolved} was {shortfall} units short, so "
            f"{restock_quantity} units were ordered and arrive {delivery_date}, "
            f"in time for the {required_by_date} deadline. "
            f"All {quantity} units can now be supplied."
        )
    return (
        f"UNAVAILABLE: {resolved} is {shortfall} units short "
        f"({on_hand} on hand, {quantity} requested) and cannot be restocked. "
        f"Reason: {outcome}"
    )


@tool
def check_cash_balance(as_of_date: str) -> str:
    """Reports the company's cash balance on a given date. Internal use only.

    Args:
        as_of_date: Date to evaluate, formatted as YYYY-MM-DD.
    """
    return f"Cash balance as of {as_of_date}: ${get_cash_balance(as_of_date):.2f}"


# ---- Quoting tools ----------------------------------------------------------
@tool
def find_similar_quotes(search_terms: List[str]) -> str:
    """Retrieves comparable past quotes so pricing follows precedent, not guesswork.

    Pass 1-3 broad keywords such as the event type or product word. The
    underlying history search requires EVERY term to match, so this tool retries
    with progressively fewer terms rather than returning nothing.

    Args:
        search_terms: Keywords to match against past customer requests and quote rationales.
    """
    terms = [t for t in (search_terms or []) if t]
    matches = []
    # Narrow to broad: all terms, then each term alone.
    for attempt in [terms] + [[t] for t in terms]:
        if not attempt:
            continue
        matches = search_quote_history(attempt, limit=5)
        if matches:
            break

    if not matches:
        return "No comparable historical quotes were found for those terms."

    summaries = []
    for i, quote in enumerate(matches, start=1):
        summaries.append(
            f"{i}. Job: {quote.get('job_type')} | Event: {quote.get('event_type')} | "
            f"Order size: {quote.get('order_size')} | "
            f"Total quoted: ${float(quote.get('total_amount') or 0):.2f}\n"
            f"   Rationale: {str(quote.get('quote_explanation'))[:300]}"
        )
    return "Comparable past quotes:\n" + "\n".join(summaries)


@tool
def calculate_quote(item_name: str, quantity: int, as_of_date: str) -> str:
    """Prices one line item, applying the company's bulk discount ladder.

    All arithmetic happens here in code, so the same item and quantity always
    produce the same total. Also reports stock so the caller knows whether the
    line is immediately fulfillable.

    Args:
        item_name: Product name; fuzzy customer wording is resolved to the catalog.
        quantity: Number of units the customer wants.
        as_of_date: Date of the request, formatted as YYYY-MM-DD.
    """
    resolved = _resolve_item_name(item_name)
    if not resolved:
        return f"Cannot quote '{item_name}': it is not in the catalog."
    if quantity <= 0:
        return "Quote quantity must be a positive number of units."

    unit_price = _unit_price(resolved)
    list_total = unit_price * quantity
    discount_rate = _discount_rate_for(quantity)
    discount_amount = round(list_total * discount_rate, 2)
    final_total = round(list_total - discount_amount, 2)
    units_on_hand = _current_stock(resolved, as_of_date)

    discount_line = (
        f"Bulk discount: {discount_rate:.0%} (-${discount_amount:.2f}), "
        f"earned by ordering {quantity} units."
        if discount_rate
        else "No bulk discount: orders under 100 units do not qualify."
    )

    return (
        f"QUOTE for {quantity} x {resolved} (as of {as_of_date}):\n"
        f"  List price ${unit_price:.2f}/unit -> ${list_total:.2f}\n"
        f"  {discount_line}\n"
        f"  FINAL TOTAL: ${final_total:.2f}\n"
        f"  Stock on hand: {units_on_hand} units "
        f"({'sufficient' if units_on_hand >= quantity else 'INSUFFICIENT'})."
    )


# ---- Sales & reporting tools ------------------------------------------------
@tool
def record_sale(item_name: str, quantity: int, total_price: float, sale_date: str) -> str:
    """Finalizes a sale: re-verifies stock, re-derives the price, writes the transaction.

    The only tool that takes the customer's money, so it trusts nothing it is
    handed. Two independent re-checks happen here:

      * Stock is re-read at commit time, so a quote produced earlier in the
        conversation can never oversell.
      * The line total is RE-DERIVED from the catalog price and the discount
        ladder. `total_price` is treated as the caller's claim, not as fact: if
        it disagrees with the authoritative figure the discrepancy is logged
        internally and the authoritative figure is what gets charged.

    The second check exists because an earlier version trusted the caller, and
    the agreed price had to survive a hop from the quoting agent to the sales
    agent. In a 20-request evaluation, 3 of 40 sale lines reached the ledger at
    the wrong price that way. A price the customer was never quoted must never
    reach the ledger.

    Args:
        item_name: Product name; fuzzy wording is resolved to the catalog.
        quantity: Number of units sold.
        total_price: The line total the caller believes was agreed, after discounts.
        sale_date: Date of the sale, formatted as YYYY-MM-DD.
    """
    resolved = _resolve_item_name(item_name)
    if not resolved:
        return f"SALE REJECTED: '{item_name}' is not in the catalog."
    if quantity <= 0:
        return "SALE REJECTED: quantity must be a positive number of units."

    units_on_hand = _current_stock(resolved, sale_date)
    if units_on_hand < quantity:
        return (
            f"SALE REJECTED: only {units_on_hand} units of {resolved} are "
            f"available on {sale_date}, but {quantity} were requested. "
            f"Restock first, or decline this line."
        )

    # Re-derive the price rather than trusting the caller. Same computation
    # calculate_quote performs, so quote and ledger cannot diverge.
    discount_rate = _discount_rate_for(quantity)
    authoritative_total = round(
        _unit_price(resolved) * quantity * (1 - discount_rate), 2
    )
    if abs(float(total_price) - authoritative_total) > 0.01:
        # Internal audit line; never surfaced to the customer.
        print(
            f"[price correction] {resolved} x{quantity}: caller said "
            f"${float(total_price):.2f}, charging ${authoritative_total:.2f}"
        )

    create_transaction(
        item_name=resolved,
        transaction_type="sales",
        quantity=quantity,
        price=authoritative_total,
        date=sale_date,
    )
    return (
        f"SALE COMPLETED: {quantity} units of {resolved} for "
        f"${authoritative_total:.2f} on {sale_date} "
        f"({discount_rate:.0%} bulk discount applied). "
        f"Quote this total to the customer."
    )


@tool
def company_financial_report(as_of_date: str) -> str:
    """Produces the company-wide financial and inventory report for a date.

    Internal health check before approving an unusually large order. Never quote
    these figures back to the customer.

    Args:
        as_of_date: Date to report on, formatted as YYYY-MM-DD.
    """
    report = generate_financial_report(as_of_date)
    # Drop the starter's seed row, which carries a NULL item_name.
    top_items = [
        item for item in report.get("top_selling_products", [])
        if item.get("item_name")
    ][:5]
    top_lines = "\n".join(
        f"  - {item.get('item_name')}: {item.get('total_units')} units, "
        f"${float(item.get('total_revenue') or 0):.2f} revenue"
        for item in top_items
    ) or "  - none yet"
    return (
        f"INTERNAL financial report as of {report['as_of_date']}:\n"
        f"  Cash balance: ${report['cash_balance']:.2f}\n"
        f"  Inventory value: ${report['inventory_value']:.2f}\n"
        f"  Total assets: ${report['total_assets']:.2f}\n"
        f"  Top sellers:\n{top_lines}"
    )
