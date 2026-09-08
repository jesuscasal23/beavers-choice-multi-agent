# Beaver's Choice Paper Company — Build Guide

This folder contains a **complete, runnable** solution. This guide explains what
was built, why each decision was made, and what you need to do to reproduce,
modify, or submit it.

If you only want to run it:

```bash
cd ~/Desktop/beavers-choice-project && .venv/bin/python project_starter.py
```

---

## 0. What is in this folder

| File | Role |
|---|---|
| `project_starter.py` | **The submission.** Pristine Udacity starter + the four implementation sections + the harness |
| `quote_requests_sample.csv` | The 20-request evaluation set |
| `quote_requests.csv`, `quotes.csv` | Seed data for the historical-quote tables |
| `test_results.csv` | Output of the evaluation run |
| `run_full.log` | Full agent trace of that run |
| `analyze_results.py` | Checks `test_results.csv` against the rubric thresholds |
| `audit_prices.py` | Re-derives every recorded sale and flags any that diverge from the quote |
| `audit_replies.py` | Scans every reply for leaked internal status codes, and for prices the ledger does not back |
| `audit_reconciliation.py` | Checks each response against its slice of the ledger: cash delta, order totals, item substitution |
| `diagram/workflow.mmd` | Mermaid source for the workflow diagram |
| `diagram/beavers_choice_workflow.png` | **Rendered diagram for submission** |
| `report/reflection_report.md` | **The reflection report for submission** |
| `snippets/01…04` | The same four implementation sections, standalone, in paste order |
| `.env` | Vocareum API key (gitignored) |
| `.venv/` | Python 3.12 virtualenv with smolagents 1.26 |

`project_starter.py` is assembled from `snippets/01…04`. If you edit a snippet,
re-paste it into `project_starter.py` — the snippets are the readable source of
truth, the single file is what gets submitted.

---

## 1. Environment

The venv already exists. It was built with Python 3.12 because **smolagents
requires 3.10+** and macOS ships 3.9.

```bash
/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`.env` holds `UDACITY_OPENAI_API_KEY`. Section 1 of the implementation reads it
and points `OpenAIServerModel` at `https://openai.vocareum.com/v1`.

**Why a proxy base URL:** Vocareum re-hosts the OpenAI API so Udacity can meter
spend. The SDK is unchanged; only `base_url` moves. Stay on `gpt-4o-mini` — the
model the course budget is sized for.

> 🔒 The key is in plaintext in `.env` and in your chat history. `.gitignore`
> excludes `.env`. Rotate the key from **Cloud Resources** once you've submitted.

---

## 2. The architecture

**Four agents — one below the cap of five.**

| # | Agent | smolagents type | Owns | Explicitly not its job |
|---|---|---|---|---|
| 1 | `orchestrator_agent` | `CodeAgent` | Parsing the request, delegation order, the customer reply | Never touches the database |
| 2 | `inventory_agent` | `ToolCallingAgent` | Stock truth, supplier lead times, reorder decisions | Never prices, never sells |
| 3 | `quoting_agent` | `ToolCallingAgent` | Pricing, the bulk-discount ladder | Never checks stock, never sells |
| 4 | `sales_agent` | `ToolCallingAgent` | Committing or refusing transactions | Never sets the price |

**Why these boundaries:** the three worker concerns map onto three different
failure modes — a wrong stock read oversells, a wrong price loses margin, a
wrong write corrupts the ledger. Isolating them makes any bad answer traceable
to exactly one owner.

**Why `CodeAgent` for the orchestrator and `ToolCallingAgent` for the workers:**
workers do one narrow job, so structured JSON tool calls are cheaper and leave
less room to improvise. The orchestrator must loop over several line items and
branch on availability, so it benefits from reasoning in Python.

**Why not use the fifth permitted agent:** a separate "customer communications"
agent would duplicate the orchestrator's final step, add a round-trip of latency
and cost, and give two agents overlapping responsibility — which the rubric
penalises. Using fewer agents deliberately is a defensible design decision.

