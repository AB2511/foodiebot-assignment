# chat_engine.py
import sqlite3
import re
from typing import Dict, Any, List, Tuple

DB_PATH = "foodiebot.db"

# ------- RULES: normalized keyword -> DB hints -------
RULES = {
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
    "appetizer": {"category": "Appetizer"},
    "side": {"category": "Sides & Appetizers"},
    "dessert": {"category": "Dessert"},
    "shake": {"category": "Shake"},
    "spicy": {"spice_min": 5},
    "extra spicy": {"spice_min": 8},
    "mild": {"spice_min": 0},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
}

# ------- Scoring (kept simple and deterministic) -------
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

def _connect():
    return sqlite3.connect(DB_PATH)

def _normalize_text_for_keyword(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _parse_budget_from_text(text: str):
    t = text.lower()
    # under $X
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

# ---------------- DB query ----------------
def query_database(filters: Dict[str, Any]) -> List[Tuple]:
    """
    filters keys:
      - keyword (string)
      - category (string)
      - price_max (float)
      - spice_min (int)
      - dietary_tags (string)
      - context (string)
    """
    conn = _connect()
    c = conn.cursor()
    conditions = []
    params = []

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

    if filters.get("category"):
        conditions.append("LOWER(category) LIKE ?")
        params.append("%" + filters["category"].lower() + "%")

    if filters.get("price_max") is not None:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    if filters.get("spice_min") is not None:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    if filters.get("dietary_tags"):
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append("%" + filters["dietary_tags"].lower() + "%")

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

# ---------------- Response generation ----------------
def generate_response(user_message: str, context: str = "") -> Tuple[str, int]:
    """
    Returns (response_text, interest_score)
    """
    clean = _normalize_text_for_keyword(user_message)
    filters: Dict[str, Any] = {"keyword": clean, "context": context}

    # apply RULES
    for k, rule in RULES.items():
        if k in clean:
            filters.update(rule)

    # budget parsing
    price_max = _parse_budget_from_text(user_message)
    if price_max is not None:
        filters["price_max"] = price_max

    # spice boost for "extra spicy"
    if "extra spicy" in user_message.lower():
        filters["spice_min"] = max(filters.get("spice_min", 0), 7)

    results = query_database(filters)
    product_match = len(results) > 0

    interest = calculate_interest_score(user_message, product_match)

    if not product_match:
        return "No matching products found in our database. What else can I help with?", interest

    # group by category for readability
    grouped = {}
    for r in results:
        pid, name, category, price, spice, desc, tags = r
        grouped.setdefault(category or "Other", []).append((name, price, spice, desc, tags))

    lines = ["Here are some recommendations from our database:"]
    for cat, items in grouped.items():
        lines.append(f"\n{cat}:")
        for name, price, spice, desc, tags in items:
            desc_short = (desc[:220] + "...") if desc and len(desc) > 220 else (desc or "")
            tag_str = f" (Tags: {tags})" if tags else ""
            lines.append(f"- {name}: ${price:.2f}, Spice {spice}/10 - {desc_short}{tag_str}")

    reply = "\n".join(lines)
    return reply, interest

# ---------------- Logging ----------------
def log_conversation(user_message: str, response: str, interest: int):
    conn = _connect()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            bot_response TEXT,
            interest_score INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute("INSERT INTO conversations (user_message, bot_response, interest_score) VALUES (?, ?, ?)",
              (user_message, response, int(interest)))
    conn.commit()
    conn.close()
