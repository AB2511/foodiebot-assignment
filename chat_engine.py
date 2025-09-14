import os
import re
import sqlite3
import unicodedata
from dotenv import load_dotenv

# Optional: keep LLM config if you want to add model replies later.
try:
    import google.generativeai as genai
    load_dotenv()
    if os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        MODEL_AVAILABLE = True
    else:
        MODEL_AVAILABLE = False
except Exception:
    MODEL_AVAILABLE = False

# ---------- Scoring ----------
ENGAGEMENT_FACTORS = {
    "specific_preferences": 15,
    "dietary_restrictions": 10,
    "budget_mention": 5,
    "mood_indication": 20,
    "question_asking": 10,
    "enthusiasm_words": 8,
    "price_inquiry": 25,
    "order_intent": 30,
}
NEGATIVE_FACTORS = {
    "hesitation": -10,
    "budget_concern": -15,
    "dietary_conflict": -20,
    "rejection": -25,
    "delay_response": -5,
}

# Normalized rules (singular/plural + DB categories)
RULES = {
    "burger": {"category": "Burger"},
    "burgers": {"category": "Burger"},
    "pizza": {"category": "Pizza"},
    "pizzas": {"category": "Pizza"},
    "wrap": {"category": "Tacos & Wraps"},
    "wraps": {"category": "Tacos & Wraps"},
    "taco": {"category": "Tacos & Wraps"},
    "tacos": {"category": "Tacos & Wraps"},
    "salad": {"category": "Salads & Healthy Options"},
    "salads": {"category": "Salads & Healthy Options"},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
    # example DB categories — add more keys if needed
    "classic burger": {"category": "Classic Burgers"},
    "fusion burger": {"category": "Fusion Burgers"},
    "vegetarian burger": {"category": "Vegetarian Burgers"},
    "personal pizza": {"category": "Personal Pizza"},
    "traditional pizza": {"category": "Traditional Pizza"},
    "gourmet pizza": {"category": "Gourmet Pizza"},
    "fried chicken sandwich": {"category": "Fried Chicken Sandwiches"},
    "fried chicken tenders": {"category": "Fried Chicken Tenders"},
    "fried chicken wings": {"category": "Fried Chicken Wings"},
    "sides": {"category": "Sides & Appetizers"},
    "sandwich": {"category": "Sandwich"},
    "shake": {"category": "Shake"},
    "dessert": {"category": "Dessert"},
    "breakfast": {"category": "Breakfast Items"},
    "specialty drink": {"category": "Specialty Drink"},
    "soda": {"category": "Soda"},
    "bowl": {"category": "Bowl"},
    "appetizer": {"category": "Appetizer"},
}

# ---------- Helpers ----------
def _clean_text(s: str) -> str:
    if not s:
        return ""
    # normalize unicode, remove zero-width and control chars
    s = unicodedata.normalize("NFKC", str(s))
    # remove zero-width spaces and FEFF
    s = re.sub(r"[\u200B-\u200D\uFEFF]", "", s)
    # remove other control characters except newline/tab
    s = "".join(ch for ch in s if ch.isprintable() or ch in "\n\t")
    return s.strip()

def _parse_price(text: str):
    """Return float price if pattern found, else None. Supports 'under $X' and 'less than X dollars'."""
    if not text:
        return None
    t = text.lower()
    m = re.search(r"under ?\$\s*([0-9]+(?:\.[0-9]+)?)", t)
    if not m:
        m = re.search(r"less than\s*([0-9]+(?:\.[0-9]+)?)\s*dollars?", t)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None

def calculate_interest_score(message: str, product_match: bool = True) -> int:
    m = (message or "").lower()
    score = 0

    # Positive engagement factors
    if any(w in m for w in ["love", "spicy", "korean", "fusion", "burger", "pizza", "wrap"]):
        score += ENGAGEMENT_FACTORS["specific_preferences"]
    if "vegetarian" in m or "vegan" in m:
        score += ENGAGEMENT_FACTORS["dietary_restrictions"]
    if "under $" in m or "less than" in m:
        score += ENGAGEMENT_FACTORS["budget_mention"]
    if "adventurous" in m:
        score += ENGAGEMENT_FACTORS["mood_indication"]
    if "?" in message:
        score += ENGAGEMENT_FACTORS["question_asking"]
    if any(w in m for w in ["amazing", "perfect", "love"]):
        score += ENGAGEMENT_FACTORS["enthusiasm_words"]
    if "how much" in m:
        score += ENGAGEMENT_FACTORS["price_inquiry"]
    if any(phrase in m for phrase in ["i'll take", "i will take", "order", "add to cart"]):
        score += ENGAGEMENT_FACTORS["order_intent"]

    # Negative factors
    if any(w in m for w in ["maybe", "not sure"]):
        score += NEGATIVE_FACTORS["hesitation"]
    if "too expensive" in m:
        score += NEGATIVE_FACTORS["budget_concern"]
    if not product_match and any(w in m for w in ["spicy", "vegetarian", "vegan", "burger", "pizza", "curry", "pasta"]):
        # Stronger penalty if user asks for something but no match exists
        score += NEGATIVE_FACTORS["dietary_conflict"]
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS["rejection"]

    # If no product matches at all, cap score based on positive engagement only
    if not product_match:
        # remove specific_preferences and dietary_restrictions if no match
        for w in ["burger", "pizza", "wrap", "vegetarian", "vegan", "curry", "pasta"]:
            if w in m:
                score -= ENGAGEMENT_FACTORS.get("specific_preferences", 0) if w in ["burger", "pizza", "wrap", "curry", "pasta"] else ENGAGEMENT_FACTORS.get("dietary_restrictions", 0)

    return max(0, min(100, int(round(score))))
