# chat_engine.py
import sqlite3
import re
from typing import Dict, Any, List, Tuple

# ------------ RULES: normalized keyword => DB category or filter ------------
# Keep these tuned to the categories you have (extracted earlier).
RULES = {
    # generic -> category (we use LIKE so exact casing doesn't matter)
    "burger": {"category": "Burger"},
    "burgers": {"category": "Burger"},
    "classic burger": {"category": "Classic Burgers"},
    "fusion burger": {"category": "Fusion Burgers"},
    "vegetarian burger": {"category": "Vegetarian Burgers"},
    "pizza": {"category": "Pizza"},
    "personal pizza": {"category": "Personal Pizza"},
    "traditional pizza": {"category": "Traditional Pizza"},
    "gourmet pizza": {"category": "Gourmet Pizza"},
    "wrap": {"category": "Wrap"},
    "wraps": {"category": "Wrap"},
    "taco": {"category": "Tacos"},
    "tacos": {"category": "Tacos"},
    "salad": {"category": "Salads"},
    "salads": {"category": "Salads"},
    "sandwich": {"category": "Sandwich"},
    "fried chicken": {"category": "Fried Chicken"},
    "appetizer": {"category": "Appetizer"},
    "side": {"category": "Sides & Appetizers"},
    "dessert": {"category": "Dessert"},
    "shake": {"category": "Shake"},
    # tags/filters
    "spicy": {"spice_min": 5},
    "mild": {"spice_min": 0},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
    "gluten-free": {"dietary_tags": "gluten-free"},
}

# ------------ Scoring config ------------
ENGAGEMENT_FACTORS = {
    'specific_preferences': 15,
    'dietary_restrictions': 10,
    'budget_mention': 5,
    'mood_indication': 20,
    'question_asking': 10,
    'enthusiasm_words': 8,
    'price_inquiry': 25,
    'order_intent': 30,
}
NEGATIVE_FACTORS = {
    'hesitation': -10,
    'budget_concern': -15,
    'dietary_conflict': -20,
    'rejection': -25,
    'delay_response': -5,
}

def calculate_interest_score(message: str, product_match: bool = True) -> int:
    m = message.lower()
    score = 0
    if any(w in m for w in ['love', 'spicy', 'korean', 'fusion', 'burger', 'pizza', 'wrap']):
        score += ENGAGEMENT_FACTORS['specific_preferences']
    if 'vegetarian' in m or 'vegan' in m:
        score += ENGAGEMENT_FACTORS['dietary_restrictions']
    if re.search(r'under \$\d+|less than \d+|<\s*\d+', m):
        score += ENGAGEMENT_FACTORS['budget_mention']
    if 'adventurous' in m:
        score += ENGAGEMENT_FACTORS['mood_indication']
    if '?' in message:
        score += ENGAGEMENT_FACTORS['question_asking']
    if any(w in m for w in ['amazing', 'perfect', 'love']):
        score += ENGAGEMENT_FACTORS['enthusiasm_words']
    if 'how much' in m or 'price' in m:
        score += ENGAGEMENT_FACTORS['price_inquiry']
    if any(phrase in m for phrase in ["i'll take", "i will take", "order", "add to cart", "i want to order"]):
        score += ENGAGEMENT_FACTORS['order_intent']

    if any(w in m for w in ['maybe', 'not sure']):
        score += NEGATIVE_FACTORS['hesitation']
    if 'too expensive' in m or 'not worth' in m:
        score += NEGATIVE_FACTORS['budget_concern']
    if not product_match and any(w in m for w in ['spicy', 'vegetarian', 'vegan', 'burger', 'pizza', 'wrap']):
        score += NEGATIVE_FACTORS['dietary_conflict']
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS['rejection']

    return max(0, min(100, score))

# ------------ DB Query helper ------------
DB_PATH = "foodiebot.db"

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: tuple(row)  # simple tuple rows
    return conn

