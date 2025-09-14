# chat_engine.py
import os
import re
import sqlite3
from typing import Dict, List, Tuple

# Optional: Gemini integration (will be used if GEMINI_API_KEY present)
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
    GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
    else:
        model = None
except Exception:
    model = None

# ---------- Config ----------
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

# Normalized mapping of many user phrasings → DB filters
RULES = {
    # generic nouns (plural forms also useful)
    "burger": {"category": "burger"},
    "burgers": {"category": "burger"},
    "pizza": {"category": "pizza"},
    "pizzas": {"category": "pizza"},
    "wrap": {"category": "tacos & wraps"},
    "wraps": {"category": "tacos & wraps"},
    "taco": {"category": "tacos & wraps"},
    "tacos": {"category": "tacos & wraps"},
    "salad": {"category": "salads & healthy options"},
    "salads": {"category": "salads & healthy options"},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
    "pasta": {},   # keep empty so keyword fallback will search names/descriptions
    "curry": {},

    # Specific DB category phrases mapped to DB category words (normalization)
    "classic burger": {"category": "classic burgers"},
    "fusion burger": {"category": "fusion burgers"},
    "vegetarian burger": {"category": "vegetarian burgers"},
    "personal pizza": {"category": "personal pizza"},
    "gourmet pizza": {"category": "gourmet pizza"},
    "traditional pizza": {"category": "traditional pizza"},
    "fried chicken sandwich": {"category": "fried chicken sandwiches"},
    "fried chicken tenders": {"category": "fried chicken tenders"},
    "fried chicken wings": {"category": "fried chicken wings"},
    "sides": {"category": "sides & appetizers"},
    "shake": {"category": "shake"},
    "dessert": {"category": "dessert"},
    "breakfast": {"category": "breakfast items"},
    "specialty drink": {"category": "specialty drink"},
    "soda": {"category": "soda"},
    "bowl": {"category": "bowl"},
    "appetizer": {"category": "appetizer"},
}

# ---------- Interest Scoring ----------
def calculate_interest_score(message: str, product_match: bool) -> int:
    """
    Compute interest score from message. If product_match is False and the user
    included explicit constraints (diet/budget/spice), heavily penalize -> return 0.
    """
    score = 0
    m = message.lower()

    # Positive engagement
    if any(w in m for w in ['love', 'spicy', 'korean', 'fusion', 'burger', 'pizza', 'wrap']):
        score += ENGAGEMENT_FACTORS['specific_preferences']
    if 'vegetarian' in m or 'vegan' in m:
        score += ENGAGEMENT_FACTORS['dietary_restrictions']
    if 'under $' in m or re.search(r'less than \d', m) or re.search(r'\$\d+', m):
        score += ENGAGEMENT_FACTORS['budget_mention']
    if 'adventurous' in m:
        score += ENGAGEMENT_FACTORS['mood_indication']
    if '?' in message:
        score += ENGAGEMENT_FACTORS['question_asking']
    if any(w in m for w in ['amazing', 'perfect', 'love', 'delicious']):
        score += ENGAGEMENT_FACTORS['enthusiasm_words']
    if 'how much' in m or 'price' in m:
        score += ENGAGEMENT_FACTORS['price_inquiry']
    if any(phrase in m for phrase in ["i'll take", "i will take", "order", "add to cart"]):
        score += ENGAGEMENT_FACTORS['order_intent']

    # Negative signals
    if any(w in m for w in ['maybe', 'not sure']):
        score += NEGATIVE_FACTORS['hesitation']
    if 'too expensive' in m or 'expensive' in m:
        score += NEGATIVE_FACTORS['budget_concern']
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS['rejection']

    # If no DB match: apply stronger logic
    if not product_match:
        # If the user asked with specific constraints (diet, budget, spice, or specific item)
        explicit_constraint = any(k in m for k in [
            'vegetarian', 'vegan', 'under $', 'less than', 'less than', 'dollars', 'spicy', 'curry', 'pasta', 'wrap', 'burger', 'pizza', '$'
        ])
        if explicit_constraint:
            # user asked for something specific but DB returned nothing → 0 interest
            return 0
        else:
            # Otherwise, reduce score substantially to indicate low engagement
            score = max(0, score - 50)

    return max(0, min(100, int(score)))


