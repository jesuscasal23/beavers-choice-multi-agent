# Beaver's Choice Paper Company — Multi-Agent System

Completed Udacity project. **See [GUIDE.md](GUIDE.md)** for the design rationale
and how to run it.

## Run it

```bash
cd ~/Desktop/beavers-choice-project && .venv/bin/python project_starter.py
```

## Submission files

| File | What it is |
|---|---|
| [`project_starter.py`](project_starter.py) | The implementation — one Python file |
| [`diagram/beavers_choice_workflow.png`](diagram/beavers_choice_workflow.png) | The agent workflow diagram |
| [`report/reflection_report.pdf`](report/reflection_report.pdf) | The reflection report (source: `reflection_report.md`) |
| [`test_results.csv`](test_results.csv) | Evaluation output over all 20 sample requests |

## Evaluation result

20/20 requests processed with no errors. 18 changed the cash balance, 18
recorded at least one sale, 2 were declined outright with specific reasons.
Cash $45,059.70 → $46,735.99 (+$1,676.29) at a 43.1% net margin.

Four properties are enforced in code and verified over the whole run: every
recorded sale matches its quote (0/42 mismatches), every price shown to a
customer is backed by a recorded sale (0/20 unbacked), every cash delta
reconciles with the ledger (0/20 mismatches), and no item is ever substituted
for the one the customer asked for.

```bash
.venv/bin/python analyze_results.py && .venv/bin/python audit_prices.py \
  && .venv/bin/python audit_replies.py && .venv/bin/python audit_reconciliation.py
```

## Architecture

Four agents (cap is five), `smolagents` 1.26, `gpt-4o-mini` via the Vocareum
OpenAI-compatible proxy:

| Agent | Type | Owns |
|---|---|---|
| `orchestrator_agent` | `CodeAgent` | Delegation and the customer reply; no database access |
| `inventory_agent` | `ToolCallingAgent` | Stock, supplier lead times, reorder decisions |
| `quoting_agent` | `ToolCallingAgent` | Pricing and the bulk-discount ladder |
| `sales_agent` | `ToolCallingAgent` | Committing or refusing transactions |

Guiding principle: **the LLM decides which tool to call; Python decides what
every number is.** Discounts, totals, cash-reserve checks and delivery-deadline
checks are all deterministic code, so quotes are reproducible and refusals are
structural rather than prompted.

## Folder layout

```
beavers-choice-project/
├── project_starter.py                 <- the submission
├── analyze_results.py                 <- rubric threshold checker
├── audit_prices.py                    <- verifies ledger prices match quotes
├── audit_replies.py                   <- verifies no leaks and no unbacked prices
├── audit_reconciliation.py            <- verifies responses reconcile with the ledger
├── quote_requests_sample.csv          <- 20-request evaluation set
├── quote_requests.csv, quotes.csv     <- historical quote seed data
├── test_results.csv                   <- evaluation output
├── run_full.log                       <- full agent trace
├── GUIDE.md, README.md, requirements.txt
├── .env, .env.example, .gitignore
├── .venv/                             <- Python 3.12 + smolagents 1.26
├── snippets/                          <- the implementation, in paste order
│   ├── 01_imports_and_config.py
│   ├── 02_tools.py
│   ├── 03_agents.py
│   ├── 04_entry_point.py
│   └── 05_test_harness_edit.py
├── diagram/
│   ├── workflow.mmd
│   └── beavers_choice_workflow.png
└── report/
    └── reflection_report.md
```
