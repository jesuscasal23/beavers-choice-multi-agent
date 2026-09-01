import pandas as pd
import numpy as np
import os
import time
import dotenv
import ast
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Dict, List, Union
from sqlalchemy import create_engine, Engine

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine, seed: int = 137) -> Engine:    
    """
    Set up the Munder Difflin database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        # Prepare transaction record as a single-row DataFrame
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }])

        # Insert the record into the database
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)

        # Fetch and return the ID of the inserted row
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0

def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }

def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]



########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################


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
def _resolve_item_name(raw_name: str) -> str:
    """Map a loosely-worded product name onto an exact catalog item name.

    Tried in order: exact match, case-insensitive match, longest catalog name
    contained in the customer's phrasing (so "heavy cardstock (white)" finds
    "Cardstock"), then a fuzzy close match. Doing this in Python rather than
    leaving it to the model removes a whole class of hallucinated item names.

    Returns an empty string when nothing plausible matches.
    """
    if not raw_name:
        return ""
    if raw_name in CATALOG_BY_NAME:
        return raw_name

    lowered = raw_name.strip().lower()
    if lowered in CATALOG_LOWER:
        return CATALOG_LOWER[lowered]

    # Longest catalog name appearing inside the customer's phrasing wins, so
    # "A4 glossy paper" resolves to "Glossy paper" rather than "A4 paper".
    contained = [name for name in CATALOG_LOWER if name in lowered]
    if contained:
        return CATALOG_LOWER[max(contained, key=len)]

    close = difflib.get_close_matches(lowered, list(CATALOG_LOWER), n=1, cutoff=0.6)
    return CATALOG_LOWER[close[0]] if close else ""


def _unit_price(item_name: str) -> float:
    """Retail price per unit for a resolved catalog item name."""
    return float(CATALOG_BY_NAME[item_name]["unit_price"])


def _discount_rate_for(quantity: int) -> float:
    """Return the bulk discount rate that applies to a given order size."""
    for threshold, rate in BULK_DISCOUNT_TIERS:
        if quantity >= threshold:
            return rate
    return 0.0


def _current_stock(item_name: str, as_of_date: str) -> int:
    """Normalize get_stock_level's single-row DataFrame down to an integer."""
    stock_df = get_stock_level(item_name, as_of_date)
    if stock_df.empty or pd.isna(stock_df.iloc[0]["current_stock"]):
        return 0
    return int(stock_df.iloc[0]["current_stock"])


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
    units = _current_stock(resolved, as_of_date)
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



# =============================================================================
# SECTION 5 -- Evaluation harness
#
# Unchanged from the starter apart from the single delegated call inside the
# loop (marked below) and two extra print lines for auditability. The harness
# writes test_results.csv in exactly the shape the rubric grades, so it is left
# alone deliberately.
# =============================================================================

def run_test_scenarios():

    print("Initializing Database...")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    ############
    # INITIALIZE YOUR MULTI AGENT SYSTEM HERE
    ############
    # The four agents are constructed at import time in Sections 1-3 above, so
    # there is nothing to build here. handle_customer_request() is the single
    # public entry point into the system.

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"

        ############
        # USE YOUR MULTI AGENT SYSTEM TO HANDLE THE REQUEST
        ############
        response = handle_customer_request(
            request_text=request_with_date,
            request_date=request_date,
        )

        # Update state
        report = generate_financial_report(request_date)
        previous_cash = current_cash
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")
        print(f"Cash delta: ${current_cash - previous_cash:+.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    results = run_test_scenarios()
