# =============================================================================
# SECTION 1 -- Imports, environment, model, and business rules
#
# Paste directly under the starter's "YOUR MULTI AGENT STARTS HERE" banner.
# =============================================================================

import difflib
import math
import os
import re
from typing import List

from dotenv import load_dotenv
from smolagents import CodeAgent, OpenAIServerModel, ToolCallingAgent, tool

# ---- Model wiring -----------------------------------------------------------
# Vocareum re-hosts the OpenAI API so Udacity can meter spend, so the only thing
# that changes versus stock OpenAI is the base URL. OpenAIServerModel is
# smolagents' adapter for any OpenAI-compatible endpoint.
load_dotenv()

VOCAREUM_BASE_URL = "https://openai.vocareum.com/v1"
UDACITY_OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")

if not UDACITY_OPENAI_API_KEY:
    raise RuntimeError(
        "UDACITY_OPENAI_API_KEY is not set. Create a .env file next to this "
        "script containing: UDACITY_OPENAI_API_KEY=voc-..."
    )

model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_base=VOCAREUM_BASE_URL,
    api_key=UDACITY_OPENAI_API_KEY,
    temperature=0.1,  # quoting must be reproducible, not creative
)

# ---- Business rules ---------------------------------------------------------
# Policy lives here, in one auditable place, rather than inside agent prompts.
# Keeping it out of the prompt is what makes quotes deterministic: the model
# chooses WHICH tool to call, but never decides what a number is.

# What we pay the supplier, as a fraction of our own retail unit price. The
# starter data ships only a retail unit_price, so we assume a 50% cost of goods.
SUPPLIER_COST_RATIO = 0.50

# A restock purchase may never drop the bank account below this.
MIN_CASH_RESERVE = 5_000.00

# Bulk discount ladder, evaluated top-down; first threshold met wins.
BULK_DISCOUNT_TIERS = [
    (10_000, 0.15),
    (5_000, 0.12),
    (1_000, 0.10),
    (500, 0.05),
    (100, 0.02),
]

# Restock enough to cover the order plus a safety buffer, so the next customer
# for the same item is not immediately declined.
RESTOCK_BUFFER_MULTIPLIER = 1.5

# Fallback deadline when a customer states no delivery date.
DEFAULT_LEAD_DAYS = 10

# Catalog lookup built once from the starter's own price list. Using
# paper_supplies rather than the seeded `inventory` table matters: the seed only
# stocks ~40% of the catalog, and an item we do not currently hold is still an
# item we can quote and reorder.
CATALOG_BY_NAME = {item["item_name"]: item for item in paper_supplies}
CATALOG_LOWER = {name.lower(): name for name in CATALOG_BY_NAME}
