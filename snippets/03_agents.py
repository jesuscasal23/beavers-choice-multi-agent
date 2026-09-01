# =============================================================================
# SECTION 3 -- The four agents
#
# Agent count: 1 orchestrator + 3 workers = 4 (the rubric caps this at five).
#
# Why ToolCallingAgent for workers and CodeAgent for the orchestrator:
#   * Workers do one narrow job and mostly need to call a tool and report back.
#     ToolCallingAgent emits structured JSON tool calls -- cheaper and more
#     predictable, with less room to improvise.
#   * The orchestrator must branch and loop (several line items per request;
#     stock? restock? in time? affordable?), so it benefits from CodeAgent,
#     which reasons in Python and can hold intermediate values across steps.
#
# `name` and `description` are the delegation interface: smolagents shows the
# orchestrator each worker's description, so they read like a job posting --
# what this agent does, and what it explicitly does not do.
# =============================================================================

INVENTORY_AGENT_RULES = """
You are the inventory controller for the Beaver's Choice Paper Company.

Always:
1. For EVERY line item you are given, call ensure_stock_available exactly once,
   with the item name, quantity, the request date and the required-by date.
   That single tool resolves the item name, measures the shortfall, and places
   a restock order itself when one is needed and permissible. Do not try to
   reproduce its logic with separate stock and restock calls.
2. Report its verdict for each line VERBATIM. Every verdict begins with
   AVAILABLE, RESTOCKED or UNAVAILABLE -- pass those keywords through unchanged,
   because the orchestrator keys its decision off them.
3. Use catalog_listing, check_stock_level, check_supplier_delivery,
   inventory_snapshot or check_cash_balance only when you need extra detail to
   explain a verdict.
4. Never invent a number you did not get from a tool.
"""

QUOTING_AGENT_RULES = """
You are the pricing analyst for the Beaver's Choice Paper Company.

Always:
1. Call find_similar_quotes once with 1-3 broad keywords (the event type and the
   product word) so your price is anchored on precedent.
2. Call calculate_quote for EVERY line item. Report its FINAL TOTAL verbatim.
   Never re-do the arithmetic yourself and never round it differently.
3. State the discount rate applied and the order size that earned it, so the
   customer can see how the price was reached.
4. Never mention supplier cost, profit margin, or the company's cash position.
"""

SALES_AGENT_RULES = """
You are the fulfillment officer for the Beaver's Choice Paper Company.

Always:
1. Re-run check_stock_level immediately before selling; stock may have changed
   since the quote was produced.
2. For orders above $5,000, run company_financial_report first as an internal
   solvency check. Keep those figures internal.
3. Call record_sale exactly once per line item, with the agreed total price.
   record_sale re-derives the authoritative total itself. Report the total from
   ITS confirmation message, never the one you sent it.
4. If record_sale rejects a line, say so plainly and give the reason in
   customer-safe language (e.g. "only 300 of the 1,000 units are available").
5. Report back a per-line list of what sold and what did not, with totals.
"""

# ---- Worker 1: Inventory & supply -------------------------------------------
inventory_agent = ToolCallingAgent(
    model=model,
    tools=[
        ensure_stock_available,  # primary: decide + restock in one atomic call
        catalog_listing,
        inventory_snapshot,
        check_stock_level,
        check_supplier_delivery,
        place_restock_order,
        check_cash_balance,
    ],
    name="inventory_agent",
    description=(
        "Owns stock and supply. For each line item it returns a verdict of "
        "AVAILABLE, RESTOCKED or UNAVAILABLE, resolving the customer's wording "
        "to an exact catalog name and placing a restock order itself when stock "
        "is short and a restock can arrive in time. Give it the item names, "
        "quantities, the request date and the customer's required-by date. "
        "It does not price and does not sell."
    ),
    instructions=INVENTORY_AGENT_RULES,
    max_steps=8,
)