# ---------- Database Query ----------
def query_database(filters: Dict) -> List[Tuple]:
    """
    Filters keys supported:
      - 'keyword' : string for free-text search (name/category/description/tags)
      - 'category' : normalized category string (will use LIKE)
      - 'price_max' : float
      - 'spice_min' : int
      - 'dietary_tags' : substring to match in dietary_tags
      - 'context' : conversation context (used to bias vegetarian/vegan)
    """
    conn = sqlite3.connect('foodiebot.db')
    c = conn.cursor()

    conditions = []
    params = []

    # Keyword fallback: always include if present
    if "keyword" in filters and filters["keyword"]:
        kw = filters["keyword"].lower().strip()
        kw_like = f"%{kw}%"
        conditions.append("""(
            LOWER(name) LIKE ? OR
            LOWER(category) LIKE ? OR
            LOWER(description) LIKE ? OR
            LOWER(dietary_tags) LIKE ? OR
            LOWER(mood_tags) LIKE ?
        )""")
        params += [kw_like, kw_like, kw_like, kw_like, kw_like]

    # Category filter: use LIKE for flexibility (e.g., 'burger' matches 'Classic Burgers')
    if 'category' in filters and filters['category']:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    # Price filter
    if 'price_max' in filters and filters['price_max'] is not None:
        conditions.append("price <= ?")
        params.append(filters['price_max'])

    # Spice filter
    if 'spice_min' in filters and filters['spice_min'] is not None:
        conditions.append("spice_level >= ?")
        params.append(filters['spice_min'])

    # Dietary tags
    if 'dietary_tags' in filters and filters['dietary_tags']:
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append(f"%{filters['dietary_tags'].lower()}%")

    # Context-aware vegetarian/vegan bias
    if 'context' in filters and filters['context']:
        ctx = filters['context'].lower()
        if 'vegetarian' in ctx or 'vegan' in ctx:
            conditions.append("(LOWER(dietary_tags) LIKE ? OR LOWER(dietary_tags) LIKE ?)")
            params.extend(['%vegetarian%', '%vegan%'])

    sql = """
        SELECT product_id, name, category, price, spice_level, description, dietary_tags
        FROM products
    """
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY popularity_score DESC LIMIT 12"

    results = c.execute(sql, params).fetchall()
    conn.close()

    if not results:
        # helpful debug in logs
        print("[DEBUG] query_database() no matches. filters:", filters)
    return results


# ---------- Response generation ----------
def generate_response(user_message: str, context: str = "") -> Tuple[str, int]:
    """
    Build filters from RULES + extracted budget, run DB, compute interest,
    then assemble safe response. Uses the model only to embellish, but falls back to
    a deterministic text response built from DB rows.
    """
    m = user_message.lower()
    filters: Dict = {'context': context, 'keyword': user_message}

    # Apply RULES: check for phrases / normalized keywords
    for keyword, rule in RULES.items():
        if keyword in m:
            # rule may be {} (marker) or contain category/spice/dietary_tags
            filters.update(rule)

    # Parse budget: "under $X" or "less than X dollars" or "$X"
    price_match = re.search(r'under \$(\d+\.?\d*)', m)
    if not price_match:
        price_match = re.search(r'less than (\d+\.?\d*) ?dollars', m)
    if not price_match:
        price_match = re.search(r'\$(\d+\.?\d*)', m)
    if price_match:
        try:
            filters['price_max'] = float(price_match.group(1))
        except Exception:
            pass

    # Parse explicit spice request like "extra spicy" or "spice 7"
    spice_match = re.search(r'(extra spicy|very spicy|spice(?: level)?[: ]?([0-9]+))', m)
    if spice_match:
        # If numeric provided use it, otherwise use a higher threshold
        if spice_match.group(2):
            try:
                filters['spice_min'] = int(spice_match.group(2))
            except Exception:
                filters['spice_min'] = 6
        else:
            filters['spice_min'] = 7

    # Query DB
    results = query_database(filters)
    product_match = bool(results)

    # Compute interest score (uses product_match)
    interest = calculate_interest_score(user_message, product_match)

    # Build product_info textual fallback (deterministic)
    if not results:
        product_info = "No matching products found in our database. What else can I help with?"
        # deterministic bot response
        bot_text = product_info
    else:
        # group results by category for a friendly listing
        groups: Dict[str, List[Tuple]] = {}
        for r in results:
            groups.setdefault(r[2], []).append(r)
        lines = []
        for cat, items in groups.items():
            lines.append(f"**{cat.title()}:**")
            for it in items:
                pid, name, category, price, spice, descr, tags = it
                tags = tags or ""
                lines.append(f"- {name} — ${price:.2f}, Spice {spice}/10 — {descr} (Tags: {tags})")
            lines.append("")  # blank line between groups
        bot_text = "\n".join(lines)

    # Try to use LLM to reword politely (non-essential). If fail, return deterministic bot_text.
    if model:
        try:
            prompt = f"""You are FoodieBot. User asked: "{user_message}". Context: {context}.
Recommend ONLY from these database products (do not invent):
{bot_text}
When no matches, say exactly: "No matching products found in our database. What else can I help with?"
Keep it concise."""
            out = model.generate_content(prompt, generation_config={"temperature": 0.45, "max_output_tokens": 220})
            return out.text.strip(), interest
        except Exception as e:
            print("[DEBUG] model call failed:", e)

    return bot_text, interest


# ---------- Logging ----------
def log_conversation(user_message: str, response: str, interest: int):
    conn = sqlite3.connect('foodiebot.db')
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
              (user_message, response, interest))
    conn.commit()
    conn.close()


# If executed directly for debugging
if __name__ == "__main__":
    print("chat_engine module test")
    print(query_database({'keyword': 'burger'}))
