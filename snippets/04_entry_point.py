# =============================================================================
# SECTION 4 -- Reply sanitisation and the single entry point
#
# One function is the whole public surface of the multi-agent system. The
# starter's test harness calls this; nothing else needs to know four agents
# exist. The try/except matters twice over: one malformed request must not abort
# a 20-request evaluation run, and a customer must never see a Python traceback.
# =============================================================================


# Internal status vocabulary produced by the tools. The orchestrator is told to
# write plain English, but an instruction is advisory: in the first evaluation
# run it passed the token UNAVAILABLE straight through to a customer. These
# substitutions are the deterministic guard that makes that impossible.
#
# Ordered longest-first so UNAVAILABLE is matched before AVAILABLE. Only the
# all-capitals form is rewritten -- lower-case "unavailable" is ordinary English
# and a perfectly good thing to say to a customer.
_INTERNAL_STATUS_TOKENS = [
    ("RESTOCK DECLINED", "could not be restocked in time"),
    ("SALE COMPLETED", "confirmed"),
    ("SALE REJECTED", "could not be fulfilled"),
    ("RESTOCK PLACED", "on order from our supplier"),
    ("NOT_IN_CATALOG", "not an item we carry"),
    ("UNAVAILABLE", "not available"),
    ("RESTOCKED", "on order from our supplier"),
    ("AVAILABLE", "available"),
]

# Terms that should never appear in a customer-facing message. These are not
# rewritten -- rewriting a leaked cash balance would produce a sentence that
# still reads oddly -- but they are logged so the leak is visible in the trace.
_FORBIDDEN_IN_REPLY = re.compile(
    r"cash balance|cash reserve|supplier cost|cost of goods|profit margin|"
    r"gross margin|inventory_agent|quoting_agent|sales_agent|orchestrator|"
    r"price correction|Traceback|create_transaction|get_stock_level|"
    r"ensure_stock_available|record_sale",
    re.IGNORECASE,
)


def _sanitize_customer_reply(reply: str) -> str:
    """Strip internal status vocabulary from a customer-facing message.

    Applied at the last hop before the reply leaves the system, on the same
    reasoning as re-deriving the price inside record_sale: a property that must
    hold is enforced in code at the point of use, not requested in a prompt.

    Returns the cleaned reply. Any remaining forbidden term is logged for
    internal audit rather than silently rewritten.
    """
    cleaned = reply
    for token, replacement in _INTERNAL_STATUS_TOKENS:
        cleaned = re.sub(rf"\b{token}\b", replacement, cleaned)

    leaked = _FORBIDDEN_IN_REPLY.findall(cleaned)
    if leaked:
        print(f"[reply audit] internal terms in customer reply: {sorted(set(leaked))}")
    return cleaned


# Any run of digits preceded by a dollar sign, with or without thousands commas
# and with or without cents.
_MONEY_PATTERN = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")


def _last_transaction_id() -> int:
    """Highest rowid in the transactions ledger right now."""
    latest = pd.read_sql("SELECT COALESCE(MAX(rowid), 0) AS max_id FROM transactions", db_engine)
    return int(latest.iloc[0]["max_id"])


def _sales_since(last_transaction_id: int) -> pd.DataFrame:
    """Sales written to the ledger after a given rowid.

    Called with the rowid captured immediately before an orchestrator run, this
    returns exactly the sales that run produced -- which is what makes it
    possible to price the reply from the ledger rather than from the model's
    recollection.
    """
    return pd.read_sql(
        text(
            "SELECT item_name, units, price FROM transactions "
            "WHERE rowid > :last_id AND transaction_type = 'sales' ORDER BY rowid"
        ),
        db_engine,
        params={"last_id": last_transaction_id},
    )


