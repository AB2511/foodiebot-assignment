import os
import re
import sqlite3
from dotenv import load_dotenv
import google.generativeai as genai

# Load API key
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# ---------- Engagement / Interest ----------
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

# ---------- Keyword → DB rules ----------
RULES = {
    # Generic keywords
    "burger": {"category": ["Classic Burgers", "Fusion Burgers", "Vegetarian Burgers"]},
    "pizza": {"category": ["Gourmet Pizza", "Personal Pizza", "Traditional Pizza"]},
    "wrap": {"category": ["Wraps"]},
    "taco": {"category": ["Tacos", "Tacos & Wraps"]},
    "salad": {"category": ["Salads & Healthy Options"]},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
    "bowl": {"category": ["Bowl"]},
    "dessert": {"category": ["Dessert"]},
    "shake": {"category": ["Shake"]},
    "sides": {"category": ["Sides & Appetizers"]},
    "breakfast": {"category": ["Breakfast Items"]},
    "specialty drink": {"category": ["Specialty Drink"]},
    "soda": {"category": ["Soda"]},
}

# ---------- Interest Score ----------
def calculate_interest_score(message, product_match=True):
    score = 0
    m = message.lower()

    # Engagement factors
    if any(word in m for word in ['love', 'spicy', 'korean', 'fusion', 'burger', 'pizza', 'wrap']):
        score += ENGAGEMENT_FACTORS['specific_preferences']
    if 'vegetarian' in m or 'vegan' in m:
        score += ENGAGEMENT_FACTORS['dietary_restrictions']
    if 'under $' in m or 'less than' in m:
        score += ENGAGEMENT_FACTORS['budget_mention']
    if 'adventurous' in m:
        score += ENGAGEMENT_FACTORS['mood_indication']
    if '?' in message:
        score += ENGAGEMENT_FACTORS['question_asking']
    if any(word in m for word in ['amazing', 'perfect', 'love']):
        score += ENGAGEMENT_FACTORS['enthusiasm_words']
    if 'how much' in m:
        score += ENGAGEMENT_FACTORS['price_inquiry']
    if any(phrase in m for phrase in ["i'll take", "i will take", "order", "add to cart"]):
        score += ENGAGEMENT_FACTORS['order_intent']

    # Negative factors
    if any(word in m for word in ['maybe', 'not sure']):
        score += NEGATIVE_FACTORS['hesitation']
    if 'too expensive' in m:
        score += NEGATIVE_FACTORS['budget_concern']
    if not product_match and any(word in m for word in ['spicy', 'vegetarian', 'vegan', 'burger', 'pizza']):
        score += NEGATIVE_FACTORS['dietary_conflict']
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS['rejection']

    return max(0, min(100, score))

# ---------- Database Query ----------
def query_database(filters):
    conn = sqlite3.connect('foodiebot.db')
    c = conn.cursor()

    conditions = []
    params = []

    # Keyword fallback: search in name and category
    if "keyword" in filters and filters["keyword"]:
        kw = f"%{filters['keyword'].lower()}%"
        conditions.append("(LOWER(name) LIKE ? OR LOWER(category) LIKE ?)")
        params += [kw, kw]

    # Category filter (handle list)
    if "category" in filters:
        cats = filters["category"]
        if isinstance(cats, list):
            conditions.append("(" + " OR ".join(["LOWER(category) LIKE ?"]*len(cats)) + ")")
            params.extend([c.lower() for c in cats])
        else:
            conditions.append("LOWER(category) LIKE ?")
            params.append(cats.lower())

    # Price
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

    sql = """
        SELECT product_id, name, category, price, spice_level, description, dietary_tags
        FROM products
    """
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY popularity_score DESC LIMIT 5"
    results = c.execute(sql, params).fetchall()
    conn.close()

    return results

# ---------- Generate Response ----------
def generate_response(user_message, context=""):
    user_lower = user_message.lower()

    # Detect relevant keywords
    keywords_found = [k for k in RULES if k in user_lower]
    filters = {'context': context}
    if keywords_found:
        keyword = keywords_found[0]  # pick first match
        filters.update(RULES[keyword])
        filters['keyword'] = keyword
    else:
        # fallback to longest word
        word = next((w for w in user_lower.split() if len(w) > 3), "")
        filters['keyword'] = word

    # Budget parsing
    price_match = re.search(r'under \$([0-9]+\.?[0-9]*)', user_lower)
    if not price_match:
        price_match = re.search(r'less than ([0-9]+\.?[0-9]*) ?dollars', user_lower)
    if price_match:
        filters['price_max'] = float(price_match.group(1))

    # Query DB
    results = query_database(filters)
    product_match = bool(results)

    # Interest
    interest = calculate_interest_score(user_message, product_match)

    # Build product info
    if not results:
        product_info = "No matches found."
    else:
        product_info = "\n".join(
            [f"- {r[1]} ({r[2]}): ${r[3]}, Spice {r[4]}/10 - {r[5]} (Tags: {r[6]})" for r in results]
        )

    prompt = f"""
You are FoodieBot. Context: {context}.
User: {user_message}.
Recommend ONLY from these database products:
{product_info}

If no matches, say: "No matching products found in our database. What else can I help with?"
Never invent products. Respect previous preferences (vegetarian, vegan, budget).
"""
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.6, "max_output_tokens": 250}
    ).text

    return response, interest

# ---------- Log Conversation ----------
def log_conversation(user_message, response, interest):
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
    c.execute(
        "INSERT INTO conversations (user_message, bot_response, interest_score) VALUES (?, ?, ?)",
        (user_message, response, interest)
    )
    conn.commit()
    conn.close()