---

## 3. The three ideas that make it work

### 3.1 The LLM decides *which*; Python decides *what*

Every number — discount tier, line total, cash-reserve check, delivery-deadline
check, stock comparison — is computed in Python inside a tool. The model only
chooses which tool to call with which arguments. That is why `temperature=0.1`
and why the same item and quantity always produce the same price.

Policy lives in named constants at the top of Section 1, not in prompts:

```python
SUPPLIER_COST_RATIO = 0.50        # cost of goods, as a fraction of retail
MIN_CASH_RESERVE = 5_000.00       # a restock may never breach this
BULK_DISCOUNT_TIERS = [(10_000, 0.15), (5_000, 0.12),
                       (1_000, 0.10), (500, 0.05), (100, 0.02)]
RESTOCK_BUFFER_MULTIPLIER = 1.5   # order the shortfall plus a buffer
DEFAULT_LEAD_DAYS = 10            # assumed deadline when none is stated
```

`SUPPLIER_COST_RATIO` is an assumption worth naming in your report: the starter
data ships only a retail `unit_price`, so a 50% cost of goods is imposed to make
margin modellable. Change the one constant to model a different margin.

### 3.2 Refusal is structural, not prompted

Three independent guards produce the rejections the rubric requires, all in
code:

- `_restock` refuses when the supplier delivery date falls after the customer's
  required-by date;
- `_restock` refuses when the purchase would push cash below `MIN_CASH_RESERVE`;
- `record_sale` re-checks stock at commit time and refuses to oversell.

`record_sale` also **re-derives the line total** rather than trusting the price
it is handed, logging any disagreement as `[price correction]`. See §3.4.

On top of that, the orchestrator simply *does not call* `sales_agent` for lines
marked `UNAVAILABLE`. A prompt can be ignored; a code path cannot.

### 3.3 `ensure_stock_available` — the bug that shaped the design

The first working version gave `inventory_agent` separate `check_stock_level`
and `place_restock_order` tools. In testing it would check stock, observe a
shortfall, call `check_supplier_delivery` — and then **forget to place the
order**, while the orchestrator went on to promise the customer a delivery date
for goods that had never been bought.

The fix was not a sterner prompt. It was collapsing check → decide → order into
one atomic tool that returns a single verdict:

```
AVAILABLE   — ships from stock
RESTOCKED   — was short; N units ordered, arriving <date>, in time
UNAVAILABLE — short and cannot be restocked, because <reason>
```

The orchestrator keys its branch off those three keywords. **General lesson:
when a multi-step decision must always happen, encode it in one tool rather than
hoping the model chains the steps.**

---

### 3.4 `record_sale` re-derives the price — the second bug

The first full evaluation passed every rubric threshold and was still wrong.
`audit_prices.py` recomputed each recorded sale from the catalog price and the
discount ladder and found **3 of 40 lines billed at a price the customer was
never quoted** — one $47.50 line written to the ledger at $237.50.

`calculate_quote` was deterministic, but `record_sale` accepted `total_price` as
an argument and wrote whatever it was given, so the agreed figure had to survive
a hop from `quoting_agent` through the orchestrator to `sales_agent`.

`record_sale` now recomputes the authoritative total itself and treats the
caller's number as a claim to be audited. Same lesson as §3.3, in a different
place: **a number that must be correct should be computed where it is used, not
passed between agents.**

### 3.5 The reply is sanitised in code — the third bug

The run after the pricing fix leaked in a different way: request 17 rendered its
declined lines as `A4 white printer paper: UNAVAILABLE`, passing an internal
verdict token to the customer three times in one message.

Two layers now prevent it. The orchestrator's rules name the five status codes
as internal and give the phrasing to use instead; and
`_sanitize_customer_reply` rewrites any surviving all-capitals token before the
message leaves `handle_customer_request`, logging any other internal term
(cash balance, supplier cost, margin, agent names, tracebacks) for audit.

