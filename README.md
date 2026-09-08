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

20/20 requests processed with no errors. 17 changed the cash balance, 17
recorded at least one sale, 3 were declined outright with specific reasons.
Cash $45,059.70 → $46,589.49 (+$1,529.79) on a 35.4% net margin.

Three properties are enforced in code and verified over the whole run: every
recorded sale matches its quote (0/39 mismatches), every price shown to a
customer is backed by a recorded sale (0/20 unbacked), and no internal status
code reaches a customer (0/20 leaked).

```bash
.venv/bin/python analyze_results.py && .venv/bin/python audit_prices.py && .venv/bin/python audit_replies.py
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
