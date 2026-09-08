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

# Business terms customers use for things Beaver's Choice does not sell. Fuzzy
# matching must never map these onto a catalog item. In evaluation, "tickets"
# scored 0.632 against "sticky notes" -- close enough for the old 0.6 cutoff to
# accept it, so a customer who asked for 10,000 tickets was sold and billed for
# 10,000 sticky notes. A blocklist is checked before any similarity scoring.
UNSUPPORTED_PRODUCT_TERMS = {
    "ticket", "tickets", "balloon", "balloons", "cardboard", "signage",
}

# Explicit synonyms for things we DO sell. These exist because the fuzzy matcher
# is now deliberately strict (see RESOLVER_FUZZY_CUTOFF): a real company keeps an
# auditable synonym list rather than letting string similarity guess. Every entry
# below was derived from wording that actually appeared in customer requests.
CATALOG_ALIASES = {
    # Copier / printer paper -- customers almost never say "standard copy paper".
    "printer paper": "Standard copy paper",
    "white printer paper": "Standard copy paper",
    "standard printer paper": "Standard copy paper",
    "standard printing paper": "Standard copy paper",
    "a4 printer paper": "A4 paper",
    "a4 printing paper": "A4 paper",
    "a4 size printer paper": "A4 paper",
    "a4 white paper": "A4 paper",
    "a4 white printer paper": "A4 paper",
    # Posters and boards
    "posters": "Poster paper",
    "poster board": "Large poster paper (24x36 inches)",
    "poster boards": "Large poster paper (24x36 inches)",
    # Party goods
    "streamers": "Party streamers",
    "table napkins": "Paper napkins",
    # Sizes the catalog spells differently from customers
    "legal paper": "Legal-size paper",
    "letter paper": "Letter-sized paper",
    # Tape
    "washi tape": "Decorative adhesive tape (washi tape)",
    "decorative washi tape": "Decorative adhesive tape (washi tape)",
    "decorative adhesive tape": "Decorative adhesive tape (washi tape)",
}

# Similarity threshold of last resort. Raised from 0.60 to 0.82 after an audit
# showed 0.60 was mapping "A4 printing paper" to "Wrapping paper" and
# "A4 white printer paper" to "Glitter paper". Above 0.82 a match is a spelling
# variant; below it, it is a guess -- and a guess here bills a customer for a
# product they did not order.
RESOLVER_FUZZY_CUTOFF = 0.82

# Guard the invariant the blocklist depends on: no unsupported term may appear
# inside a real catalog name, or we would block a product we actually sell.
for _term in UNSUPPORTED_PRODUCT_TERMS:
    assert not any(_term in _name for _name in CATALOG_LOWER), (
        f"unsupported term {_term!r} collides with a catalog item"
    )
for _alias_target in CATALOG_ALIASES.values():
    assert _alias_target in CATALOG_BY_NAME, f"alias target {_alias_target!r} is not a catalog item"

# Paper sizes the catalog names explicitly. A fuzzy match that swaps one of
# these for another is a product substitution, not a spelling correction:
# "A3 paper" scores 0.875 against "A4 paper", comfortably above the cutoff, and
# the company does not sell A3 paper at all. Size-agnostic items are unaffected,
# so "A3 colored paper" still resolves to "Colored paper".
SIZE_TOKENS = ("a3", "a4", "a5", "legal", "letter")