# ---------- DB query ----------
def query_database(filters: dict):
    """
    Returns list of rows:
    (product_id, name, category, price, spice_level, description, dietary_tags)
    """
    conn = sqlite3.connect("foodiebot.db")
    c = conn.cursor()

    conditions = []
    params = []

    # category (LIKE)
    if "category" in filters and filters["category"]:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    # price
    if "price_max" in filters and filters["price_max"] is not None:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    # spice
    if "spice_min" in filters and filters["spice_min"] is not None:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # dietary_tags
    if "dietary_tags" in filters and filters["dietary_tags"]:
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append(f"%{filters['dietary_tags'].lower()}%")

    # context enforced vegetarian/vegan
    if "context" in filters and filters["context"]:
        ctxt = filters["context"].lower()
        if "vegetarian" in ctxt or "vegan" in ctxt:
            conditions.append("(LOWER(dietary_tags) LIKE ? OR LOWER(dietary_tags) LIKE ?)")
            params.extend(["%vegetarian%", "%vegan%"])

    # keyword fallback (only if present). If the keyword was clearly a category term, we avoid repeating.
    if "keyword" in filters and filters["keyword"]:
        kw = filters["keyword"].lower().strip()
        is_cat_like = any(k in kw and RULES[k].get("category") for k in RULES.keys())
        if not is_cat_like:
            kw_like = f"%{kw}%"
            conditions.append("""(
                LOWER(name) LIKE ? OR
                LOWER(category) LIKE ? OR
                LOWER(description) LIKE ? OR
                LOWER(dietary_tags) LIKE ? OR
                LOWER(mood_tags) LIKE ?
            )""")
            params += [kw_like] * 5

    sql = """
        SELECT product_id, name, category, price, spice_level, description, dietary_tags
        FROM products
    """
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY popularity_score DESC LIMIT 20"

    try:
        rows = c.execute(sql, params).fetchall()
    except Exception as e:
        print("SQL ERROR:", e, sql, params)
        rows = []
    conn.close()

    # sanitize fields
    cleaned = []
    for r in rows:
        cleaned.append((
            _clean_text(r[0]),
            _clean_text(r[1]),
            _clean_text(r[2]),
            float(r[3]) if r[3] is not None else 0.0,
            int(r[4]) if r[4] is not None else 0,
            _clean_text(r[5]),
            _clean_text(r[6]),
        ))
    return cleaned

# ---------- Generate response (constructs stable summary) ----------
def generate_response(user_message: str, context: str = ""):
    """
    Returns: (bot_text, interest_int, results_list)
    results_list is the same rows returned from query_database
    """
    user_message = _clean_text(user_message)
    filters = {"context": context}

    # try rule-based detection (longer keys first)
    for key in sorted(RULES.keys(), key=lambda x: -len(x)):
        if key in user_message:
            filters.update(RULES[key])
            break

    # price parsing
    price_val = _parse_price(user_message)
    if price_val is not None:
        filters["price_max"] = price_val

    # always include keyword fallback
    filters["keyword"] = user_message

    # fetch results
    results = query_database(filters)
    product_match = bool(results)

    # interest score
    interest = calculate_interest_score(user_message, product_match)

    # Build a clean, human-readable summary text (we do this in code to avoid LLM formatting issues)
    if not results:
        bot_text = 'No matching products found in our database. What else can I help with?'
    else:
        # group by category for nicer display
        by_cat = {}
        for row in results:
            pid, name, category, price, spice, desc, tags = row
            by_cat.setdefault(category or "Other", []).append(row)

        lines = ["Here are the results from our database:"]
        for cat in sorted(by_cat.keys()):
            lines.append(f"\n{cat}:")
            for r in by_cat[cat]:
                _, name, _, price, spice, desc, tags = r
                short_desc = (desc[:140] + "...") if desc and len(desc) > 140 else desc
                tag_text = f" (Tags: {tags})" if tags else ""
                lines.append(f"- {name} — ${price:.2f}, Spice {spice}/10{tag_text}")
                if short_desc:
                    lines.append(f"  {short_desc}")
        bot_text = "\n".join(lines)

    # return bot_text, interest, structured results (so UI & logs can use structured data)
    return bot_text, interest, results

# ---------- Log conversation ----------
def log_conversation(user_message: str, response: str, interest: int):
    conn = sqlite3.connect("foodiebot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            bot_response TEXT,
            interest_score INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("INSERT INTO conversations (user_message, bot_response, interest_score) VALUES (?, ?, ?)",
              (user_message, response, int(interest)))
    conn.commit()
    conn.close()  
