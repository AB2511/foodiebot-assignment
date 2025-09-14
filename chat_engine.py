# chat_engine.py
import os
import re
import sqlite3
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Scoring constants
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

# Normalized keyword -> DB category/tag map (include plurals and DB categories)
RULES = {
    # generic
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
    # specific DB categories (as seen in your DB)
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

# ---------- Helper functions ----------
def _clean_text(s: str) -> str:
    return (s or "").lower().strip()

def _parse_price(user_text: str):
    t = user_text.lower()
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
    m = _clean_text(message)
    score = 0

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

    # negatives
    if any(w in m for w in ["maybe", "not sure"]):
        score += NEGATIVE_FACTORS["hesitation"]
    if "too expensive" in m:
        score += NEGATIVE_FACTORS["budget_concern"]
    if not product_match and any(w in m for w in ["spicy", "vegetarian", "vegan", "burger", "pizza"]):
        score += NEGATIVE_FACTORS["dietary_conflict"]
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS["rejection"]

    return max(0, min(100, int(round(score))))

# ---------- Database query ----------
def query_database(filters: dict):
    """
    filters may contain:
      - category (string) => will use LIKE '%category%'
      - keyword (string) => fallback full-text LIKE search on name/description/tags
      - spice_min (int)
      - price_max (float)
      - dietary_tags (string)
      - context (string) optional
    Returns list of rows (product_id, name, category, price, spice_level, description, dietary_tags).
    """
    conn = sqlite3.connect("foodiebot.db")
    c = conn.cursor()

    conditions = []
    params = []

    # If category present, prefer category match
    if "category" in filters and filters["category"]:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    # Price
    if "price_max" in filters and filters["price_max"] is not None:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    # Spice
    if "spice_min" in filters and filters["spice_min"] is not None:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # Dietary
    if "dietary_tags" in filters and filters["dietary_tags"]:
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append(f"%{filters['dietary_tags'].lower()}%")

    # Context enforced vegetarian/vegan
    if "context" in filters and filters["context"]:
        ctxt = filters["context"].lower()
        if "vegetarian" in ctxt or "vegan" in ctxt:
            conditions.append("(LOWER(dietary_tags) LIKE ? OR LOWER(dietary_tags) LIKE ?)")
            params.extend(["%vegetarian%", "%vegan%"])

    # Keyword fallback (only if no stronger category filter or as additional filter)
    if "keyword" in filters and filters["keyword"]:
        kw = filters["keyword"].lower().strip()
        # if keyword looks like a category (single word 'burgers' etc.) skip adding a generic clause
        is_cat_like = False
        for k in RULES.keys():
            if k in kw and RULES[k].get("category"):
                is_cat_like = True
                break
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

    sql += " ORDER BY popularity_score DESC LIMIT 10"
    try:
        results = c.execute(sql, params).fetchall()
    except Exception as e:
        # debug print
        print("SQL Error:", e, sql, params)
        results = []
    conn.close()
    return results

# ---------- Generate response ----------
def generate_response(user_message: str, context: str = ""):
    """
    Returns: (bot_text_response, interest_score(int), results(list-of-rows))
    results is the rows returned from query_database (so UI and LLM share same products).
    """
    m = _clean_text(user_message)
    filters = {"context": context}

    # 1) Try to detect explicit category/keywords using RULES (longer matches first)
    sorted_keys = sorted(RULES.keys(), key=lambda x: -len(x))
    for key in sorted_keys:
        if key in m:
            filters.update(RULES[key])
            # prefer category match over generic keyword fallback
            break

    # 2) price detection
    price = _parse_price(user_message)
    if price is not None:
        filters["price_max"] = price

    # 3) if we didn't detect category/diet, always provide a keyword fallback
    filters["keyword"] = user_message.strip()

    # 4) Query DB for real results (so both UI and prompt use them)
    results = query_database(filters)
    product_match = bool(results)

    # 5) recalc interest after knowing if matches exist
    interest = calculate_interest_score(user_message, product_match)

    # 6) build strict product_info text for the LLM prompt (only the rows returned)
    if not results:
        product_info = "No matches found."
    else:
        lines = []
        for r in results[:8]:
            # r: product_id, name, category, price, spice_level, description, dietary_tags
            lines.append(f"- {r[1]} [{r[2]}]: ${r[3]:.2f}, Spice {r[4]}/10 - {r[5]} (Tags: {r[6]})")
        product_info = "\n".join(lines)

    prompt = f"""
You are FoodieBot. Use the following context: {context}
User: {user_message}

Recommend ONLY from these database products (use only the names/lines below). If no matches, say exactly: "No matching products found in our database. What else can I help with?"
{product_info}

Respect user's dietary/budget/spice constraints. Do NOT invent products not listed above. Keep language natural and concise.
"""
    try:
        response_text = model.generate_content(
            prompt,
            generation_config={"temperature": 0.6, "max_output_tokens": 300},
        ).text
    except Exception as e:
        # If LLM fails, still return a fallback textual response so UI doesn't break
        response_text = (
            "Sorry — I'm temporarily unable to generate a natural response. "
            + ("No matching products found in our database. What else can I help with?" if not product_match else product_info)
        )

    return response_text.strip(), interest, results

# ---------- Logging ----------
def log_conversation(user_message: str, response: str, interest: int):
    conn = sqlite3.connect("foodiebot.db")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            bot_response TEXT,
            interest_score INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        "INSERT INTO conversations (user_message, bot_response, interest_score) VALUES (?, ?, ?)",
        (user_message, response, int(interest)),
    )
    conn.commit()
    conn.close()