Worth being precise about what fixed it: in the final run the *instruction*
alone was sufficient — the orchestrator's raw output contained zero status codes
before sanitisation, so the code layer never activated. Its correctness comes
from unit tests, not from that run. It stays because instructions are exactly
what had already failed once, and the deterministic layer is what makes the
property hold on runs nobody has watched.

Note the lower-case word "unavailable" passes through untouched — it is ordinary
English and a perfectly good thing to say to a customer.

### 3.6 Money in the reply comes from the ledger — the fourth bug

Fixing the ledger (§3.4) did not fix the customer. In the next run, request 17's
reply said *"$237.50 … $237.50 … total $475.00"* while the ledger correctly
charged **$95.00**. `calculate_quote` had returned $47.50 per line; the model
corrupted it on the hop to `sales_agent`; `record_sale`'s guard caught it and
charged correctly — and the orchestrator then wrote the corrupted figure into
the reply. The guard protected the ledger and left the message exposed, and
`audit_prices.py` reported clean because it only checked the ledger.

`handle_customer_request` now marks the ledger position before the run, reads
back exactly the sales that run produced, replaces any money figure in the prose
that does not match one of them with an em dash, and appends a ledger-generated
`Confirmed order` block. Correct figures survive untouched.

Three bugs, one root cause: trusting the model to carry a value across a hop.
Each was fixed by moving the guarantee into code at the point of use.

### 3.7 The resolver refuses instead of guessing — the fifth bug

`_resolve_item_name` ended in a `difflib` fallback at a 0.60 cutoff. A customer
asked for 10,000 **tickets**; *"tickets"* scores 0.632 against *"sticky notes"*,
so the system sold them 10,000 sticky notes and billed $255 for a product they
never mentioned. Auditing all 74 item phrasings the agents had ever used showed
it was systemic — *"A4 printing paper"* was resolving to **Wrapping paper**,
*"A4 white printer paper"* to **Glitter paper**, *"printer paper"* to
**Poster paper**.

The resolver is now ordered from certain to speculative: a word-level blocklist
(`UNSUPPORTED_PRODUCT_TERMS`) ahead of any scoring, exact match, a curated
synonym table (`CATALOG_ALIASES`) matched exactly and by containment, catalog
containment, then fuzzy matching at 0.82 that may never cross a paper-size
boundary — because *"A3 paper"* scores 0.875 against *"A4 paper"* and swapping a
size is a substitution, not a spelling fix.

70 of the 74 phrasings resolve; the four that do not (tickets, balloons,
cardboard for signage, A3 paper) are genuinely not carried.

---

## 4. Tools and helper-function coverage

All seven required starter helpers are used. Coverage is also recorded in the
header comment of `snippets/02_tools.py`.

| Starter helper | Used by | Owning agent(s) |
|---|---|---|
| `create_transaction` | `ensure_stock_available`, `place_restock_order`, `record_sale` | inventory, sales |
| `get_all_inventory` | `inventory_snapshot` | inventory |
| `get_stock_level` | `ensure_stock_available`, `check_stock_level`, `calculate_quote`, `record_sale` | inventory, quoting, sales |
| `get_supplier_delivery_date` | `ensure_stock_available`, `place_restock_order`, `check_supplier_delivery` | inventory, sales |
| `get_cash_balance` | `ensure_stock_available`, `place_restock_order`, `check_cash_balance` | inventory |
| `generate_financial_report` | `company_financial_report` | sales |
| `search_quote_history` | `find_similar_quotes` | quoting |

Two things the starter does not give you, handled explicitly:

- **No price-lookup helper.** `catalog_listing` and `_unit_price` read the
  starter's own `paper_supplies` list rather than the seeded `inventory` table.
  This matters: the seed stocks only ~40% of the catalog (18 of 44 items), and
  an item we don't currently hold is still one we can quote and reorder.
