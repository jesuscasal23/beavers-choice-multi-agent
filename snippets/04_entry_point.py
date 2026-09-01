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
    try:
        return _sanitize_customer_reply(str(orchestrator_agent.run(task)).strip())
    except Exception as error:  # noqa: BLE001 -- deliberately catch everything
        # Log the real cause internally; return something safe to the customer.
        print(f"[orchestrator error] {type(error).__name__}: {error}")
        return (
            "Thank you for your enquiry. We were not able to complete an "
            "automated quote for this request, and a member of our sales team "
            "will follow up with you directly."
        )