def query_database(filters: Dict[str, Any]) -> List[Tuple]:
    """
    Accepts filters dict keys:
      - keyword (string)
      - category (string)  (will be used with LIKE)
      - price_max (float)
      - spice_min (int)
      - dietary_tags (string)
      - context (string)
    Returns list of rows (product_id, name, category, price, spice_level, description, dietary_tags)
    """
    conn = _connect()
    c = conn.cursor()

    conditions = []
    params = []

    # keyword fallback searches key text fields
    if filters.get("keyword"):
        kw = "%" + filters["keyword"].lower() + "%"
        conditions.append("""(
            LOWER(name) LIKE ? OR
            LOWER(category) LIKE ? OR
            LOWER(description) LIKE ? OR
            LOWER(dietary_tags) LIKE ? OR
            LOWER(mood_tags) LIKE ?
        )""")
        params += [kw, kw, kw, kw, kw]

    # category (LIKE)
    if filters.get("category"):
        conditions.append("LOWER(category) LIKE ?")
        params.append("%" + filters["category"].lower() + "%")

    # price_max
    if filters.get("price_max") is not None:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    # spice_min
    if filters.get("spice_min") is not None:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # dietary_tags
    if filters.get("dietary_tags"):
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append("%" + filters["dietary_tags"].lower() + "%")

    # context-aware vegetarian/vegan (if present)
    if filters.get("context"):
        ctx = filters["context"].lower()
        if "vegetarian" in ctx or "vegan" in ctx:
            conditions.append("(LOWER(dietary_tags) LIKE ? OR LOWER(dietary_tags) LIKE ?)")
            params += ["%vegetarian%", "%vegan%"]

    sql = ("SELECT product_id, name, category, price, spice_level, description, dietary_tags "
           "FROM products")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY popularity_score DESC LIMIT 12"

    rows = c.execute(sql, params).fetchall()
    conn.close()
    return rows

# ------------ Generate response (no LLM used for formatting) ------------
def _normalize_text_for_keyword(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _parse_budget_from_text(text: str):
    t = text.lower()
    m = re.search(r'under \$\s*([0-9]+(?:\.[0-9]+)?)', t)
    if not m:
        m = re.search(r'less than\s+([0-9]+(?:\.[0-9]+)?)\s*dollars', t)
    if not m:
        m = re.search(r'<\s*([0-9]+(?:\.[0-9]+)?)', t)
    if m:
        try:
            return float(m.group(1))
        except:
            return None
    return None

def generate_response(user_message: str, context: str = "") -> Tuple[str, int]:
    """
    Returns (response_text, interest_score)
    """
    clean = _normalize_text_for_keyword(user_message)
    filters: Dict[str, Any] = {"keyword": clean, "context": context}

    # apply RULES: check for rule keys in normalized string
    for k, rule in RULES.items():
        if k in clean:
            filters.update(rule)

    # budget parsing
    price_max = _parse_budget_from_text(user_message)
    if price_max is not None:
        filters["price_max"] = price_max

    # Spice words like "extra spicy" bump spice_min a bit
    if "extra spicy" in user_message.lower():
        filters["spice_min"] = max(filters.get("spice_min", 0), 7)

    # query DB
    results = query_database(filters)
    product_match = len(results) > 0

    # compute interest AFTER knowing whether matches exist
    interest = calculate_interest_score(user_message, product_match)

    # build reply text (clean, grouped by category)
    if not product_match:
        reply = "No matching products found in our database. What else can I help with?"
        return reply, interest

    # group by category
    grouped = {}
    for r in results:
        pid, name, category, price, spice, desc, tags = r
        grouped.setdefault(category or "Other", []).append({
            "name": name,
            "price": price,
            "spice": spice,
            "desc": desc,
            "tags": tags
        })

    # create readable response
    lines = ["Here are some recommendations from our database:"]
    for cat, items in grouped.items():
        lines.append(f"\n{cat}:")
        for it in items:
            desc_short = (it["desc"][:220] + "...") if it["desc"] and len(it["desc"]) > 220 else (it["desc"] or "")
            tag_str = f" (Tags: {it['tags']})" if it.get("tags") else ""
            lines.append(f"- {it['name']}: ${it['price']:.2f}, Spice {it['spice']}/10 - {desc_short}{tag_str}")

    reply = "\n".join(lines)
    return reply, interest
