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
    "burger": {},
    "pizza": {},
    "wrap": {},
    "taco": {},
    "salad": {},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
}

# ---------- Interest Score ----------
def calculate_interest_score(message, product_match=True):
    score = 0
    m = message.lower()

    # Engagement
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

    # Negative
    if any(word in m for word in ['maybe', 'not sure']):
        score += NEGATIVE_FACTORS['hesitation']
    if 'too expensive' in m:
        score += NEGATIVE_FACTORS['budget_concern']
    if not product_match and any(word in m for word in ['spicy', 'vegetarian', 'vegan', 'burger', 'pizza']):
        score += NEGATIVE_FACTORS['dietary_conflict']
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS['rejection']

    return max(0, min(100, score))

# ---------- Query Database ----------
def query_database(filters):
    conn = sqlite3.connect('foodiebot.db')
    c = conn.cursor()

    conditions = []
    params = []

    # Keyword fallback
    if "keyword" in filters:
        kw = f"%{filters['keyword'].lower()}%"
        conditions.append("""(
            LOWER(name) LIKE ?
            OR LOWER(category) LIKE ?
            OR LOWER(description) LIKE ?
            OR LOWER(dietary_tags) LIKE ?
            OR LOWER(mood_tags) LIKE ?
        )""")
        params += [kw]*5

    # Category filter (optional)
    if 'category' in filters:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    # Price filter
    if "price_max" in filters:
        conditions.append("price <= ?")
        params.append(filters["price_max"])

    # Spice filter
    if "spice_min" in filters:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # Dietary filter
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

    if not results:
        print("[DEBUG] No DB matches with filters:", filters)
    return results

# ---------- Generate Response ----------
def generate_response(user_message, context=""):
    filters = {'context': context, 'keyword': user_message}

    # Apply RULES
    for keyword, rule in RULES.items():
        if keyword in user_message.lower():
            filters.update(rule)

    # Budget parsing
    price_match = re.search(r'under \$([0-9]+\.?[0-9]*)', user_message.lower())
    if not price_match:
        price_match = re.search(r'less than ([0-9]+\.?[0-9]*) ?dollars', user_message.lower())
    if price_match:
        filters['price_max'] = float(price_match.group(1))

    results = query_database(filters)
    product_match = bool(results)
    interest = calculate_interest_score(user_message, product_match)

    if not results:
        product_info = "No matching products found."
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