- **`search_quote_history` ANDs its search terms.** Passing four keywords
  usually returns nothing. `find_similar_quotes` therefore retries with
  progressively fewer terms instead of reporting "no precedent".

**Fuzzy item resolution** (`_resolve_item_name`) runs in Python, not the model:
exact → case-insensitive → longest catalog name contained in the customer's
phrasing → `difflib` close match. That is how *"heavy cardstock (white)"* finds
`Cardstock` and *"A4 glossy paper"* correctly finds `Glossy paper` rather than
`A4 paper`.

---

## 5. Customer-safety rules

The "Industry Best Practices" rubric row wants transparent outputs that don't
leak internals. Enforced in four places:

1. `company_financial_report`'s docstring marks the figures internal-only.
2. `QUOTING_AGENT_RULES` forbids mentioning supplier cost, margin, or cash.
3. `ORCHESTRATOR_TASK_TEMPLATE` Step 5 lists exactly what the reply must contain
   (item, quantity, total, discount rate *and the order size that earned it*,
   availability date, or a specific refusal reason) and what it must never
   contain (balances, costs, tool output, tracebacks, internal agent names).
4. `handle_customer_request` catches every exception, logs the real cause to
   stdout, and returns a neutral fallback — so no stack trace can reach
   `test_results.csv`.

---

## 6. Running and evaluating

```bash
.venv/bin/python project_starter.py
```

`run_test_scenarios()` re-initialises the database each run, so results are
reproducible. Expect roughly 2–3 minutes per request (four agents, several LLM
calls each) — about 50 minutes for all 20.

**Dry-run first when you change anything.** Add this after the sort in
`run_test_scenarios()`, then remove it:

```python
        quote_requests_sample = quote_requests_sample.head(3)  # TEMP
```

Catching a tool error on request 1 of 3 costs cents; catching it on request 19
of 20 costs a chunk of the Vocareum budget.

**Check the rubric thresholds:**

```bash
.venv/bin/python analyze_results.py && .venv/bin/python audit_prices.py && .venv/bin/python audit_replies.py && .venv/bin/python audit_reconciliation.py
```

You need ≥3 requests that change the cash balance, ≥3 fulfilled, and ≥1
unfulfilled with a stated reason. Both audits must report zero: every recorded
sale has to equal the price the customer was quoted, no internal status code may
appear in a reply, no price may appear that the ledger does not back, and every
response must reconcile with its slice of the ledger.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: smolagents` | using system Python 3.9 | use `.venv/bin/python` |
| Agent hits `max_steps` | a tool returned something ambiguous | make the return more explicit before raising `max_steps` |
| 429 / rate-limit errors | requests firing too fast | raise `time.sleep(1)` in the harness to `3` |
| Every quote is `$0.00` | item name didn't resolve | check `_resolve_item_name()` in a shell |
| Nothing ever declined | seeded stock covers everything | raise `MIN_CASH_RESERVE`; don't fake a refusal |
| `audit_prices.py` reports mismatches | quote and ledger formulas diverged | keep `calculate_quote` and `record_sale` in step |
| `audit_replies.py` reports leaks | a new internal token was introduced | add it to `_INTERNAL_STATUS_TOKENS` in Section 4 |
| Empty `test_results.csv` | exception before the loop | check the date format matches `%m/%d/%y` |

---

## 7. Submission checklist

- [x] `diagram/beavers_choice_workflow.png` — 4 agents, every tool labelled with purpose **and** helper function
- [x] `project_starter.py` — one Python file, agents match the diagram
- [x] All seven helper functions used in at least one tool
- [x] `test_results.csv` over the full sample set
- [x] `report/reflection_report.md` — architecture, evaluation, ≥2 improvements
- [x] No API key hard-coded in the `.py` — read from `.env`
- [x] Customer-facing responses contain no balances, margins, or tracebacks