def _sale_described_by(line: str, sales: pd.DataFrame):
    """The recorded sale a prose line refers to, or None if it is ambiguous.

    A line such as "- Cardstock: 200 sheets, total price $X" names both the item
    and the quantity, so an unverified amount on it can be replaced with the real
    one rather than blanked. Matching prefers item-and-quantity agreement, then
    quantity alone, then item alone, and gives up unless exactly one sale fits.
    """
    numbers = {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", line)}
    resolved = _resolve_item_name(line)

    both, by_quantity, by_item = [], [], []
    for sale in sales.itertuples():
        quantity_hit = int(sale.units) in numbers
        item_hit = bool(resolved) and resolved == sale.item_name
        if quantity_hit and item_hit:
            both.append(sale)
        if quantity_hit:
            by_quantity.append(sale)
        if item_hit:
            by_item.append(sale)

    for candidates in (both, by_quantity, by_item):
        if len(candidates) == 1:
            return candidates[0]
    return None


def _enforce_authoritative_pricing(reply: str, sales: pd.DataFrame) -> str:
    """Guarantee every price shown to the customer came from the ledger.

    record_sale already protects the LEDGER from a corrupted price. It cannot
    protect the customer-facing message, because the orchestrator writes that
    from what it remembers rather than from the confirmations. In evaluation the
    model corrupted a $47.50 line into $237.50 on the hop between agents three
    times in a single request; the ledger was charged correctly and the customer
    was quoted the corrupt figure.

    So: any money figure in the prose that does not match a recorded sale is
    replaced with an em dash, and an itemised summary generated from the ledger
    is appended. The customer may see a dash, but never a wrong price.

    This is the narrowly-scoped version of composing the whole reply from a
    template -- applied to the part that must be correct.
    """
    authoritative = set()
    summary_lines = []
    order_total = 0.0

    for sale in sales.itertuples():
        price, quantity = float(sale.price), int(sale.units)
        order_total += price
        discount_rate = _discount_rate_for(quantity)
        authoritative.update(_money_forms(price))
        summary_lines.append(
            f"  - {quantity} x {sale.item_name} — ${price:,.2f}"
            + (f" ({discount_rate:.0%} bulk discount)" if discount_rate else "")
        )

    if summary_lines:
        authoritative.update(_money_forms(order_total))

    # Correct line by line: a prose line usually names the item and quantity it
    # is talking about, which is enough to identify the sale it refers to and
    # substitute the real figure. Only when the line is ambiguous do we fall
    # back to removing the amount -- a customer should see the right price, not
    # a gap, and the gap is reserved for the case where we genuinely cannot tell
    # which line was meant.
    corrected_lines = []
    for line in reply.split("\n"):
        def _keep_or_correct(match: re.Match, line: str = line) -> str:
            if match.group(0).replace(" ", "") in authoritative:
                return match.group(0)
            sale = _sale_described_by(line, sales)
            if sale is not None:
                return f"${float(sale.price):,.2f}"
            # A summing line ("your combined order total is ...") names no item
            # and no quantity, so nothing above can identify it -- but there is
            # only one figure it could mean.
            if summary_lines and re.search(r"\btotals?\b", line, re.IGNORECASE):
                return f"${order_total:,.2f}"
            return "—"

        corrected_lines.append(_MONEY_PATTERN.sub(_keep_or_correct, line))
    corrected = "\n".join(corrected_lines)

    if summary_lines:
        corrected += (
            "\n\nConfirmed order\n"
            + "\n".join(summary_lines)
            + f"\n  Order total: ${order_total:,.2f}"
        )
    return corrected


def _money_forms(amount: float) -> set:
    """Every spelling of an amount we are willing to accept in the prose."""
    forms = {f"${amount:,.2f}", f"${amount:.2f}"}
    if amount == int(amount):
        forms.update({f"${amount:,.0f}", f"${amount:.0f}"})
    return forms


def handle_customer_request(request_text: str, request_date: str) -> str:
    """Runs one customer request through the multi-agent system.

    Args:
        request_text: The raw customer inquiry.
        request_date: Date the request was received, formatted as YYYY-MM-DD.

    Returns:
        A single customer-facing message. Never raises.
    """
    default_required_by = (
        datetime.fromisoformat(request_date) + timedelta(days=DEFAULT_LEAD_DAYS)
    ).strftime("%Y-%m-%d")

    task = ORCHESTRATOR_TASK_TEMPLATE.format(
        request_text=request_text,
        request_date=request_date,
        default_required_by=default_required_by,
    )
    # Ledger position before the run, so the sales this request produces can be
    # identified afterwards and used to price the reply.
    ledger_mark = _last_transaction_id()
    try:
        reply = _sanitize_customer_reply(str(orchestrator_agent.run(task)).strip())
        return _enforce_authoritative_pricing(reply, _sales_since(ledger_mark))
    except Exception as error:  # noqa: BLE001 -- deliberately catch everything
        # Log the real cause internally; return something safe to the customer.
        print(f"[orchestrator error] {type(error).__name__}: {error}")
        return (
            "Thank you for your enquiry. We were not able to complete an "
            "automated quote for this request, and a member of our sales team "
            "will follow up with you directly."
        )
