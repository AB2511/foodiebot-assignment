# chat_engine.py
import os
import re
import sqlite3
from typing import Dict, Any, List, Tuple

# Defer LLM setup to runtime to avoid import-time failures
try:
    from dotenv import load_dotenv
    import google.generativeai as genai
    load_dotenv()
    GEMINI_KEY = os.getenv("GEMINI_API_KEY") or None
except Exception:
    GEMINI_KEY = None

DB_PATH = "foodiebot.db"

# Normalized keyword -> DB hints (plural forms included)
RULES = {
    "burger": {"category": "Burgers"},
    "burgers": {"category": "Burgers"},
    "classic burger": {"category": "Classic Burgers"},
    "fusion burger": {"category": "Fusion Burgers"},
    "vegetarian burger": {"category": "Vegetarian Burgers"},
    "vegan": {"dietary_tags": "vegan"},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "pizza": {"category": "Pizza"},
    "pizzas": {"category": "Pizza"},
    "personal pizza": {"category": "Personal Pizza"},
    "traditional pizza": {"category": "Traditional Pizza"},
    "wrap": {"category": "Tacos & Wraps"},
    "wraps": {"category": "Tacos & Wraps"},
    "taco": {"category": "Tacos"},
    "tacos": {"category": "Tacos"},
    "salad": {"category": "Salads & Healthy Options"},
    "appetizer": {"category": "Appetizer"},
    "side": {"category": "Sides & Appetizers"},
    "dessert": {"category": "Dessert"},
    "spicy": {"spice_min": 5},
    "extra spicy": {"spice_min": 8},
    "mild": {"spice_min": 0},
}

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

STOP_WORDS = {
    "show", "me", "i", "want", "please", "give", "some", "something", "any", "want", "need",
    "the", "a", "an", "for", "under", "less", "than", "dollars", "in", "on", "with"
}

def _connect():
    return sqlite3.connect(DB_PATH)

def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokenize_and_filter(s: str) -> List[str]:
    s = _normalize_text(s)
    tokens = [t for t in s.split() if t and t not in STOP_WORDS]
    # simple stemming: strip trailing 's' for plurals ("burgers" -> "burger")
    tokens = [t[:-1] if t.endswith("s") and len(t) > 3 else t for t in tokens]
    return tokens

def _parse_budget(text: str):
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
    if 'too expensive' in m:
        score += NEGATIVE_FACTORS['budget_concern']
    if not product_match and any(w in m for w in ['spicy', 'vegetarian', 'vegan', 'burger', 'pizza', 'wrap']):
        score += NEGATIVE_FACTORS['dietary_conflict']
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS['rejection']
    return max(0, min(100, score))

def query_database(filters: Dict[str, Any]) -> List[Tuple]:
    """
    filters may contain:
      - keyword_tokens: List[str]
      - category
      - price_max
      - spice_min
      - dietary_tags
      - context
    """
    conn = _connect()
    c = conn.cursor()
    conditions = []
    params = []

    # Category filter (match with LIKE)
    if filters.get("category"):
        conditions.append("LOWER(category) LIKE ?")
        params.append("%" + filters["category"].lower() + "%")

    # Price filter
    if filters.get("price_max") is not None:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    # Spice
    if filters.get("spice_min") is not None:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # dietary tags
    if filters.get("dietary_tags"):
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append("%" + filters["dietary_tags"].lower() + "%")

    # context aware vegetarian/vegan
    if filters.get("context"):
        ctx = filters["context"].lower()
        if "vegetarian" in ctx or "vegan" in ctx:
            conditions.append("(LOWER(dietary_tags) LIKE ? OR LOWER(dietary_tags) LIKE ?)")
            params += ["%vegetarian%", "%vegan%"]

    # Keyword tokens: create a single big OR clause where any token matches any searchable column
    token_list = filters.get("keyword_tokens") or []
    if token_list:
        token_clauses = []
        for tok in token_list:
            tok_w = "%" + tok.lower() + "%"
            token_clauses.append("(LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(description) LIKE ? OR LOWER(dietary_tags) LIKE ? OR LOWER(mood_tags) LIKE ?)")
            params += [tok_w, tok_w, tok_w, tok_w, tok_w]
        # join token_clauses with OR (so if any token matches)
        if token_clauses:
            conditions.append("(" + " OR ".join(token_clauses) + ")")

    sql = ("SELECT product_id, name, category, price, spice_level, description, dietary_tags "
           "FROM products")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY popularity_score DESC LIMIT 12"

    rows = c.execute(sql, params).fetchall()
    conn.close()
    return rows

def _build_text_reply_from_results(results: List[Tuple]) -> str:
    grouped = {}
    for r in results:
        pid, name, category, price, spice, desc, tags = r
        grouped.setdefault(category or "Other", []).append((name, price, spice, desc, tags))
    lines = ["Here are some recommendations from our database:"]
    for cat, items in grouped.items():
        lines.append(f"\n{cat}:")
        for name, price, spice, desc, tags in items:
            short = (desc[:200] + "...") if desc and len(desc) > 200 else (desc or "")
            tag_str = f" (Tags: {tags})" if tags else ""
            lines.append(f"- {name}: ${price:.2f}, Spice {spice}/10 - {short}{tag_str}")
    return "\n".join(lines)

def generate_response(user_message: str, context: str = "") -> Tuple[str, int]:
    # Normalize tokens
    clean = _normalize_text(user_message)
    tokens = _tokenize_and_filter(clean)

    # Start filters
    filters: Dict[str, Any] = {"context": context, "keyword_tokens": tokens}

    # Apply RULES if any keyword is present (more specific rules override)
    for k, rule in RULES.items():
        if k in clean:
            filters.update(rule)

    # Budget parsing
    budget = _parse_budget(user_message)
    if budget is not None:
        filters["price_max"] = budget

    # Spice handling
    if "extra spicy" in user_message.lower():
        filters["spice_min"] = max(filters.get("spice_min", 0), 7)
    elif "spicy" in user_message.lower():
        filters["spice_min"] = max(filters.get("spice_min", 0), 5)

    # Query DB
    results = query_database(filters)
    product_match = bool(results)

    # Interest score (recalculate after match)
    interest = calculate_interest_score(user_message, product_match)

    # If no match -> clear helpful reply
    if not product_match:
        return "No matching products found in our database. What else can I help with?", interest

    # Build product summary text
    product_text = _build_text_reply_from_results(results)

    # If GEMINI key available, call LLM for a nicer, natural reply (but it's optional)
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""You are FoodieBot. Use only the following product list to answer the user.
User: {user_message}
Products:
{product_text}
Keep the reply friendly and do not invent anything."""
            gen_resp = model.generate_content(prompt, generation_config={"temperature": 0.4, "max_output_tokens": 220})
            return gen_resp.text.strip(), interest
        except Exception:
            # If LLM fails, fall back to deterministic product_text
            return product_text, interest

    # No LLM configured -> deterministic product text
    return product_text, interest

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