# ---- Worker 2: Quoting ------------------------------------------------------
quoting_agent = ToolCallingAgent(
    model=model,
    tools=[
        catalog_listing,
        find_similar_quotes,
        calculate_quote,
    ],
    name="quoting_agent",
    description=(
        "Owns pricing. Turns confirmed item names and quantities into priced "
        "line items with the bulk discount applied, anchored on comparable "
        "historical quotes. Give it the item names, quantities and request date. "
        "It does not check stock and does not sell."
    ),
    instructions=QUOTING_AGENT_RULES,
    max_steps=8,
)

# ---- Worker 3: Sales & fulfillment ------------------------------------------
sales_agent = ToolCallingAgent(
    model=model,
    tools=[
        check_stock_level,
        check_supplier_delivery,
        record_sale,
        company_financial_report,
    ],
    name="sales_agent",
    description=(
        "Owns order fulfillment. Given item names, quantities, agreed line "
        "totals and the request date, it re-verifies stock and either records "
        "each sale or refuses it with a reason. Call it LAST, only after prices "
        "are agreed and stock has been confirmed or restocked."
    ),
    instructions=SALES_AGENT_RULES,
    max_steps=8,
)

# ---- Orchestrator -----------------------------------------------------------
orchestrator_agent = CodeAgent(
    model=model,
    tools=[],  # delegates only; it never touches the database itself
    managed_agents=[inventory_agent, quoting_agent, sales_agent],
    additional_authorized_imports=["json", "datetime"],
    name="orchestrator_agent",
    description="Front door for customer requests; delegates to the worker agents.",
    max_steps=10,
)

ORCHESTRATOR_TASK_TEMPLATE = """
You are the customer service orchestrator for the Beaver's Choice Paper Company.
You never touch the database yourself. You delegate to three specialists and
then write the single reply the customer will read.

CUSTOMER REQUEST (received {request_date}):
\"\"\"{request_text}\"\"\"

Follow this procedure exactly.

STEP 1 - Understand. List every product line the customer wants, with its
quantity. Determine the date they need delivery by. If they state no date, use
{default_required_by}.

STEP 2 - Availability. Call inventory_agent once, passing ALL line items, the
request date {request_date}, and the required-by date. It returns a verdict per
line. Treat AVAILABLE and RESTOCKED as fulfillable; treat UNAVAILABLE as
declined, and keep its stated reason for your reply.

STEP 3 - Price. Call quoting_agent once with the resolved item names, the
quantities, and {request_date}. Use the exact FINAL TOTAL and discount rate it
returns for each line.

STEP 4 - Fulfill. If at least one line is fulfillable, call sales_agent once
with those lines, their quantities, their agreed totals, and {request_date}.
Do NOT send it lines marked UNAVAILABLE -- those are declined.
If NO line is fulfillable, do not call sales_agent at all.

STEP 5 - Reply. Write the final answer as a short message to the customer. It
must contain:
  - each item and quantity you are responding about
  - for each fulfilled line: the total price, the discount rate applied and the
    order size that earned it, and the expected availability date
  - for each declined line: a clear, specific reason (not enough stock on hand,
    supplier delivery would arrive after their deadline, or the item is not one
    we carry)
  - the combined order total for the lines being fulfilled

Rules for the reply:
  - Never reveal cash balances, supplier costs, profit margins, tool output,
    error messages, or the names of your internal agents.
  - Write plain English. AVAILABLE, RESTOCKED, UNAVAILABLE, SALE COMPLETED and
    SALE REJECTED are internal status codes -- never put them in the reply. Say
    "in stock", "on order from our supplier", "not available", "confirmed" or
    "could not be fulfilled" instead.
  - Never state a price or a date that did not come back from a specialist.
  - A line may be described as confirmed or ordered ONLY if sales_agent reported
    SALE COMPLETED for it. If sales_agent reported SALE REJECTED, or you never
    sent the line to sales_agent, that line is declined and must be described
    as such. Never promise a delivery for a line that was not sold.
  - Decline warmly, but say exactly what blocked it.

Return ONLY the customer-facing message as your final answer.
"""
