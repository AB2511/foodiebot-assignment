import sqlite3
import re

# ---------- Keyword Normalization & Mapping ----------
RULES = {
    # Generic keywords → category
    "burger": {"category": "Burger"},
    "burgers": {"category": "Burger"},
    "pizza": {"category": "Pizza"},
    "pizzas": {"category": "Pizza"},
    "wrap": {"category": "Wrap"},
    "wraps": {"category": "Wrap"},
    "taco": {"category": "Tacos & Wraps"},
    "tacos": {"category": "Tacos & Wraps"},
    "salad": {"category": "Salads & Healthy Options"},
    "salads": {"category": "Salads & Healthy Options"},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
}

# ---------- Engagement / Interest ----------
ENGAGEMENT_FACTORS = {
    "specific_preferences": 15,
    "dietary_restrictions": 10,
    "budget_mention": 5,
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

# ---------- Normalize & Extract ----------
def extract_keywords(user_message):
    text = user_message.lower()
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    keywords = []
    for key in RULES.keys():
        if key in text:
            keywords.append(key)
    return keywords

# ---------- Interest Score ----------
def calculate_interest_score(message, product_match=True):
    score = 0
    m = message.lower()
    if any(word in m for word in ["burger", "pizza", "wrap", "taco", "salad"]):
        score += ENGAGEMENT_FACTORS["specific_preferences"]
    if "vegetarian" in m or "vegan" in m:
        score += ENGAGEMENT_FACTORS["dietary_restrictions"]
    if "under $" in m or "less than" in m:
        score += ENGAGEMENT_FACTORS["budget_mention"]
    if "?" in m:
        score += ENGAGEMENT_FACTORS["question_asking"]
    if any(word in m for word in ["amazing", "perfect", "love"]):
        score += ENGAGEMENT_FACTORS["enthusiasm_words"]
    if "how much" in m:
        score += ENGAGEMENT_FACTORS["price_inquiry"]
    if any(phrase in m for phrase in ["i'll take", "i will take", "order", "add to cart"]):
        score += ENGAGEMENT_FACTORS["order_intent"]
    # Negative factors
    if any(word in m for word in ["maybe", "not sure"]):
        score += NEGATIVE_FACTORS["hesitation"]
    if "too expensive" in m:
        score += NEGATIVE_FACTORS["budget_concern"]
    if not product_match and any(word in m for word in ["spicy", "vegetarian", "vegan", "burger", "pizza"]):
        score += NEGATIVE_FACTORS["dietary_conflict"]
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS["rejection"]
    return max(0, min(100, score))

# ---------- Query Database ----------
def query_database(filters):
    conn = sqlite3.connect("foodiebot.db")
    c = conn.cursor()

    conditions = []
    params = []

    # Keyword search
    if "keyword" in filters:
        kw = f"%{filters['keyword'].lower()}%"
        conditions.append("(LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(description) LIKE ?)")
        params += [kw]*3

    # Category
    if "category" in filters:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    # Price max
    if "price_max" in filters:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    # Spice
    if "spice_min" in filters:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # Dietary
    if "dietary_tags" in filters:
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append(f"%{filters['dietary_tags'].lower()}%")

    sql = "SELECT product_id, name, category, price, spice_level, description, dietary_tags FROM products"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY popularity_score DESC LIMIT 5"

    results = c.execute(sql, params).fetchall()
    conn.close()
    return results

# ---------- Generate Response ----------
def generate_response(user_message):
    filters = {}
    keywords = extract_keywords(user_message)
    for k in keywords:
        filters.update(RULES[k])

    # Price parsing
    price_match = re.search(r"under \$([0-9]+\.?[0-9]*)", user_message.lower())
    if price_match:
        filters["price_max"] = float(price_match.group(1))

    results = query_database(filters)
    product_match = bool(results)
    interest = calculate_interest_score(user_message, product_match)

    if not results:
        response = "No matching products found in our database. What else can I help with?"
    else:
        lines = []
        cat_map = {}
        for r in results:
            cat_map.setdefault(r[2], []).append(f"{r[1]}: ${r[3]}, Spice {r[4]}/10 - {r[5]} (Tags: {r[6]})")
        for cat, items in cat_map.items():
            lines.append(f"**{cat}**:\n" + "\n".join(items))
        response = "Here are some recommendations from our database:\n\n" + "\n\n".join(lines)

    return response, interest

# ---------- Log Conversation ----------
def log_conversation(user_message, response, interest):
    conn = sqlite3.connect("foodiebot.db")
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
    c.execute(
        "INSERT INTO conversations (user_message, bot_response, interest_score) VALUES (?, ?, ?)",
        (user_message, response, interest)
    )
    conn.commit()
    conn.close()
